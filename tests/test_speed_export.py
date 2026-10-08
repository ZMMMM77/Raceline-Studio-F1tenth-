import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from raceline_studio import app as studio


class SpeedExportTests(unittest.TestCase):
    def test_speed_endpoint_writes_waypoints_plot_and_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            (path/'report.json').write_text('{}',encoding='utf-8')
            s=np.arange(0,10,.5)
            result={'result_id':'test_speed_result','route':np.c_[s,np.zeros_like(s)].tolist(),
                    's':s.tolist(),'heading':np.zeros_like(s).tolist(),
                    'curvature':np.r_[1.,np.zeros(len(s)-1)].tolist(),
                    'steering':np.zeros_like(s).tolist(),'metrics':{'length':10.0},
                    'files':{'zip':'/outputs/test_speed_result/results.zip'}}
            studio.RESULTS[result['result_id']]={'result':result,'path':path,'track':None}
            try:
                response=studio.app.test_client().post('/api/speed-profile',
                    json={'result_id':result['result_id'],'parameters':{
                        'base_speed':4,'lateral_accel':1,'acceleration':1,'braking':1}},
                    headers={'X-Raceline-Local':'1','Host':'localhost:8766'})
                self.assertEqual(response.status_code,200,response.get_json())
                data=response.get_json()
                self.assertEqual(len(data['speed']),len(s))
                self.assertTrue((path/'speed_waypoints.csv').exists())
                self.assertTrue((path/'speed_profile.png').exists())
                self.assertTrue((path/'results.zip').exists())
                self.assertEqual((path/'speed_waypoints.csv').read_text().splitlines()[0],
                    '# x_m,y_m,vx_mps,s_m,psi_rad,kappa_radpm,ax_mps2,steering_rad')
                self.assertIn('speed_profile',json.loads((path/'report.json').read_text()))
            finally:
                studio.RESULTS.pop(result['result_id'],None)

    def test_imported_route_can_generate_speed_without_optimization(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            (path/'import_report.json').write_text('{}',encoding='utf-8')
            t=np.linspace(0,2*np.pi,40,endpoint=False)
            route=np.c_[10*np.cos(t),10*np.sin(t)]
            ident='test_import_speed'
            studio.TRACKS[ident]={'id':ident,'dir':path,'source_route':route,'center':route}
            try:
                response=studio.app.test_client().post('/api/speed-profile',
                    json={'track_id':ident,'parameters':{'base_speed':4,'lateral_accel':2,
                         'acceleration':1,'braking':1}},
                    headers={'X-Raceline-Local':'1','Host':'localhost:8766'})
                self.assertEqual(response.status_code,200,response.get_json())
                data=response.get_json()
                self.assertEqual(len(data['route']),len(data['speed']))
                np.testing.assert_allclose(data['route'],route)
                self.assertTrue((path/'speed_waypoints.csv').exists())
                self.assertEqual((path/'speed_waypoints.csv').read_text().splitlines()[0],
                    '# x_m,y_m,vx_mps,s_m,psi_rad,kappa_radpm,ax_mps2')
            finally:
                studio.TRACKS.pop(ident,None)


if __name__=='__main__':unittest.main()
