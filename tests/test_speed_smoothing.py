import unittest
import numpy as np
from raceline_studio.velocity import calculate,smooth_velocity
from raceline_studio.planner import PlanningError
from raceline_studio import app as studio

class SmoothingTests(unittest.TestCase):
    def payload(self):
        t=np.arange(400)*2*np.pi/400
        r=dict(points=np.c_[15*np.cos(t),15*np.sin(t)].tolist(),parameters={'v_min':5,'v_max':10},ratio=[0.]*400,pinned_indices=list(range(120,125)))
        r['ratio'][120:125]=[1.]*5
        return r
    def check_fixed(self,d,r):
        a=np.array(d['ratio']);b=np.array(r['ratio']);p=d['pinned_indices']
        np.testing.assert_array_equal(a[p],b[p]);np.testing.assert_array_equal(d['points'],r['points'])
        inactive=np.ones(400,dtype=bool);inactive[r['smoothing']['affected_indices']]=False
        np.testing.assert_array_equal(a[inactive],b[inactive])
    def test_ten_mps_plateau_preserved_and_neighbors_raise(self):
        d=self.payload();r=smooth_velocity(d);self.check_fixed(d,r)
        self.assertEqual(r['speed'][120:125],[10.]*5)
        self.assertGreater(r['speed'][119],5);self.assertGreater(r['speed'][125],5)
        self.assertLess(max(abs(np.array(r['acceleration']))),max(abs(np.array(calculate(d)['acceleration']))))
    def test_low_fixed_patch_preserved_and_neighbors_lower(self):
        d=self.payload();d['ratio']=[1.]*400;d['ratio'][120:125]=[0.]*5
        r=smooth_velocity(d);self.check_fixed(d,r)
        self.assertEqual(r['speed'][120:125],[5.]*5);self.assertLess(r['speed'][119],10)
    def test_every_pinned_value_preserved_even_if_conflicting(self):
        d=self.payload();d['ratio'][120:125]=[1.,0.,.4,.8,1.]
        r=smooth_velocity(d);self.check_fixed(d,r);self.assertTrue(r['smoothing']['warning'])
    def test_all_points_pinned_does_not_change_anything(self):
        d=self.payload();d['pinned_indices']=list(range(400));r=smooth_velocity(d)
        self.assertEqual(r['ratio'],d['ratio']);self.assertTrue(r['smoothing']['warning'])
    def test_rotation_and_loop_seam(self):
        d=self.payload();shift=278;r=smooth_velocity(d)
        z=dict(d,points=np.roll(d['points'],shift,axis=0).tolist(),ratio=np.roll(d['ratio'],shift).tolist(),pinned_indices=[(i+shift)%400 for i in d['pinned_indices']])
        np.testing.assert_allclose(smooth_velocity(z)['speed'],np.roll(r['speed'],shift),atol=1e-9)
    def test_no_pins_and_bad_pins_rejected(self):
        for pins in [[],None,[-1],[True],[400],[1.2]]:
            with self.assertRaises(PlanningError):smooth_velocity(dict(self.payload(),pinned_indices=pins))
    def test_gentle_profile_unchanged(self):
        d=self.payload();d['ratio']=[.5]*400;r=smooth_velocity(d)
        self.assertEqual(r['ratio'],d['ratio']);self.assertEqual(r['smoothing']['changed_points'],0)
    def test_nonuniform_spacing_and_multiple_segments(self):
        d=self.payload();t=2*np.pi*(np.arange(400)/400)**1.3;d['points']=np.c_[15*np.cos(t),15*np.sin(t)].tolist()
        d['pinned_indices']+=list(range(250,255));d['ratio'][250:255]=[.7]*5
        self.check_fixed(d,smooth_velocity(d))
    def test_api_export_roundtrip(self):
        d=self.payload();c=studio.app.test_client();h={'Host':'localhost:8766','X-Raceline-Local':'1'}
        response=c.post('/api/velocity/smooth',json=d,headers=h);self.assertEqual(response.status_code,200)
        r=response.get_json();self.check_fixed(d,r)
        np.testing.assert_allclose(calculate(dict(d,ratio=r['ratio']))['speed'],r['speed'])
        self.assertEqual(c.post('/api/velocity/smooth',json=d,headers={'Host':'localhost:8766'}).status_code,403)
if __name__=='__main__':unittest.main()
