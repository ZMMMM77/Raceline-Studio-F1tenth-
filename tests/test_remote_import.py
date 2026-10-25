import io
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image
from raceline_studio import app as studio
from raceline_studio.remote import RemoteError


class RemoteFiles:
    identity={'host':'car.test','username':'driver','port':22}

    def __init__(self, files):
        self.files=files
        self.lock=threading.RLock()
        self.connected=True
        self.read_paths=[]

    def status(self):
        return {'connected':self.connected}

    def path(self,path):
        if not isinstance(path,str) or not path:raise RemoteError('远程路径无效。')
        return path

    def read(self,path):
        self.read_paths.append(path)
        if path not in self.files:raise FileNotFoundError(path)
        return self.files[path]


class RemoteImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old_tracks=set(studio.TRACKS)
        self.old_results=set(studio.RESULTS)
        self.old_jobs=set(studio.JOBS)
        t=np.linspace(0,2*np.pi,100,endpoint=False)
        self.xy=np.c_[10*np.cos(t),10*np.sin(t)]
        self.csv=io.StringIO()
        np.savetxt(self.csv,np.c_[self.xy,np.full((100,2),2.)],delimiter=',',header='x_m,y_m,w_tr_right_m,w_tr_left_m')
        self.path='/tracks/center.csv'
        self.remote=RemoteFiles({self.path:self.csv.getvalue().encode()})
        self.patch_remote=patch.object(studio,'REMOTE',self.remote);self.patch_remote.start()
        self.patch_output=patch.object(studio,'OUTPUT',Path(self.tmp.name));self.patch_output.start()
        self.client=studio.app.test_client()
        self.headers={'X-Raceline-Local':'1','Host':'localhost:8766'}

    def tearDown(self):
        self.patch_remote.stop();self.patch_output.stop()
        for cache,old in [(studio.TRACKS,self.old_tracks),(studio.RESULTS,self.old_results),(studio.JOBS,self.old_jobs)]:
            for key in set(cache)-old:cache.pop(key,None)
        self.tmp.cleanup()

    def post(self,**options):
        form={'source':'remote','remote_csv':self.path,'remote_identity':json.dumps(self.remote.identity),'mode':'csv',**options}
        return self.client.post('/api/import',data=form,headers=self.headers)

    def test_remote_and_local_share_geometry_widths_and_report(self):
        remote=self.post();self.assertEqual(remote.status_code,200,remote.json)
        local=self.client.post('/api/import',data={'mode':'csv','csv':(io.BytesIO(self.remote.files[self.path]),'center.csv')},headers=self.headers)
        self.assertEqual(local.status_code,200,local.json)
        np.testing.assert_allclose(remote.json['center'],local.json['center'])
        np.testing.assert_allclose(remote.json['widths'],local.json['widths'])
        self.assertEqual(remote.json['remote_source']['path'],self.path)
        report=json.loads((Path(remote.json['output_dir'])/'import_report.json').read_text())
        self.assertEqual(report['remote_source']['identity'],self.remote.identity)
        self.assertEqual(self.remote.files[self.path],self.csv.getvalue().encode())

    def test_path_only_requires_width_then_uses_explicit_fallback(self):
        f=io.StringIO();np.savetxt(f,self.xy,delimiter=',',header='x_m,y_m')
        self.remote.files[self.path]=f.getvalue().encode()
        self.assertEqual(self.post().status_code,400)
        r=self.post(fallback_width='1.8',reverse='true')
        self.assertEqual(r.status_code,200,r.json)
        np.testing.assert_allclose(r.json['widths'],1.8)
        self.assertIn('统一宽度',' '.join(r.json['warnings']))

    def test_remote_map_resolves_yaml_image_and_preserves_map_constraints(self):
        yy,xx=np.mgrid[0:600,0:600]
        radius=np.hypot((xx-300)*.05,(yy-300)*.05)
        image=Image.fromarray(np.where((radius>7)&(radius<13),254,0).astype('uint8'))
        buf=io.BytesIO();image.save(buf,format='PNG')
        self.remote.files['/maps/track.yaml']=b'image: images/track.png\nresolution: 0.05\norigin: [-15, -15, 0]\n'
        self.remote.files['/maps/images/track.png']=buf.getvalue()
        r=self.post(remote_yaml='/maps/track.yaml')
        self.assertEqual(r.status_code,200,r.json)
        self.assertEqual(r.json['boundary_mode'],'map')
        self.assertEqual(r.json['map']['resolution'],.05)
        self.assertIn('/maps/images/track.png',self.remote.read_paths)
        self.assertEqual(r.json['remote_source']['yaml_path'],'/maps/track.yaml')

    def test_disconnected_changed_identity_missing_and_non_csv_are_rejected(self):
        self.remote.connected=False;self.assertEqual(self.post().status_code,400)
        self.remote.connected=True
        self.assertEqual(self.post(remote_identity='{}').status_code,400)
        self.assertEqual(self.post(remote_csv='/tracks/missing.csv').status_code,400)
        self.assertEqual(self.post(remote_csv='/tracks/not.csv.png').status_code,400)
        self.assertNotIn('/tracks/not.csv.png',self.remote.read_paths)
        self.assertEqual(set(studio.TRACKS),self.old_tracks)

    def test_open_route_stays_previewable_but_is_rejected_for_closed_loop_planning(self):
        self.remote.files[self.path]=b'x,y\n0,0\n1,1\n2,2\n'
        r=self.post(fallback_width='1.8')
        self.assertEqual(r.status_code,400)
        self.assertEqual(set(studio.TRACKS),self.old_tracks)

    def test_remote_import_can_optimize_and_download_min_curvature_csv(self):
        imported=self.post();self.assertEqual(imported.status_code,200,imported.json)
        p=dict(wheelbase=.3302,steer=24,car_width=.31,car_length=.58,rear_overhang=.1,reference='rear',margin=.1,nodes=80,spacing=.5,algorithm='min_curvature',max_runtime_s=5)
        job=self.client.post('/api/optimize',json={'track_id':imported.json['id'],'parameters':p},headers=self.headers)
        self.assertEqual(job.status_code,200,job.json)
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            result=self.client.get('/api/jobs/'+job.json['job_id'],headers=self.headers).json
            if result['status']!='running':break
            time.sleep(.05)
        self.assertEqual(result['status'],'done',result)
        output=result['result']
        self.assertEqual(output['metrics']['algorithm'],'min_curvature')
        self.assertTrue(output['metrics']['curvature_ok']);self.assertTrue(output['metrics']['boundary_ok'])
        downloaded=self.client.get(output['files']['route'],headers=self.headers)
        self.assertEqual(downloaded.status_code,200)
        self.assertIn(b'kappa_radpm',downloaded.data)
        self.assertTrue(output['files']['route'].endswith('/min_curvature_path.csv'))
        downloaded.close()
