import io
import unittest
import numpy as np
from PIL import Image
from scipy.optimize._numdiff import approx_derivative
from planner import (MapData, PlanningError, parse_csv, normals, SplineProblem,
                     optimize, vehicle_parameters, plan_speed_profile)

PARAMS=dict(wheelbase=.3302,steer=24,car_width=.31,car_length=.58,
            rear_overhang=.1,reference='rear',margin=.1,nodes=80,spacing=.1)

class PlannerTests(unittest.TestCase):
    def test_csv_formats_and_closure(self):
        t=np.linspace(0,2*np.pi,25)
        rows=['# s_m; x_m; y_m; psi_rad; kappa_radpm; vx_mps; ax_mps2']
        rows.extend(f'{i};{np.cos(a)};{np.sin(a)};0;1;2;0' for i,a in enumerate(t))
        p,w,path_only=parse_csv('\n'.join(rows).encode())
        self.assertEqual(p.shape,(24,2));self.assertIsNone(w);self.assertTrue(path_only)

    def test_map_coordinates_rotate_and_unknown(self):
        b=io.BytesIO();Image.fromarray(np.full((60,80),255,np.uint8)).save(b,format='PNG')
        m=MapData.read(b.getvalue(),b'resolution: 0.1\norigin: [4, -3, 0.7]\n')
        pix=np.array([[20.,30.],[15.5,5.1]])
        np.testing.assert_allclose(m.to_pixel(m.to_world(pix)),pix,atol=1e-12)
        self.assertGreater(m.distance(m.to_world(pix[:1]))[0],1)
        self.assertLess(m.distance(np.array([[100.,100.]]))[0],0)

    def test_vehicle_conversion_and_missing(self):
        v=vehicle_parameters(PARAMS)
        self.assertAlmostEqual(v['curvature_limit'],np.tan(np.deg2rad(24))/.3302)
        inside=vehicle_parameters(dict(PARAMS,angle_type='inner',wheel_track=.25))
        self.assertGreater(inside['radius'],v['radius'])
        self.assertGreater(v['body_radius'],PARAMS['car_width']/2)
        with self.assertRaises(PlanningError):vehicle_parameters({})

    def test_constraint_derivatives(self):
        t=np.linspace(0,2*np.pi,80,endpoint=False);p=np.c_[10*np.cos(t),8*np.sin(t)]
        q=SplineProblem(p,np.full((80,2),2),None,vehicle_parameters(PARAMS),80)
        q.setup(240);x=.17+np.sin(t)*.05
        numerical=approx_derivative(lambda a:q.evaluate(a)[0],x,method='3-point')
        np.testing.assert_allclose(q.evaluate(x)[1],numerical,atol=2e-5,rtol=2e-4)
        g=approx_derivative(lambda a:q.objective(a)[0],x)
        np.testing.assert_allclose(q.objective(x)[1],g,atol=1e-6)

    def test_circle_known_optimum(self):
        t=np.linspace(0,2*np.pi,240,endpoint=False);p=np.c_[10*np.cos(t),10*np.sin(t)]
        result=optimize(p,np.full((len(p),2),2),None,dict(PARAMS,limit_mode='radius',radius=9))
        # Curvature constraint dominates the shorter inner boundary.
        self.assertGreater(result['metrics']['length'],2*np.pi*9-.01)
        self.assertLess(result['metrics']['length'],2*np.pi*9+.4)
        self.assertLessEqual(result['metrics']['max_curvature'],1/9+1e-5)
        self.assertTrue(result['metrics']['boundary_ok'])
        self.assertLess(result['metrics']['closure_error'],1e-9)

    def test_impossible_footprint_rejected(self):
        t=np.linspace(0,2*np.pi,80,endpoint=False);p=np.c_[10*np.cos(t),10*np.sin(t)]
        with self.assertRaises(PlanningError):optimize(p,np.full((80,2),.2),None,PARAMS)

    def test_closed_speed_profile_brakes_before_corner_across_csv_seam(self):
        s=np.arange(10,dtype=float);k=np.zeros(10);k[0]=1.0
        p=plan_speed_profile(s,k,10.0,6.0,1.0,2.0,1.0)
        v=p['speed'];a=p['acceleration']
        self.assertAlmostEqual(v[0],1.0)
        self.assertLess(v[-1],2.0)  # braking starts before corner at point zero
        self.assertLessEqual(np.max(a),2.0+1e-8)
        self.assertGreaterEqual(np.min(a),-1.0-1e-8)
        self.assertTrue(np.all(v<=6.0))

    def test_straight_speed_remains_at_baseline(self):
        p=plan_speed_profile(np.arange(10,dtype=float),np.zeros(10),10.0,3.0,1.5,1.0,1.5)
        np.testing.assert_allclose(p['speed'],3.0)
        self.assertEqual(p['metrics']['limited_points'],0)

if __name__=='__main__':unittest.main()
