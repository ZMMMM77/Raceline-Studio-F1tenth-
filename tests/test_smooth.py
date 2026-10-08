import unittest
import numpy as np
from waypoint_edit import smooth_points
from planner import PlanningError
from file_preview import route_preview
class SmoothTests(unittest.TestCase):
    def setUp(self):
        t=np.linspace(0,2*np.pi,80,endpoint=False);radius=10+.25*np.cos(20*t);self.p=np.c_[radius*np.cos(t),radius*np.sin(t)]
    def test_reduces_high_frequency_noise_and_keeps_count(self):
        q=smooth_points(self.p);self.assertEqual(q.shape,self.p.shape)
        bending=lambda p:np.sum((np.roll(p,1,axis=0)+np.roll(p,-1,axis=0)-2*p)**2)
        self.assertLess(bending(q),bending(self.p)*.5)
        self.assertAlmostEqual(np.linalg.norm(q,axis=1).mean(),10,delta=.15)
    def test_local_does_not_move_unselected_points(self):
        indices=[78,79,0,1,2];q=smooth_points(self.p,indices);mask=np.ones(80,bool);mask[indices]=False
        np.testing.assert_array_equal(q[mask],self.p[mask]);self.assertGreater(np.linalg.norm(q[indices]-self.p[indices]),0)
    def test_periodic_seam_and_source_unchanged(self):
        old=self.p.copy();q=smooth_points(self.p);shift=smooth_points(np.roll(self.p,17,axis=0));np.testing.assert_allclose(shift,np.roll(q,17,axis=0));np.testing.assert_array_equal(old,self.p)
    def test_invalid_controls(self):
        for selected in ([1],[1,1,1],[0,1,80],[0,1,True]):
            with self.assertRaises(PlanningError):smooth_points(self.p,selected)
        with self.assertRaises(PlanningError):smooth_points(self.p,iterations=100)
        with self.assertRaises(PlanningError):smooth_points(self.p,strength=float('nan'))
    def test_named_widths_preserved_in_csv_preview(self):
        text='# x_m,y_m,w_tr_right_m,w_tr_left_m\n'+'\n'.join(f'{x},{y},1.2,1.4' for x,y in self.p)
        r=route_preview(text.encode());self.assertEqual(len(r['boundaries']),2);self.assertEqual(len(r['boundaries'][0]),80)
        width=np.linalg.norm(np.array(r['boundaries'][0])-self.p,axis=1);np.testing.assert_allclose(width,1.2)
