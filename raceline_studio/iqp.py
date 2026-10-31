"""Iterative minimum-curvature QP with fixed physical boundaries.

Each accepted step is a nonlinear spline, not a QP feasibility certificate.
Only independently validated candidates are eligible for output. The body is
covered by overlapping discs that rotate with the spline tangent; their union
covers the complete vehicle rectangle, including its interior and corners.
"""
import copy
import time
from collections import deque
import numpy as np
from matplotlib.path import Path
from scipy import sparse
from scipy.interpolate import CubicSpline
from scipy.spatial import cKDTree
from .planner import (PlanningError,SplineProblem,vehicle_parameters,
                      optimization_limits,positive,resample,arc,normals,has_crossing)


def covering_discs(vehicle):
    length=float(vehicle['car_length']);width=float(vehicle['car_width'])
    rear=float(vehicle['rear_overhang'])
    count=max(2,int(np.ceil(length/.1)))
    step=length/count
    offsets=np.linspace(-rear+step/2,length-rear-step/2,count)
    return offsets,float(np.hypot(width/2,step/2))


class Corridor:
    """Frozen CSV ribbon. Recentring the reference never moves these walls."""
    def __init__(self,center,widths):
        p=np.asarray(center);w=np.asarray(widths);n=normals(p)
        right=p+n*w[:,0,None];left=p-n*w[:,1,None]
        if has_crossing(right) or has_crossing(left):
            raise PlanningError('CSV 宽度构成的边界自交，请提供地图与 YAML 或修正宽度。')
        right,_=resample(right,spacing=.02);left,_=resample(left,spacing=.02)
        self.polygons=[Path(np.vstack([line,line[0]])) for line in (right,left)]
        self.boundary=np.vstack([right,left]);self.tree=cKDTree(self.boundary)
        self.deduction=max(np.linalg.norm(np.roll(line,-1,axis=0)-line,axis=1).max() for line in (right,left))/2
        self.extent=min(100,float(np.linalg.norm(np.ptp(self.boundary,axis=0))))

    def distance(self,points,gradient=False):
        p=np.asarray(points);dist,ids=self.tree.query(p)
        inside=self.polygons[0].contains_points(p)^self.polygons[1].contains_points(p)
        sign=np.where(inside,1.,-1.)
        value=sign*dist-self.deduction
        if not gradient:return value
        grad=sign[:,None]*(p-self.boundary[ids])/np.maximum(dist[:,None],1e-10)
        return value,grad

    def widths(self,points):
        p=np.asarray(points);n=normals(p);out=[]
        for sign in (1,-1):
            width=np.zeros(len(p));active=self.distance(p)>0
            for distance in np.arange(.025,self.extent,.025):
                ids=np.flatnonzero(active)
                if not len(ids):break
                good=self.distance(p[ids]+sign*distance*n[ids])>0
                width[ids[good]]=distance;active[ids[~good]]=False
            out.append(width)
        return np.maximum(np.column_stack(out),.01)


class Fields:
    def __init__(self,center,widths,map_data,boundary_mode):
        self.map=map_data
        self.corridor=Corridor(center,widths) if boundary_mode=='csv' else None

    def distance(self,p,gradient=False):
        fields=[f for f in (self.map,self.corridor) if f is not None]
        if not gradient:return np.minimum.reduce([f.distance(p) for f in fields])
        values,grads=zip(*(f.distance(p,True) for f in fields))
        ids=np.argmin(values,axis=0);rows=np.arange(len(p))
        return np.asarray(values)[ids,rows],np.asarray(grads)[ids,rows]

    def widths(self,p):
        # These rays only bound the local step; collision checks use frozen fields.
        if self.map is not None:return self.map.widths(p,cap=False)
        return self.corridor.widths(p)


