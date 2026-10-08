import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from velocity import calculate
from planner import PlanningError
from file_preview import route_preview
import app as studio

class VelocityTests(unittest.TestCase):
    def payload(self):
        t=np.linspace(0,2*np.pi,100,endpoint=False)
        return dict(points=np.c_[10*np.cos(t),3*np.sin(t)].tolist())
    def test_closed_loop_limits(self):
        r=calculate(self.payload());v=np.array(r['speed']);p=r['parameters'];xy=np.array(r['points']);ds=np.linalg.norm(np.roll(xy,-1,axis=0)-xy,axis=1)
        self.assertTrue(np.all(v>=p['v_min']));self.assertTrue(np.all(v<=p['v_max']))
        a=(np.roll(v,-1)**2-v*v)/(2*ds)
        self.assertLessEqual(a.max(),p['a_max']+1e-8);self.assertGreaterEqual(a.min(),-p['a_brake']-1e-8)
    def test_friction_and_manual_ratios(self):
        d=self.payload();low=calculate(d);high=calculate(dict(d,friction=[.7]*100))
        self.assertGreater(min(high['speed']),min(low['speed']))
        ratios=np.linspace(0,1,100);r=calculate(dict(d,ratio=ratios.tolist()));np.testing.assert_allclose(r['speed'],1.5+ratios*6.1)
    def test_bad_input(self):
        for extra in [dict(parameters={'v_max':0}),dict(parameters={'a_max':'bad'}),dict(parameters={'v_min':8,'v_max':2}),dict(ratio=[2]*100),dict(friction=[.4]),dict(friction=['bad']*100)]:
            with self.assertRaises(PlanningError):calculate(dict(self.payload(),**extra))
    def test_export_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(studio,'OUTPUT',Path(tmp)):
            c=studio.app.test_client();h={'Host':'localhost:8766','X-Raceline-Local':'1'}
            payload=dict(self.payload(),ratio=np.linspace(0,1,100).tolist(),friction=[.7]*100)
            response=c.post('/api/velocity/export',json=payload,headers=h)
            self.assertEqual(response.status_code,200,response.get_json());files=response.get_json()['files']
            pp=c.get(files['pp'],headers=h);mppi=c.get(files['mppi'],headers=h)
            self.assertEqual(pp.status_code,200);self.assertEqual(mppi.status_code,200)
            a=route_preview(pp.data)['velocity'];b=route_preview(mppi.data)['velocity']
            np.testing.assert_allclose(a['ratio'],payload['ratio'],atol=1e-9);np.testing.assert_allclose(b['speed'],1.5+6.1*np.array(payload['ratio']));self.assertEqual(a['friction'],[.7]*100)
            png=c.get(files['speed_png'],headers=h);self.assertEqual(png.status_code,200);png.close();pp.close();mppi.close()
