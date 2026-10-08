import io
import unittest
import numpy as np
from raceline_studio.planner import parse_csv
class Formats(unittest.TestCase):
    def test_explicit_waypoints_never_become_widths(self):
        t=np.linspace(0,2*np.pi,30,endpoint=False);xy=np.c_[np.cos(t),np.sin(t)]
        for fmt,cols in [('pure_pursuit',np.c_[xy,t,np.ones(30)]),('mppi',np.c_[t,xy,np.zeros((30,6))])]:
            f=io.StringIO();np.savetxt(f,cols,delimiter=',')
            p,w,only=parse_csv(f.getvalue().encode(),fmt)
            np.testing.assert_allclose(p,xy);self.assertIsNone(w);self.assertTrue(only)
