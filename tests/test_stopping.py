import unittest
from unittest.mock import patch
import numpy as np
from raceline_studio import planner

PARAMS=dict(reference='rear',wheelbase=.3302,limit_mode='steering',steer=24,
            car_width=.31,car_length=.58,rear_overhang=.1,margin=.1,
            nodes=80,spacing=.1,algorithm='min_curvature',max_runtime_s=300,
            plateau_window=5,plateau_percent=.1)

def circle(radius=10):
    t=np.linspace(0,2*np.pi,160,endpoint=False)
    return np.c_[radius*np.cos(t),radius*np.sin(t)],np.full((len(t),2),2.)

class StoppingTests(unittest.TestCase):
    def test_normal_solver_still_converges(self):
        p,w=circle()
        r=planner.optimize(p,w,None,dict(PARAMS,plateau_percent=0))
        self.assertTrue(r['metrics']['converged'])
        self.assertFalse(r['metrics']['stopped_early'])
        self.assertTrue(r['metrics']['boundary_ok'])
        self.assertLess(r['metrics']['curvature_energy'],2*np.pi/10)

    def test_plateau_yields_valid_route_without_claiming_convergence(self):
        def solver(fun,x,callback,**kwargs):
            for _ in range(30):callback(x.copy())
            self.fail('flat feasible trajectory did not stop')
        p,w=circle()
        with patch.object(planner,'minimize',side_effect=solver):
            r=planner.optimize(p,w,None,PARAMS)
        self.assertEqual(r['metrics']['stop_reason'],'plateau')
        self.assertFalse(r['metrics']['converged'])
        self.assertTrue(r['metrics']['feasible'])
        self.assertEqual(r['metrics']['iterations'],6)

    def test_timeout_in_trial_evaluation_retains_accepted_iterate(self):
        clock=[0.]
        def solver(fun,x,callback,**kwargs):
            clock[0]=2.
            fun(x+100)  # This trial must never become the exported candidate.
            self.fail('deadline was not enforced')
        p,w=circle()
        with patch.object(planner.time,'monotonic',side_effect=lambda:clock[0]),patch.object(planner,'minimize',side_effect=solver):
            r=planner.optimize(p,w,None,dict(PARAMS,max_runtime_s=1))
        self.assertEqual(r['metrics']['stop_reason'],'time_limit')
        self.assertTrue(r['metrics']['boundary_ok'])
        self.assertFalse(r['metrics']['converged'])
        self.assertLess(np.max(np.linalg.norm(r['route'],axis=1)),10.1)

    def test_timeout_cannot_export_infeasible_route(self):
        clock=[0.]
        def solver(fun,x,callback,**kwargs):
            clock[0]=2.;fun(x)
        p,w=circle(.5)  # Exceeds the steering curvature limit.
        with patch.object(planner.time,'monotonic',side_effect=lambda:clock[0]),patch.object(planner,'minimize',side_effect=solver):
            with self.assertRaisesRegex(planner.PlanningError,'未通过加密约束检查'):
                planner.optimize(p,w,None,dict(PARAMS,max_runtime_s=1))

    def test_deadline_includes_coarse_initialization(self):
        clock=[0.];sizes=[]
        def solver(fun,x,callback,**kwargs):
            sizes.append(len(x));clock[0]=2.;fun(x)
        p,w=circle()
        with patch.object(planner.time,'monotonic',side_effect=lambda:clock[0]),patch.object(planner,'minimize',side_effect=solver):
            r=planner.optimize(p,w,None,dict(PARAMS,nodes=140,max_runtime_s=1))
        self.assertEqual(sizes,[80,140])
        self.assertEqual(r['metrics']['stop_reason'],'time_limit')
        self.assertTrue(r['metrics']['feasible'])

    def test_plateau_window_resets_after_refinement(self):
        counts=[];original=planner._validate_candidate
        def solver(fun,x,callback,**kwargs):
            counts.append(0)
            for _ in range(30):
                counts[-1]+=1;callback(x.copy())
        checks=[0]
        def validate(*args):
            checked=original(*args);checks[0]+=1
            if checks[0]==1:checked['valid']=False
            return checked
        p,w=circle()
        with patch.object(planner,'minimize',side_effect=solver),patch.object(planner,'_validate_candidate',side_effect=validate):
            r=planner.optimize(p,w,None,PARAMS)
        self.assertEqual(counts,[6,6])
        self.assertEqual(r['metrics']['stop_reason'],'plateau')

    def test_invalid_cutoff_parameters_rejected(self):
        for fields in ({'max_runtime_s':0},{'plateau_window':5.5},{'plateau_percent':float('nan')}):
            with self.assertRaises(planner.PlanningError):
                planner.optimization_limits(dict(PARAMS,**fields))

if __name__=='__main__':unittest.main()
