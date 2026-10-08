import unittest
import numpy as np
from scipy.optimize._numdiff import approx_derivative
from raceline_studio.planner import SplineProblem, optimize, vehicle_parameters, PlanningError, plan_speed_profile
from test_planner import PARAMS

class CurvatureTests(unittest.TestCase):
    def test_arc_weighted_gradient(self):
        t=np.linspace(0,2*np.pi,80,endpoint=False)
        p=np.c_[10*np.cos(t),8*np.sin(t)]
        q=SplineProblem(p,np.full((80,2),2),None,vehicle_parameters(PARAMS),80,'min_curvature')
        q.setup(400)
        x=.15+.07*np.sin(3*t)
        np.testing.assert_allclose(q.objective(x)[1],approx_derivative(lambda a:q.objective(a)[0],x),atol=1e-7,rtol=1e-5)

    def test_circle_curvature_prefers_larger_radius_and_supports_speed(self):
        t=np.linspace(0,2*np.pi,240,endpoint=False);p=np.c_[10*np.cos(t),10*np.sin(t)]
        w=np.full((240,2),2)
        short=optimize(p,w,None,PARAMS)
        smooth=optimize(p,w,None,dict(PARAMS,algorithm='min_curvature'))
        m=smooth['metrics']
        self.assertGreater(m['length'],2*np.pi*11)
        self.assertLess(m['curvature_energy'],short['metrics']['curvature_energy'])
        self.assertAlmostEqual(m['curvature_energy'],4*np.pi**2/m['length'],places=4)
        self.assertTrue(m['boundary_ok'] and m['curvature_ok'])
        v=plan_speed_profile(smooth['s'],smooth['curvature'],m['length'],10,1.5,1,1.5)
        self.assertEqual(len(v['speed']),len(smooth['route']))
        self.assertLessEqual(np.max(v['speed']**2*np.abs(smooth['curvature'])),1.5+1e-8)
        with self.assertRaises(PlanningError):optimize(p,w,None,dict(PARAMS,algorithm='typo'))
