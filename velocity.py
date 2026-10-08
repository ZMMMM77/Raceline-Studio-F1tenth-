"""Closed-loop velocity model matching cedrichld/raceline_UI_f1tenth.
Menger curvature, wrapped box filtering, two forward/backward laps and ratios.
"""
import numpy as np
from scipy.ndimage import uniform_filter1d
from flask import request, jsonify
from planner import PlanningError
from waypoint_edit import points


def calculate(data):
    xy=points(data.get('points'))
    params=data.get('parameters',{})
    defaults=dict(v_min=1.5,v_max=7.6,a_max=6.,a_brake=8.,mu_min=.41,mu_max=.70,width=1.)
    try:p={k:float(params.get(k,v)) for k,v in defaults.items()}
    except (ValueError,TypeError,AttributeError):raise PlanningError('速度参数必须为有效数字。')
    if not all(np.isfinite(v) and 0<v<=100 for v in p.values()) or p['v_min']>p['v_max'] or p['mu_min']>p['mu_max']:
        raise PlanningError('速度、加减速及摩擦系数必须为正数，最小值不能大于最大值。')
    n=len(xy)
    def vector(key,default,low,high):
        try:a=np.asarray(data.get(key,default),dtype=float)
        except (ValueError,TypeError):raise PlanningError(key+' 必须为数值数组。')
        if a.shape!=(n,) or not np.isfinite(a).all() or (a<low).any() or (a>high).any():raise PlanningError(key+' 数量或取值无效。')
        return a
    mu=vector('friction',np.full(n,p['mu_min']),.001,100)
    d= np.roll(xy,-1,axis=0)-xy
    prev=xy-np.roll(xy,1,axis=0)
    ds=np.linalg.norm(d,axis=1)
    denom=np.linalg.norm(prev,axis=1)*ds*np.linalg.norm(d+prev,axis=1)
    cross=prev[:,0]*d[:,1]-prev[:,1]*d[:,0]
    k=np.divide(2*cross,denom,out=np.zeros(n),where=denom>1e-10)
    smooth=uniform_filter1d(abs(k),size=max(3,n//10),mode='wrap')
    v=np.full(n,p['v_max']); mask=smooth>1e-6
    v[mask]=np.minimum(np.sqrt(mu[mask]*9.81/smooth[mask]),p['v_max'])
    v=np.clip(v,p['v_min'],p['v_max'])
    for _ in range(2):
        for i in range(n):v[i]=min(v[i],np.sqrt(v[i-1]**2+2*p['a_max']*ds[i-1]))
    for _ in range(2):
        for i in range(n-1,-1,-1):v[i]=min(v[i],np.sqrt(v[(i+1)%n]**2+2*p['a_brake']*ds[i]))
    ratio=(v-p['v_min'])/(p['v_max']-p['v_min']) if p['v_max']>p['v_min'] else np.ones(n)
    if 'ratio' in data:ratio=vector('ratio',ratio,0,1)
    v=p['v_min']+ratio*(p['v_max']-p['v_min'])
    return dict(points=xy.tolist(),ratio=ratio.tolist(),speed=v.tolist(),friction=mu.tolist(),s=np.r_[0,np.cumsum(ds[:-1])].tolist(),heading=np.arctan2(d[:,1],d[:,0]).tolist(),curvature=k.tolist(),acceleration=((np.roll(v,-1)**2-v**2)/(2*ds)).tolist(),length=float(ds.sum()),lap_time=float(np.sum(ds/np.maximum((v+np.roll(v,-1))/2,.1))),parameters=p)


def install_velocity(app,directory,json_write,pack):
    @app.post('/api/velocity/profile')
    def profile():return jsonify(calculate(request.get_json() or {}))

    @app.post('/api/velocity/export')
    def export():
        r=calculate(request.get_json() or {})
        ident,path=directory('velocity')
        xy=np.asarray(r['points']);p=r['parameters'];n=len(xy)
        meta='; '.join(f'{k}={v}' for k,v in p.items())
        np.savetxt(path/'pure_pursuit.csv',np.c_[xy,r['heading'],r['ratio'],r['friction']],delimiter=',',header=meta+'\nx,y,yaw,speed_ratio,friction',fmt='%.10f')
        np.savetxt(path/'mppi.csv',np.c_[r['s'],xy,r['heading'],r['curvature'],r['speed'],r['acceleration'],np.full((n,2),p['width']),r['friction']],delimiter=';',header=meta+'\ns_m;x_m;y_m;psi_rad;kappa_radpm;vx_mps;ax_mps2;w_tr_right_m;w_tr_left_m;friction',fmt='%.18e')
        np.savetxt(path/'speed_waypoints.csv',np.c_[xy,r['speed'],r['s'],r['heading'],r['curvature'],r['acceleration']],delimiter=',',header='x_m,y_m,vx_mps,s_m,psi_rad,kappa_radpm,ax_mps2',fmt='%.10f')
        from matplotlib.figure import Figure
        from matplotlib.collections import LineCollection
        fig=Figure(figsize=(10,3),facecolor='#131e2c');ax=fig.subplots();ax.set_facecolor('#131e2c')
        q=np.c_[r['s']+[r['length']],r['speed']+[r['speed'][0]]]
        line=LineCollection(np.stack([q[:-1],q[1:]],axis=1),cmap='rainbow_r',linewidth=2)
        # Explicit HSV matches the editor's red -> yellow -> cyan -> blue palette.
        def reference_color(value):
            t=float(np.clip(value,0,1))
            return ((1 if t<.5 else 1-(t-.5)*2)*220/255,(t*2 if t<.5 else 1)*220/255,((t-.7)/.3 if t>.7 else 0)*180/255)
        line.set_color([reference_color(v) for v in r['ratio']]);ax.add_collection(line);ax.set_xlim(0,r['length']);ax.set_ylim(0,p['v_max']*1.1);ax.tick_params(colors='white');ax.set_xlabel('Distance / m',color='white');ax.set_ylabel('Speed / m/s',color='white');fig.tight_layout();fig.savefig(path/'speed_profile.png')
        json_write(path/'report.json',r);pack(path)
        return jsonify(files={k:f'/outputs/{ident}/{f}' for k,f in dict(pp='pure_pursuit.csv',mppi='mppi.csv',speed='speed_waypoints.csv',speed_png='speed_profile.png',zip='results.zip').items()},output_dir=str(path))
