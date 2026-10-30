import io
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image
from raceline_studio import app as studio
from raceline_studio.planner import MapData, PlanningError, resample
from test_remote_import import RemoteFiles


def ring_image(radius=5.,half_width=1.4,resolution=.05,format='PPM'):
    n=int((radius+half_width+1)*2/resolution)
    yy,xx=np.mgrid[:n,:n];r=np.hypot(xx-n/2,yy-n/2)*resolution
    pixels=np.where((r>radius-half_width)&(r<radius+half_width),254,0).astype('uint8')
    out=io.BytesIO();Image.fromarray(pixels).save(out,format=format)
    return out.getvalue()


class MapImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.caches=[(cache,set(cache)) for cache in (studio.TRACKS,studio.RESULTS,studio.JOBS)]
        self.yaml=b'image: images/map.pgm\nresolution: 0.05\norigin: [-8, -8, 0.3]\nnegate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.196\n'
        self.image=ring_image()
        self.remote=RemoteFiles({'/maps/map.yaml':self.yaml,'/maps/images/map.pgm':self.image})
        self.patches=[patch.object(studio,'OUTPUT',Path(self.tmp.name)),patch.object(studio,'REMOTE',self.remote)]
        for p in self.patches:p.start()
        self.client=studio.app.test_client();self.headers={'X-Raceline-Local':'1','Host':'localhost:8766'}

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        for cache,old in self.caches:
            for key in set(cache)-old:cache.pop(key,None)
        self.tmp.cleanup()

    def remote_import(self,**kwargs):
        return self.client.post('/api/import',headers=self.headers,data={
            'source':'remote','mode':'map','remote_yaml':'/maps/map.yaml',
            'remote_identity':json.dumps(self.remote.identity),**kwargs})

    def test_pgm_local_and_ssh_match_and_layers_preserve_original(self):
        before=dict(self.remote.files)
        r=self.remote_import();self.assertEqual(r.status_code,200,r.json)
        local=self.client.post('/api/import',headers=self.headers,data={'mode':'map',
            'yaml':(io.BytesIO(self.yaml),'map.yaml'),'image':(io.BytesIO(self.image),'map.pgm')})
        self.assertEqual(local.status_code,200,local.json)
        np.testing.assert_allclose(r.json['center'],local.json['center'])
        self.assertEqual(r.json['boundary_mode'],'map');self.assertEqual(r.json['source_kind'],'centerline')
        self.assertEqual(r.json['remote_source']['path'],'/maps/map.yaml')
        self.assertEqual(self.remote.files,before)
        track=studio.TRACKS[r.json['id']];original=MapData.read(self.image,self.yaml)
        np.testing.assert_array_equal(track['map'].free,original.free)
        np.testing.assert_array_equal(track['map'].sdf,original.sdf)
        self.assertEqual(set(r.json['preprocessing']),{'cleaned','changes','distance'})
        for url in r.json['preprocessing'].values():
            response=self.client.get(url,headers=self.headers)
            self.assertEqual(response.status_code,200)
            self.assertEqual(Image.open(io.BytesIO(response.data)).size,original.image.size)
            response.close()
        report=json.loads((track['dir']/'import_report.json').read_text())
        self.assertGreater(report['diagnostics']['cleanup']['distance_field_max_m'],0)
        self.assertGreater(report['diagnostics']['cleanup']['validation_points'],len(track['center']))

    def test_png_and_zero_smoothing_and_reverse(self):
        self.remote.files['/maps/map.yaml']=self.yaml.replace(b'map.pgm',b'map.png')
        self.remote.files['/maps/images/map.png']=ring_image(format='PNG')
        forward=self.remote_import(map_smoothing='0');self.assertEqual(forward.status_code,200,forward.json)
        reverse=self.remote_import(map_smoothing='0',reverse='true')
        self.assertEqual(reverse.status_code,200,reverse.json)
        np.testing.assert_allclose(forward.json['center'][::-1],reverse.json['center'])
        self.assertEqual(forward.json['diagnostics']['cleanup']['smoothing_applied_m'],0)

    def test_missing_invalid_yaml_and_changed_connection_fail_without_track(self):
        for kwargs in ({'remote_yaml':''},{'remote_yaml':'/maps/image.png'},
                       {'remote_identity':'{}'},{'map_smoothing':'nan'},{'map_smoothing':'-1'}):
            r=self.remote_import(**kwargs);self.assertEqual(r.status_code,400,r.json)
        self.remote.files['/maps/map.yaml']=b'resolution: 0.05\norigin: [0,0,0]\n'
        self.assertEqual(self.remote_import().status_code,400)
        self.remote.files['/maps/map.yaml']=self.yaml
        del self.remote.files['/maps/images/map.pgm']
        self.assertEqual(self.remote_import().status_code,400)
        self.assertEqual(set(studio.TRACKS),self.caches[0][1])

    def test_strong_smoothing_reduces_instead_of_cutting_corner(self):
        raw=ring_image(radius=2,half_width=.18,resolution=.025)
        m=MapData.read(raw,b'resolution: 0.025\norigin: [0,0,0]\n')
        p,w=m.extract(smoothing=1,cleanup=False)
        self.assertLess(m.cleanup_info['smoothing_applied_m'],1)
        dense,_=resample(p,spacing=.01)
        self.assertGreaterEqual(m.distance(dense).min(),0)
        self.assertTrue(np.all(w>0))

    def test_map_centerline_can_optimize_and_export(self):
        r=self.remote_import();self.assertEqual(r.status_code,200,r.json)
        params=dict(wheelbase=.3302,steer=24,car_width=.31,car_length=.58,rear_overhang=.1,
                    reference='rear',margin=.1,nodes=80,spacing=.2,algorithm='min_curvature',max_runtime_s=8)
        job=self.client.post('/api/optimize',json={'track_id':r.json['id'],'parameters':params},headers=self.headers)
        self.assertEqual(job.status_code,200,job.json)
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            status=self.client.get('/api/jobs/'+job.json['job_id'],headers=self.headers).json
            if status['status']!='running':break
            time.sleep(.05)
        self.assertEqual(status['status'],'done',status)
        self.assertTrue(status['result']['metrics']['boundary_ok'])
        self.assertTrue(status['result']['metrics']['curvature_ok'])
        with self.client.get(status['result']['files']['route'],headers=self.headers) as response:
            self.assertEqual(response.status_code,200);self.assertIn(b'kappa_radpm',response.data)


if __name__=='__main__':unittest.main()
