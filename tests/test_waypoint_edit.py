import io,unittest,tempfile,json,zipfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
from raceline_studio.planner import PlanningError
from raceline_studio.waypoint_edit import resample_points,points
from raceline_studio.app import app
class EditTests(unittest.TestCase):
    def setUp(self):
        t=np.linspace(0,2*np.pi,80,endpoint=False);self.p=np.c_[10*np.cos(t),10*np.sin(t)]
    def test_exact_counts_and_first_point(self):
        for count in (12,37,250,5000):
            q=resample_points(self.p,count);self.assertEqual(q.shape,(count,2));np.testing.assert_allclose(q[0],self.p[0]);self.assertGreater(np.linalg.norm(q[-1]-q[0]),0)
    def test_source_unchanged(self):
        before=self.p.copy();resample_points(self.p,31);np.testing.assert_array_equal(before,self.p)
    def test_bad_count_and_coordinates(self):
        for count in (0,11,5001,30.5,True,'20'):
            with self.assertRaises(PlanningError):resample_points(self.p,count)
        for p in ([[1,2]]*12,[[float('nan'),0]]*12):
            with self.assertRaises(PlanningError):points(p)
    def test_endpoint_export_dragged_coordinates_and_no_old_speed(self):
        p=resample_points(self.p,48);p[3]+=[.05,.02]
        with tempfile.TemporaryDirectory() as t:
            target=Path(t);ident='20261008_010101_aabbccdd'
            with patch('raceline_studio.app.directory',return_value=(ident,target)):
                # installer has a reference to the original helper; patch its OUTPUT instead
                with patch('raceline_studio.app.OUTPUT',target):
                    c=app.test_client();r=c.post('/api/waypoints/export',json={'points':p.tolist(),'source':'test'},headers={'X-Raceline-Local':'1'})
            self.assertEqual(r.status_code,200,r.json);data=np.loadtxt(Path(r.json['output_dir'])/'edited_waypoints.csv',delimiter=',');np.testing.assert_allclose(data[:,:2],p,atol=1e-8)
            self.assertEqual(len(data),48);self.assertFalse(r.json['report']['validated_feasible']);self.assertEqual(data.shape[1],5)
    def test_local_guard_and_invalid_input(self):
        c=app.test_client();self.assertEqual(c.post('/api/waypoints/resample',json={}).status_code,403)
        r=c.post('/api/waypoints/resample',json={'points':self.p.tolist(),'count':30},headers={'X-Raceline-Local':'1'});self.assertEqual(r.status_code,200);self.assertEqual(len(r.json['points']),30)