class FootprintProblem(SplineProblem):
    def __init__(self,center,widths,vehicle,nodes,fields):
        super().__init__(center,widths,None,vehicle,nodes,'min_curvature')
        self.fields=fields;self.offsets,self.disc_radius=covering_discs(vehicle)

    def bounds(self):
        return list(zip(-self.w[:,1],self.w[:,0]))

    def evaluate(self,a):
        if self.last is not None and np.array_equal(a,self.last[0]):return self.last[1]
        pos=np.c_[self.xy[0][:,0]+self.mx[0]@a,self.xy[0][:,1]+self.my[0]@a]
        dx=self.xy[1][:,0]+self.mx[1]@a;dy=self.xy[1][:,1]+self.my[1]@a
        ddx=self.xy[2][:,0]+self.mx[2]@a;ddy=self.xy[2][:,1]+self.my[2]@a
        speed2=np.maximum(dx*dx+dy*dy,1e-12);speed=np.sqrt(speed2)
        k=(dx*ddy-dy*ddx)/speed2**1.5
        dk=(self.mx[1]*ddy[:,None]+self.my[2]*dx[:,None]-self.my[1]*ddx[:,None]-self.mx[2]*dy[:,None])/speed2[:,None]**1.5
        dk-=3*k[:,None]*(dx[:,None]*self.mx[1]+dy[:,None]*self.my[1])/speed2[:,None]
        tangent=np.c_[dx,dy]/speed[:,None]
        dspeed=(dx[:,None]*self.mx[1]+dy[:,None]*self.my[1])/speed[:,None]
        dtx=(self.mx[1]-tangent[:,0,None]*dspeed)/speed[:,None]
        dty=(self.my[1]-tangent[:,1,None]*dspeed)/speed[:,None]
        limit=self.vehicle['curvature_limit']*.997
        vals=[limit-k,limit+k,np.sum(np.c_[dx,dy]*self.tangent,axis=1)-.2]
        jacs=[-dk,dk,self.mx[1]*self.tangent[:,0,None]+self.my[1]*self.tangent[:,1,None]]
        for offset in self.offsets:
            points=pos+offset*tangent
            distance,gradient=self.fields.distance(points,True)
            vals.append(distance-self.disc_radius-self.vehicle['margin']-.025)
            jacs.append(gradient[:,0,None]*(self.mx[0]+offset*dtx)+gradient[:,1,None]*(self.my[0]+offset*dty))
        result=(np.concatenate(vals),np.vstack(jacs),pos,k)
        self.last=(a.copy(),result)
        return result


def validate(problem,x,spacing):
    spline=problem.spline(x)
    count=max(len(x)*30,int(np.ceil(problem.total/min(.02,spacing/3))))
    t=np.linspace(0,problem.total,count,endpoint=False)
    p=spline(t);v=spline(t,1);acc=spline(t,2);speed=np.linalg.norm(v,axis=1)
    k=(v[:,0]*acc[:,1]-v[:,1]*acc[:,0])/np.maximum(speed,1e-12)**3
    tangent=v/np.maximum(speed,1e-12)[:,None]
    # Bound between-pose motion using speed and angular speed of every disc.
    dt=problem.total/count
    motion=float(np.max(speed)*(1+max(abs(problem.offsets))*np.max(abs(k)))*dt/2)
    clearance=min(float(problem.fields.distance(p+offset*tangent).min())-problem.disc_radius for offset in problem.offsets)-motion
    refv=problem.base(t,1);reft=refv/np.maximum(np.linalg.norm(refv,axis=1),1e-12)[:,None]
    forward=bool(np.min(np.sum(v*reft,axis=1))>=.2-1e-4)
    curve=bool(np.max(abs(k))<=problem.vehicle['curvature_limit']+1e-5)
    boundary=bool(clearance>=problem.vehicle['margin']-1e-4)
    finite=bool(np.isfinite(p).all() and np.isfinite(k).all() and np.min(speed)>1e-8)
    crossing=has_crossing(p) if finite else True
    energy=float(np.mean(k*k*speed)*problem.total)
    return dict(valid=finite and curve and boundary and forward and not crossing,
                spline=spline,t=t,pp=p,k=k,energy=energy,min_clearance=clearance,
                curve_ok=curve,boundary_ok=boundary,forward_ok=forward,
                closure_error=float(np.linalg.norm(spline(0)-spline(problem.total))))


