import copy
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from PIL import Image
from scipy.optimize._numdiff import approx_derivative
from raceline_studio import app as studio
from raceline_studio.exclusions import (ExclusionField, ExclusionStore, ExclusionConflict,
                                       track_key, validate_zones)
from raceline_studio.planner import (PlanningError, MapData, SplineProblem, optimize,
                                    _validate_candidate, vehicle_parameters)
from raceline_studio.iqp import Fields, FootprintProblem, covering_discs, validate
from test_planner import PARAMS


def circle():
    t=np.linspace(0,2*np.pi,160,endpoint=False)
    return np.c_[5*np.cos(t),5*np.sin(t)],np.full((len(t),2),1.5)

ZONE=[[4.9,-1.1],[6.8,-1.1],[6.8,1.1],[4.9,1.1]]


class ExclusionGeometryTests(unittest.TestCase):
    def test_signed_distance_and_gradient_for_concave_and_overlapping_zones(self):
        concave=[[0,0],[3,0],[3,1],[1,1],[1,3],[0,3]]
        field=ExclusionField([concave,[[2,-1],[4,-1],[4,.5],[2,.5]]])
        p=np.array([[.3,.4],[1.7,1.8],[3.2,-.3],[4.2,1.2]])
        self.assertLess(field.distance(p)[0],0)
        self.assertGreater(field.distance(p)[1],0)
        self.assertLess(field.distance(p)[2],0)
        for point in p:
            numerical=approx_derivative(lambda x:field.distance(x[None]),point).ravel()
            np.testing.assert_allclose(field.distance(point[None],True)[1][0],numerical,atol=1e-6)
        np.testing.assert_allclose(ExclusionField([concave[::-1]]).distance(p),ExclusionField([concave]).distance(p))

    def test_invalid_polygons_rejected(self):
        invalid=[None,[[]],[[[0,0],[1,1],[0,1],[1,0]]],[[[0,0],[1,0],[2,0]]],
                 [[[0,0],[1,0],[1,0],[0,1]]],[[[0,0],[float('nan'),0],[0,1]]],
                 [[[0,0],[1,0],[1,1],[.5,0],[0,1]]],[ZONE]*21]
        for zones in invalid:
            with self.subTest(zones=zones),self.assertRaises(PlanningError):validate_zones(zones)

    def test_vehicle_body_is_blocked_even_with_reference_outside_zone(self):
        p,w=circle();vehicle=vehicle_parameters(PARAMS)
        zone=[[[4.95,.18],[5.05,.18],[5.05,.32],[4.95,.32]]]
        field=ExclusionField(zone)
        self.assertGreater(field.distance(p[:1])[0],0)
        original=FootprintProblem(p,w,vehicle,80,Fields(p,w,None,'csv'))
        blocked=FootprintProblem(p,w,vehicle,80,Fields(p,w,None,'csv',field))
        for problem in (original,blocked):problem.setup(320)
        self.assertTrue(validate(original,np.zeros(80),.1)['valid'])
        self.assertFalse(validate(blocked,np.zeros(80),.1)['boundary_ok'])

    def test_legacy_dense_validation_and_constraint_gradient_use_zones(self):
        p,w=circle();field=ExclusionField([ZONE])
        base=SplineProblem(p,w,None,vehicle_parameters(PARAMS),80,'shortest')
        problem=SplineProblem(p,w,None,vehicle_parameters(PARAMS),80,'shortest',field)
        for q in (base,problem):q.setup(320)
        self.assertTrue(_validate_candidate(base,np.zeros(80),.1)['valid'])
        self.assertFalse(_validate_candidate(problem,np.zeros(80),.1)['boundary_ok'])
        x=.003*np.sin(np.arange(80)*.17)
        # Only compare new polygon constraints, away from other nonsmooth walls.
        numeric=approx_derivative(lambda a:problem.evaluate(a)[0][-len(problem.t):],x)
        np.testing.assert_allclose(problem.evaluate(x)[1][-len(problem.t):],numeric,atol=2e-5)

    def test_both_solvers_repair_reference_and_leave_vehicle_clearance(self):
        p,w=circle();original=p.copy();field=ExclusionField([ZONE])
        self.assertLess(field.distance(p).min(),0)  # Supplied CSV crosses new zone.
        for solver in ('iterative_qp','legacy'):
            params=dict(PARAMS,algorithm='min_curvature',solver=solver,max_runtime_s=12,exclusion_zones=[ZONE])
            result=optimize(p,w,None,params)
            route=np.asarray(result['route']);heading=np.asarray(result['heading'])
            tangent=np.c_[np.cos(heading),np.sin(heading)]
            offsets,radius=covering_discs(vehicle_parameters(params))
            body_clearance=min(field.distance(route+offset*tangent).min()-radius for offset in offsets)
            self.assertGreaterEqual(body_clearance,params['margin']-1e-4)
            self.assertTrue(result['metrics']['boundary_ok'])
            self.assertEqual(result['metrics']['exclusion_count'],1)
            self.assertLess(route[0,0],4.7)
        np.testing.assert_array_equal(p,original)

    def test_no_unchecked_export_when_all_space_is_forbidden(self):
        p,w=circle();zones=[[[-20,-20],[20,-20],[20,20],[-20,20]]]
        with patch('raceline_studio.iqp.qp_step',return_value=None):
            with self.assertRaisesRegex(PlanningError,'禁行区'):
                optimize(p,w,None,dict(PARAMS,algorithm='min_curvature',exclusion_zones=zones,max_runtime_s=1))

    def test_map_constraints_and_source_raster_remain_authoritative(self):
        p,w=circle();yy,xx=np.mgrid[:320,:320]
        r=np.hypot((xx+.5)*.05-8,8-(yy+.5)*.05)
        pixels=np.where((r>3.5)&(r<6.5),254,0).astype('uint8')
        raw=io.BytesIO();Image.fromarray(pixels).save(raw,format='PNG')
        m=MapData.read(raw.getvalue(),b'resolution: 0.05\norigin: [-8,-8,0]\n')
        before=(m.free.copy(),m.sdf.copy(),np.array(m.image))
        result=optimize(p,w,m,dict(PARAMS,algorithm='min_curvature',boundary_mode='map',
                                 exclusion_zones=[ZONE],max_runtime_s=12))
        route=np.asarray(result['route']);angle=np.asarray(result['heading'])
        offsets,radius=covering_discs(vehicle_parameters(PARAMS))
        field=ExclusionField([ZONE]);tangent=np.c_[np.cos(angle),np.sin(angle)]
        for offset in offsets:
            centres=route+offset*tangent
            self.assertGreaterEqual(np.minimum(m.distance(centres),field.distance(centres)).min()-radius,PARAMS['margin']-1e-4)
        for actual,expected in zip((m.free,m.sdf,np.array(m.image)),before):
            np.testing.assert_array_equal(actual,expected)


