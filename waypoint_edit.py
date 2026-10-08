"""Waypoint editing operates on a copy; the optimizer and its results are unchanged."""
import numpy as np
from flask import request, jsonify
from planner import PlanningError, clean_loop, arc, resample, route_geometry, has_crossing

def points(value):
    try:p=np.asarray(value,dtype=float)
    except (TypeError,ValueError):raise PlanningError('Waypoint 坐标必须是有效数字。')
    if p.ndim!=2 or p.shape[1]!=2 or not 12<=len(p)<=5000 or not np.isfinite(p).all():
        raise PlanningError('需要 12–5000 个有限的 x/y 坐标。')
    if np.any(np.linalg.norm(np.roll(p,-1,axis=0)-p,axis=1)<1e-7):
        raise PlanningError('相邻点不能重合；闭环无需重复首点。')
    return p

def resample_points(value,count):
    p=points(value)
    if isinstance(count,bool) or not isinstance(count,int) or not 12<=count<=5000:
        raise PlanningError('Waypoint 个数必须是 12–5000 的整数。')
    q,_=resample(p,count=count)
    points(q)
    return q

def smooth_points(value, selection=None, iterations=8, strength=0.6):
    p=points(value).copy()
    if isinstance(iterations,bool) or not isinstance(iterations,int) or not 1<=iterations<=30:
        raise PlanningError('平滑次数必须为 1–30 的整数。')
    if isinstance(strength,bool) or not isinstance(strength,(int,float)) or not np.isfinite(strength) or not 0<strength<=1:
        raise PlanningError('平滑强度应大于 0 且不超过 1。')
    mask=np.ones(len(p),dtype=bool)
    if selection is not None:
        if not isinstance(selection,list) or len(selection)<3 or any(isinstance(i,bool) or not isinstance(i,int) or not 0<=i<len(p) for i in selection):
            raise PlanningError('局部平滑需要至少选中三个有效节点。')
        if len(set(selection))<3:raise PlanningError('局部平滑需要至少三个不同节点。')
        mask[:]=False;mask[selection]=True
    # Two opposite Laplacian passes reduce the shrinkage of ordinary averaging.
    # Periodic neighbors handle a selected segment crossing the start/end seam.
    for _ in range(iterations):
        for step in (0.5*strength,-0.53*strength):
            delta=(np.roll(p,1,axis=0)+np.roll(p,-1,axis=0))/2-p
            p[mask]+=step*delta[mask]
    points(p)
    return p

def install_waypoint_edit(app,directory,json_write,pack):
    @app.post('/api/waypoints/resample')
    def resample_route():
        d=request.get_json() or {};q=resample_points(d.get('points'),d.get('count'))
        return jsonify(points=q.tolist(),count=len(q))
    @app.post('/api/waypoints/smooth')
    def smooth_route():
        d=request.get_json() or {};q=smooth_points(d.get('points'),d.get('selection'),d.get('iterations',8),d.get('strength',0.6))
        return jsonify(points=q.tolist(),count=len(q))
    @app.post('/api/waypoints/export')
    def export_route():
        d=request.get_json() or {};p=points(d.get('points'))
        # This exports geometry, not the original optimizer's feasibility certificate.
        g=route_geometry(p);ident,path=directory('edited_waypoints')
        np.savetxt(path/'edited_waypoints.csv',np.c_[p,g['s'],g['heading'],g['curvature']],delimiter=',',
                   header='x_m,y_m,s_m,psi_rad,kappa_radpm',fmt='%.9f')
        report={'kind':'manually_edited_geometry','waypoint_count':len(p),'length_m':g['metrics']['length'],
                'source':str(d.get('source',''))[:500],'validated_feasible':False,
                'self_crossing':bool(has_crossing(p)),
                'note':'Edited/resampled path. Original optimization and speed profile are not modified. No speed column; clearance and vehicle constraints have not been revalidated.'}
        json_write(path/'report.json',report);pack(path)
        return jsonify(count=len(p),files={'edited':f'/outputs/{ident}/edited_waypoints.csv','zip':f'/outputs/{ident}/results.zip'},output_dir=str(path),report=report)