def qp_step(problem,x,trust,remaining):
    import osqp
    values,jac,_,k=problem.evaluate(x);n=len(x);m=len(k)
    dx=problem.xy[1][:,0]+problem.mx[1]@x;dy=problem.xy[1][:,1]+problem.my[1]@x
    weight=problem.weights*np.hypot(dx,dy)
    jk=-jac[:m]
    hessian=2*(jk.T*weight)@jk+np.eye(n)*1e-4
    gradient=problem.objective(x)[1]
    matrix=sparse.csc_matrix(np.where(abs(jac)>1e-10,jac,0))
    bounds=np.asarray(problem.bounds())
    lo=np.maximum(-trust,bounds[:,0]-x);hi=np.minimum(trust,bounds[:,1]-x)
    if np.any(lo>hi):return None
    if values.min() < -1e-6:
        # Restore feasibility first, without the poorly scaled curvature cost.
        matrix=sparse.hstack([matrix,np.ones((len(values),1))],format='csc')
        matrix=sparse.vstack([matrix,sparse.eye(n+1)],format='csc')
        lower=np.r_[-values,lo,0];upper=np.r_[np.full(len(values),np.inf),hi,np.inf]
        h=sparse.diags(np.r_[np.full(n,.1),2000.],format='csc')
        q=np.r_[np.zeros(n),100.]
    else:
        # A hard QP avoids a large slack penalty masking small curvature gradients.
        matrix=sparse.vstack([matrix,sparse.eye(n)],format='csc')
        lower=np.r_[-values,lo];upper=np.r_[np.full(len(values),np.inf),hi]
        scale=max(float(np.max(abs(gradient))),1e-3)
        h=sparse.csc_matrix(hessian/scale);q=gradient/scale
    solver=osqp.OSQP()
    solver.setup(P=h,q=q,A=matrix,l=lower,u=upper,verbose=False,eps_abs=1e-6,eps_rel=1e-6,
                 max_iter=8000,polishing=True,time_limit=max(.01,min(remaining,5.)))
    result=solver.solve(raise_error=False)
    if result.x is None or not np.isfinite(result.x).all() or result.info.status_val not in (1,2,7,8):return None
    linear=matrix@result.x
    if max(np.max(lower-linear),np.max(linear-upper))>3e-4:return None
    return result.x[:n]