class ExclusionPersistenceTests(unittest.TestCase):
    def test_atomic_save_reload_conflict_and_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            key='a'*64;store=ExclusionStore(tmp);first=store.load(key)
            saved=store.save(key,[ZONE],first['revision'])
            self.assertEqual(ExclusionStore(tmp).load(key),saved)
            with self.assertRaises(ExclusionConflict):store.save(key,[],first['revision'])
            self.assertEqual(store.save(key,[],saved['revision'])['zones'],[])
            self.assertFalse(list(Path(tmp).glob('*.tmp')))

    def test_map_identity_tracks_origin_occupancy_and_resolution_not_csv(self):
        raw=io.BytesIO();Image.fromarray(np.full((60,80),254,np.uint8)).save(raw,format='PNG')
        m=MapData.read(raw.getvalue(),b'resolution: 0.1\norigin: [0,0,0]\n')
        p,w=circle();key=track_key(p,w,m)
        self.assertEqual(key,track_key(p[::-1],w,m))
        for change in ('origin','resolution','free'):
            modified=copy.deepcopy(m)
            if change=='origin':modified.origin[2]=.5
            elif change=='resolution':modified.resolution=.2
            else:modified.free[20,30]=False
            self.assertNotEqual(key,track_key(p,w,modified))


class ExclusionAPITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=ExclusionStore(Path(self.tmp.name)/'settings')
        self.patches=[patch.object(studio,'OUTPUT',Path(self.tmp.name)),patch.object(studio,'EXCLUSIONS',self.store),patch.object(studio,'plot')]
        for p in self.patches:p.start()
        self.old=[(cache,set(cache)) for cache in (studio.TRACKS,studio.RESULTS,studio.JOBS)]
        self.client=studio.app.test_client();self.headers={'Host':'localhost:8766','X-Raceline-Local':'1'}
        p,w=circle();self.track=studio.register('test',p,w,None,[])
        self.url='/api/tracks/'+self.track['id']+'/exclusions'

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        for cache,old in self.old:
            for key in set(cache)-old:cache.pop(key,None)
        self.tmp.cleanup()

    def save(self,zones,revision=None):
        revision=revision or self.client.get(self.url,headers=self.headers).json['revision']
        return self.client.post(self.url,json={'zones':zones,'revision':revision},headers=self.headers)

    def test_reload_same_track_recovers_settings_and_local_guard_still_applies(self):
        r=self.save([ZONE]);self.assertEqual(r.status_code,200)
        p,w=circle();again=studio.register('another name',p,w,None,[])
        self.assertEqual(studio.public(again)['exclusions'],r.json)
        self.assertEqual(self.client.post(self.url,json={'zones':[]},headers={'Host':'localhost:8766'}).status_code,403)
        self.assertEqual(self.save([[[0,0],[1,1],[0,1],[1,0]]]).status_code,400)

    def test_stale_window_gets_current_configuration(self):
        first=self.client.get(self.url,headers=self.headers).json
        saved=self.save([ZONE]).json
        conflict=self.save([],first['revision'])
        self.assertEqual(conflict.status_code,409)
        self.assertEqual(conflict.json['current'],saved)
        r=self.client.post('/api/optimize',headers=self.headers,json={'track_id':self.track['id'],'parameters':PARAMS,'exclusion_revision':first['revision']})
        self.assertEqual(r.status_code,409)

    def test_compute_snapshot_and_export_record_survive_later_zone_changes(self):
        saved=self.save([ZONE]).json;captured=[]
        p=self.track['center'];count=len(p)
        result=dict(route=p.tolist(),s=np.arange(count).tolist(),curvature=[.2]*count,
                    steering=[0.]*count,heading=[0.]*count,metrics=dict(algorithm='min_curvature',stop_message='test'))
        def optimize(*args):
            captured.append(args[3]['exclusion_zones'])
            self.store.save(saved['key'],[],saved['revision'])
            return copy.deepcopy(result)
        with patch.object(studio,'optimize',side_effect=optimize),patch.object(studio.threading,'Thread',side_effect=lambda **kw:SimpleNamespace(start=kw['target'])):
            r=self.client.post('/api/optimize',headers=self.headers,json={'track_id':self.track['id'],'parameters':dict(PARAMS,exclusion_zones=[]),'exclusion_revision':saved['revision']})
        self.assertEqual(r.status_code,200,r.json)
        job=studio.JOBS[r.json['job_id']];self.assertEqual(job['status'],'done',job)
        self.assertEqual(captured,[[ZONE]])
        output=Path(job['result']['output_dir'])
        self.assertEqual(json.loads((output/'report.json').read_text())['exclusions'],saved)
        with zipfile.ZipFile(output/'results.zip') as z:
            self.assertEqual(json.loads(z.read('exclusion_zones.json')),saved)
        self.assertEqual(self.client.get('/outputs/'+output.name+'/exclusion_zones.json',headers=self.headers).status_code,200)


if __name__=='__main__':unittest.main()
