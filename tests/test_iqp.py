import io
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image
from scipy.optimize._numdiff import approx_derivative
from raceline_studio.planner import MapData,vehicle_parameters,optimize,PlanningError,resample
from raceline_studio.iqp import covering_discs,Fields,FootprintProblem,validate
from test_planner import PARAMS


class IQPTests(unittest.TestCase):
    def circle(self,radius=5,count=80):
        t=np.linspace(0,2*np.pi,count,endpoint=False)
        return np.c_[radius*np.cos(t),radius*np.sin(t)]

    def test_discs_cover_full_rectangle_including_interior(self):
        vehicle=vehicle_parameters(PARAMS);offsets,radius=covering_discs(vehicle)
        x,y=np.meshgrid(np.linspace(-.1,.48,121),np.linspace(-.155,.155,81))
        distance=np.sqrt((x[...,None]-offsets)**2+y[...,None]**2).min(axis=-1)
        self.assertLessEqual(distance.max(),radius+1e-12)

    def test_rotating_cover_detects_obstacle_inside_body(self):
        raw=np.full((1000,1000),254,np.uint8);raw[499:502,522:525]=0
        image=io.BytesIO();Image.fromarray(raw).save(image,format='PNG')
        m=MapData.read(image.getvalue(),b'resolution: 0.01\norigin: [0,0,0]\n')
        offsets,radius=covering_discs(vehicle_parameters(PARAMS))
        pose=np.array([5.,5.]);centres=pose+offsets[:,None]*[1.,0.]
        self.assertGreater(m.distance(pose[None,:])[0],0)
        self.assertLess(np.min(m.distance(centres)-radius),0)

    def test_analytic_body_and_heading_gradients(self):
        p=self.circle();w=np.full((len(p),2),1.)
        problem=FootprintProblem(p,w,vehicle_parameters(PARAMS),80,Fields(p,w,None,'csv'))
        problem.setup(240);x=.02*np.sin(np.arange(80)*.2)
        actual=problem.evaluate(x)[1]
        numerical=approx_derivative(lambda a:problem.evaluate(a)[0],x)
        np.testing.assert_allclose(actual,numerical,atol=2e-5,rtol=2e-4)

    def test_recentring_cannot_move_physical_csv_walls(self):
        p=self.circle();w=np.full((80,2),.5);fields=Fields(p,w,None,'csv')
        outside=p*1.16
        problem=FootprintProblem(outside,np.full_like(w,2),vehicle_parameters(PARAMS),80,fields)
        problem.setup(320)
        self.assertFalse(validate(problem,np.zeros(80),.1)['boundary_ok'])

    def test_narrow_ring_accepts_real_dimensions_and_preserves_margin(self):
        p=self.circle();w=np.full((80,2),.5)
        # The old enclosing circle cannot fit; the rotated full body can.
        with self.assertRaises(PlanningError):optimize(p,w,None,dict(PARAMS,algorithm='min_curvature',solver='legacy'))
        result=optimize(p,w,None,dict(PARAMS,algorithm='min_curvature',max_runtime_s=8))
        metrics=result['metrics']
        self.assertEqual(metrics['solver'],'iterative_qp')
        self.assertTrue(metrics['boundary_ok'] and metrics['curvature_ok'])
        self.assertGreaterEqual(metrics['min_clearance'],PARAMS['margin']-1e-4)
        self.assertEqual(metrics['vehicle']['car_width'],PARAMS['car_width'])
        self.assertEqual(metrics['vehicle']['car_length'],PARAMS['car_length'])
        valid=[record['curvature_energy'] for record in metrics['seeds'] if record['valid']]
        self.assertAlmostEqual(metrics['curvature_energy'],min(valid),places=7)

    def test_timeout_and_rejected_qp_never_export_unchecked_trial(self):
        p=self.circle();w=np.full((80,2),1.)
        with patch('raceline_studio.iqp.qp_step',return_value=np.full(80,100.)):
            result=optimize(p,w,None,dict(PARAMS,algorithm='min_curvature',max_runtime_s=2))
        self.assertTrue(result['metrics']['boundary_ok'])
        self.assertLess(np.max(np.linalg.norm(result['route'],axis=1)),5.1)

    def test_legacy_solver_remains_selectable(self):
        p=self.circle(10);w=np.full((80,2),2.)
        result=optimize(p,w,None,dict(PARAMS,algorithm='min_curvature',solver='legacy'))
        self.assertIn('SLSQP',result['metrics']['method'])


if __name__=='__main__':unittest.main()