def optimize_iqp(center,widths,map_data,parameters,progress=lambda *a:None):
    try:import osqp
    except ImportError:raise PlanningError('迭代 QP 需要 OSQP，请按 requirements.txt 安装依赖。') from None
    vehicle=vehicle_parameters(parameters)
    boundary_mode=parameters.get('boundary_mode','csv')
    if boundary_mode not in ('map','csv'):raise PlanningError('未知边界约束来源。')
    if boundary_mode=='map' and map_data is None:raise PlanningError('原始地图约束需要匹配的图片与 YAML。')
    runtime,window,percent=optimization_limits(parameters);started=time.monotonic()
    nodes=int(parameters.get('nodes',140))
    if nodes not in (80,140,220):raise PlanningError('请选择 80、140 或 220 个优化控制点。')
    spacing=positive(parameters.get('spacing',.1),'导出间距',low=.019,high=1)
    vehicle.update(boundary_mode=boundary_mode,footprint_model='oriented_covering_discs')
    if boundary_mode=='csv' and np.min(np.sum(widths,axis=1))<=float(vehicle['car_width'])+2*vehicle['margin']:
        raise PlanningError('CSV 走廊宽度不足以容纳车宽及两侧安全余量。')
    fields=Fields(center,widths,map_data,boundary_mode)
    p,w=resample(center,widths,count=nodes)
    seeds=[('CSV/reference',p,w)]
    # A second reference and a smoothed seed explore genuinely different starts.
    if map_data is not None:
        try:
            extracted,ew=copy.copy(map_data).extract()
            ep,ew=resample(extracted,ew,count=nodes)
            seeds.append(('map-centerline',ep,ew))
        except PlanningError:pass
    smooth,_=resample(p,count=nodes,smooth=.6)
    if np.min(fields.distance(smooth))>0:
        seeds.append(('smooth-reference',smooth,fields.widths(smooth)))
    else:
        seeds.append(('offset-reference',p+.1*normals(p),w))
    best=None;iteration=0;records=[];initial_energy=None;timed_out=False
    for seed_index,(name,reference,seed_widths) in enumerate(seeds):
        if time.monotonic()-started>=runtime:timed_out=True;break
        seed_deadline=started+runtime*(seed_index+1)/len(seeds)
        problem=FootprintProblem(reference,seed_widths,vehicle,nodes,fields)
        samples=max(nodes*4,int(np.ceil(problem.total/.08)))
        problem.setup(samples);x=np.zeros(nodes);trust=.3;stable=0;seed_best=None;reason='iteration_limit'
        history=deque(maxlen=window+1)
        record=dict(seed=name,valid=False,qp_iterations=0,references=1)
        baseline=validate(problem,x,spacing)
        if baseline['valid']:
            if initial_energy is None:initial_energy=baseline['energy']
            seed_best=(baseline,problem,x.copy())
            if best is None or baseline['energy']<best[0]['energy']:best=seed_best
        def merit(a):
            values=problem.evaluate(a)[0];violation=np.maximum(-values,0)
            return problem.objective(a)[0]+10000*np.dot(violation,violation)+1000*np.max(violation,initial=0)
        for local in range(80):
            elapsed=time.monotonic()-started
            if time.monotonic()>=seed_deadline:
                reason='seed_time_budget';timed_out=time.monotonic()-started>=runtime;break
            step=qp_step(problem,x,trust,seed_deadline-time.monotonic())
            iteration+=1;record['qp_iterations']+=1
            if step is None:
                trust*=.5
                if trust<.005:reason='qp_stalled';break
                continue
            old=merit(x);accepted=None
            for alpha in (1.,.5,.25,.125,.0625):
                candidate=x+alpha*step
                if merit(candidate)<old-1e-9:
                    accepted=candidate;break
            if accepted is None:
                stable+=1;trust*=.65
                if stable>=4 or trust<.005:reason='stationary';break
                continue
            improvement=(old-merit(accepted))/max(abs(old),1e-12)
            x=accepted;stable=stable+1 if improvement<1e-5 else 0
            trust=min(.5,trust*1.2)
            values=problem.evaluate(x)[0]
            if values.min()>=-1e-5:
                checked=validate(problem,x,spacing)
                if checked['valid']:
                    if initial_energy is None:initial_energy=checked['energy']
                    if seed_best is None or checked['energy']<seed_best[0]['energy']:
                        seed_best=(checked,problem,x.copy())
                    if best is None or checked['energy']<best[0]['energy']:best=(checked,problem,x.copy())
                    history.append(seed_best[0]['energy'])
                elif local<50 and samples<nodes*16:
                    samples*=2;problem.setup(samples)
            if iteration%3==0:
                progress(iteration,f'迭代 QP · 初值 {seed_index+1}/{len(seeds)} · 第 {local+1} 轮 · 曲率平方积分 {problem.objective(x)[0]:.5f} m⁻¹ · 已用 {elapsed:.0f}/{runtime:g} 秒')
            if stable>=4:reason='stationary';break
            if percent>0 and len(history)==window+1 and (history[0]-history[-1])/max(abs(history[0]),1e-12)<percent/100:
                reason='plateau';break
            # Rebuild normals and spline coordinates around the current route.
            # The Fields instance always remains the original physical corridor.
            if (local+1)%6==0 and values.min()>=-1e-5:
                reference,_=resample(problem.spline(x)(problem.s[:-1]),count=nodes)
                if np.min(fields.distance(reference))>0:
                    problem=FootprintProblem(reference,fields.widths(reference),vehicle,nodes,fields)
                    problem.setup(samples);x=np.zeros(nodes);record['references']+=1
        if seed_best:
            record.update(valid=True,curvature_energy=seed_best[0]['energy'],stop_reason=reason)
        else:record['stop_reason']=reason
        records.append(record)
    if best is None:
        raise PlanningError('迭代 QP 未找到通过车身轮廓、转向及闭环检查的路线。请核对地图和车辆参数，或增加计算时间。')
    checked,problem,x=best
    # Revalidate the selected winner, independent of all QP status codes.
    checked=validate(problem,x,spacing)
    if not checked['valid']:raise PlanningError('迭代 QP 的最终路线未通过加密检查，未导出。')
    spline=checked['spline'];dense_s,total=arc(checked['pp']);t=checked['t']
    out_s=np.linspace(0,total,max(20,int(np.ceil(total/spacing))),endpoint=False)
    out_t=np.interp(out_s,dense_s,np.r_[t,problem.total]);route=spline(out_t)
    v=spline(out_t,1);acc=spline(out_t,2)
    k=(v[:,0]*acc[:,1]-v[:,1]*acc[:,0])/np.linalg.norm(v,axis=1)**3
    offsets,radius=covering_discs(vehicle)
    selected=min((r for r in records if r['valid']),key=lambda r:r['curvature_energy'])
    converged=all(r.get('stop_reason')=='stationary' for r in records) and len(records)==len(seeds)
    stop='iqp_stationary' if converged else ('time_limit' if timed_out else 'iqp_best_feasible')
    message='迭代 QP 多初值求解结束；已选择通过检查的最低曲率积分路线'
    if timed_out:message=f'达到最大求解时间 {runtime:g} 秒；已选择通过检查的最佳 QP 路线'
    metrics=dict(length=total,center_length=arc(center)[1],saved=arc(center)[1]-total,
                 max_curvature=float(np.max(abs(checked['k']))),curvature_limit=vehicle['curvature_limit'],
                 min_clearance=checked['min_clearance'],required_clearance=vehicle['margin'],
                 clearance_definition='covered vehicle body to original boundary, after sampling deductions',
                 iterations=iteration,validation_points=len(t),closure_error=checked['closure_error'],
                 curvature_ok=checked['curve_ok'],boundary_ok=checked['boundary_ok'],forward_ok=checked['forward_ok'],
                 converged=converged,feasible=True,stopped_early=not converged,stop_reason=stop,stop_message=message,
                 elapsed_seconds=time.monotonic()-started,max_runtime_s=runtime,plateau_window=window,plateau_percent=percent,
                 algorithm='min_curvature',boundary_mode=boundary_mode,feasibility_iterations=0,
                 curvature_energy=checked['energy'],initial_feasible_curvature_energy=initial_energy,
                 solver='iterative_qp',selected_seed=selected['seed'],seeds=records,
                 footprint_model='oriented_covering_discs',footprint_disc_count=len(offsets),footprint_disc_radius_m=radius,
                 method='Iterative Gauss-Newton QP (OSQP), updated reference normals, multiple seeds, oriented covering discs; no global optimum certificate',vehicle=vehicle)
    return dict(route=route.tolist(),s=out_s.tolist(),curvature=k.tolist(),heading=np.arctan2(v[:,1],v[:,0]).tolist(),
                steering=np.arctan(vehicle['wheelbase']*k).tolist(),metrics=metrics)
