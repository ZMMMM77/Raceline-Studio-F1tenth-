"""Offline closed-track planning. All distances are metres, angles radians.

Optimize periodic cubic-spline control points along fixed reference normals.
Objective: sampled arc length or arc-length-weighted squared curvature.
Constraints: signed spline curvature, forward progress, corridor bounds and
optional raster clearance. Dense post-validation gates successful exports.
"""
import io
import csv
import math
import time
from collections import deque
from dataclasses import dataclass
import numpy as np
import yaml
from PIL import Image
from scipy import ndimage as ndi
from scipy.interpolate import CubicSpline
from scipy.optimize import minimize, OptimizeResult
from scipy.spatial import cKDTree
from skimage.morphology import skeletonize
import networkx as nx


class PlanningError(ValueError):
    pass


def positive(value, name, low=0., high=1e5, inclusive=False):
    try:
        v = float(value)
    except (ValueError, TypeError):
        raise PlanningError(f'请填写{name}。')
    if not np.isfinite(v) or v > high or (v < low if inclusive else v <= low):
        raise PlanningError(f'{name}不在允许范围内。')
    return v


def vehicle_parameters(d):
    if d.get('reference') != 'rear':
        raise PlanningError('当前 Ackermann 模型以后轴中心为路径参考点，请先确认车辆坐标。')
    wheelbase = positive(d.get('wheelbase'), '轴距', high=10)
    if d.get('limit_mode') == 'radius':
        radius = positive(d.get('radius'), '最小转弯半径', high=10000)
        angle = math.atan(wheelbase / radius)
    else:
        angle = math.radians(positive(d.get('steer'), '最大前轮转角', high=75))
        radius = wheelbase / math.tan(angle)
        if d.get('angle_type') == 'inner':
            radius += positive(d.get('wheel_track'), '前轮轮距', high=10) / 2
            angle = math.atan(wheelbase / radius)
    width = positive(d.get('car_width'), '车宽', high=10)
    length = positive(d.get('car_length'), '车长', high=20)
    if length < wheelbase:
        raise PlanningError('车长应不小于轴距，请确认单位为米。')
    rear = positive(d.get('rear_overhang'), '后轴至车尾距离', low=0, high=length, inclusive=True)
    if rear + wheelbase > length:
        raise PlanningError('后轴至车尾距离＋轴距不能大于车长。')
    extent = max(rear, length-rear)
    body_radius = math.hypot(extent, width/2)
    margin = positive(d.get('margin'), '额外余量', low=0, high=5, inclusive=True)
    return dict(wheelbase=wheelbase, effective_steer=angle, curvature_limit=1/radius,
                radius=radius, body_radius=body_radius, margin=margin,
                clearance=body_radius+margin, **{k:d.get(k) for k in ('reference','car_width','car_length','rear_overhang','angle_type','wheel_track')})


def clean_loop(points, widths=None):
    p = np.asarray(points, dtype=float)
    if p.ndim != 2 or p.shape[1] != 2 or len(p) < 12 or not np.isfinite(p).all():
        raise PlanningError('路线需要至少 12 个有效的有序 x、y 坐标点。')
    keep = np.r_[True, np.linalg.norm(np.diff(p,axis=0),axis=1)>1e-7]
    p = p[keep]
    w = np.asarray(widths, dtype=float)[keep] if widths is not None else None
    if np.linalg.norm(p[-1]-p[0]) < 1e-6:
        p = p[:-1]
        if w is not None: w = w[:-1]
    ds = np.linalg.norm(np.roll(p,-1,axis=0)-p,axis=1)
    if len(p)<12 or np.min(ds)<1e-7: raise PlanningError('有效路径点不足或存在重复点。')
    if ds[-1] > max(np.median(ds)*8,2.0):
        raise PlanningError('输入路径不像完整闭环：末点到起点距离过大。请提供按行驶顺序排列的一整圈。')
    if w is not None and (not np.isfinite(w).all() or np.any(w<=0)):
        raise PlanningError('左右宽度必须为正数，单位为米。')
    return p,w


def parse_csv(content, file_format="auto"):
    text=content.decode('utf-8-sig')
    lines=[s.strip() for s in text.splitlines() if s.strip()]
    if not lines: raise PlanningError('CSV 文件为空。')
    comments=[s.lstrip('# ').lower() for s in lines if s.startswith('#')]
    data=[s for s in lines if not s.startswith('#')]
    if not data: raise PlanningError('CSV 没有数值数据。')
    delim=';' if data[0].count(';')>data[0].count(',') else ','
    rows=list(csv.reader(data,delimiter=delim))
    try: float(rows[0][0]); header=None
    except ValueError: header=[c.strip().lower() for c in rows.pop(0)]
    if header is None:
        for s in reversed(comments):
            fields=[c.strip() for c in s.split(delim)]
            if ('x_m' in fields and 'y_m' in fields) or ('x' in fields and 'y' in fields):header=fields;break
    try: a=np.array([[float(c.strip()) for c in r] for r in rows],dtype=float)
    except (ValueError, TypeError): raise PlanningError('CSV 有无法读取的数值行或列数不一致。')
    if a.ndim!=2 or a.shape[1]<2 or not np.isfinite(a).all(): raise PlanningError('CSV 至少需要两列有限数值。')
    path_only=False
    if file_format == 'pure_pursuit':
        if a.shape[1] not in (4,5): raise PlanningError('Pure Pursuit 需要 4 或 5 列：x,y,yaw,speed[,friction]。')
        p,w,path_only=a[:,:2],None,True
    elif file_format == 'mppi':
        if a.shape[1] not in (9,10): raise PlanningError('MPPI 需要 9 或 10 列。')
        p,w,path_only=a[:,1:3],None,True
    elif file_format == 'xy_widths':
        if a.shape[1]!=4:raise PlanningError('中心线宽度格式需要四列 x,y,右宽,左宽。')
        p,w=a[:,:2],a[:,2:4]
    elif file_format != 'auto': raise PlanningError('未知 CSV 格式。')
    elif header and 'x' in header and 'y' in header:
        p,w,path_only=a[:,[header.index('x'),header.index('y')]],None,True
    elif header and 'x_m' in header and 'y_m' in header:
        p=a[:,[header.index('x_m'),header.index('y_m')]]
        if 'w_tr_right_m' in header and 'w_tr_left_m' in header:
            w=a[:,[header.index('w_tr_right_m'),header.index('w_tr_left_m')]]
        else: w=None; path_only=True
    elif a.shape[1]==4: p,w=a[:,:2],a[:,2:4]
    elif a.shape[1]==2: p,w=a,None
    elif a.shape[1]==7: p,w=a[:,1:3],None; path_only=True
    else: raise PlanningError('列含义不明确。请使用 x_m,y_m,w_tr_right_m,w_tr_left_m 表头，或两列 x,y。')
    p,w=clean_loop(p,w)
    return p,w,path_only


def arc(p):
    ds=np.linalg.norm(np.roll(p,-1,axis=0)-p,axis=1)
    return np.r_[0,np.cumsum(ds)],float(ds.sum())


def plan_speed_profile(s, curvature, total_length, base_speed, lateral_accel, acceleration, braking):
    """Plan a periodic waypoint speed profile from curvature and acceleration limits.

    The lateral limit is v²|kappa| <= a_y. Forward and backward sweeps make
    every edge reachable by acceleration and braking, including the last-to-first
    edge of a closed track. Parameters are measured/selected by the user.
    """
    base=positive(base_speed,'直道基准速度',high=100)
    ay=positive(lateral_accel,'允许横向加速度',high=100)
    ax=positive(acceleration,'最大加速度',high=100)
    brake=positive(braking,'最大制动减速度',high=100)
    s=np.asarray(s,dtype=float);k=np.asarray(curvature,dtype=float)
    if s.ndim!=1 or k.shape!=s.shape or len(s)<3 or not np.isfinite(s).all() or not np.isfinite(k).all():
        raise PlanningError('速度规划需要至少三个有效的路线点及曲率。')
    if abs(s[0])>1e-6 or np.any(np.diff(s)<=0) or not np.isfinite(total_length) or total_length<=s[-1]:
        raise PlanningError('路线弧长无效，无法规划闭环速度。')
    ds=np.diff(np.r_[s,total_length])
    cap=np.minimum(base,np.sqrt(ay/np.maximum(np.abs(k),1e-12)))
    speed=cap.copy();n=len(speed)
    # Two full laps per direction propagate the tightest corner constraint
    # across the seam regardless of where the CSV starts.
    for _ in range(2*n):
        i=_ % n;j=(i+1)%n
        speed[j]=min(speed[j],math.sqrt(speed[i]**2+2*ax*ds[i]))
    for _ in range(2*n):
        i=(n-1-_)%n;j=(i+1)%n
        speed[i]=min(speed[i],math.sqrt(speed[j]**2+2*brake*ds[i]))
    # Closing the loop after the backward pass may lower an upstream point;
    # repeat the forward sweep and check both constraints explicitly.
    for _ in range(2*n):
        i=_ % n;j=(i+1)%n
        speed[j]=min(speed[j],math.sqrt(speed[i]**2+2*ax*ds[i]))
    for _ in range(2*n):
        i=(n-1-_)%n;j=(i+1)%n
        speed[i]=min(speed[i],math.sqrt(speed[j]**2+2*brake*ds[i]))
    next_speed=np.roll(speed,-1)
    segment_accel=(next_speed**2-speed**2)/(2*ds)
    if np.any(segment_accel>ax+1e-8) or np.any(segment_accel< -brake-1e-8):
        raise PlanningError('闭环速度约束未收敛，请检查路线与参数。')
    return dict(speed=speed,acceleration=segment_accel,corner_limit=cap,
                metrics=dict(base_speed=base,lateral_accel=ay,acceleration_limit=ax,
                             braking_limit=brake,min_speed=float(speed.min()),
                             max_speed=float(speed.max()),
                             estimated_lap_time=float(np.sum(2*ds/np.maximum(speed+next_speed,1e-9))),
                             limited_points=int(np.count_nonzero(speed<base-1e-6))))


def route_geometry(points):
    """Estimate curvature while preserving every imported waypoint coordinate."""
    p,_=clean_loop(points)
    s,total=arc(p)
    spline=CubicSpline(s,np.vstack([p,p[0]]),bc_type='periodic')
    deriv=spline(s[:-1],1);second=spline(s[:-1],2)
    curvature=(deriv[:,0]*second[:,1]-deriv[:,1]*second[:,0])/np.maximum(np.linalg.norm(deriv,axis=1)**3,1e-12)
    heading=np.arctan2(deriv[:,1],deriv[:,0])
    return dict(route=p.tolist(),s=s[:-1].tolist(),curvature=curvature.tolist(),
                heading=heading.tolist(),metrics={'length':total})


def resample(p,w=None,count=None,spacing=.2,smooth=0.):
    s,total=arc(p)
    count=count or max(30,int(np.ceil(total/spacing)))
    q=np.linspace(0,total,count,endpoint=False)
    out=np.column_stack([np.interp(q,s,np.r_[p[:,j],p[0,j]]) for j in (0,1)])
    if smooth: out=ndi.gaussian_filter1d(out,smooth/(total/count),axis=0,mode='wrap')
    widths=None if w is None else np.column_stack([np.interp(q,s,np.r_[w[:,j],w[0,j]]) for j in (0,1)])
    return out,widths


def normals(p):
    d=np.roll(p,-1,axis=0)-np.roll(p,1,axis=0)
    d/=np.maximum(np.linalg.norm(d,axis=1)[:,None],1e-10)
    return np.c_[d[:,1],-d[:,0]]


@dataclass
class MapData:
    image: Image.Image
    resolution: float
    origin: np.ndarray
    free: np.ndarray
    sdf: np.ndarray
    rotation: np.ndarray
    extraction_free: object = None
    cleanup_info: object = None

    @classmethod
    def read(cls,image_bytes,yaml_bytes):
        try:
            metadata=yaml.safe_load(yaml_bytes)
            res=positive(metadata['resolution'],'地图分辨率',high=10)
            origin=np.asarray(metadata['origin'],float)
            if origin.shape!=(3,) or not np.isfinite(origin).all(): raise ValueError()
            image=Image.open(io.BytesIO(image_bytes)).convert('L')
            if max(image.size)>6000 or image.width*image.height>20_000_000: raise PlanningError('地图太大，请先缩小至 6000 像素以内并更新分辨率。')
            gray=np.asarray(image)/255.
            occ=gray if int(metadata.get('negate',0)) else 1-gray
            free_thresh=float(metadata.get('free_thresh',.196))
            occupied_thresh=float(metadata.get('occupied_thresh',.65))
            if not 0<free_thresh<occupied_thresh<1: raise ValueError()
            free=occ<free_thresh
            # Image border and unknown/ambiguous pixels are non-drivable.
            free[[0,-1],:]=False;free[:,[0,-1]]=False
            sdf=(ndi.distance_transform_edt(free)-ndi.distance_transform_edt(~free))*res
            c,s=np.cos(origin[2]),np.sin(origin[2])
            return cls(image,res,origin,free,sdf,np.array([[c,-s],[s,c]]))
        except PlanningError: raise
        except Exception as e: raise PlanningError('无法读取地图或 YAML，请检查 image、resolution、origin 和阈值。') from e

    def to_pixel(self,p):
        q=(np.asarray(p)-self.origin[:2])@self.rotation/self.resolution
        return np.c_[self.image.height-.5-q[:,1],q[:,0]-.5]

    def to_world(self,pix):
        p=np.asarray(pix)
        xy=np.c_[p[:,1]+.5,self.image.height-p[:,0]-.5]*self.resolution
        return xy@self.rotation.T+self.origin[:2]

    def distance(self,p,gradient=False):
        pix=self.to_pixel(p);r,c=pix[:,0],pix[:,1]
        r0=np.floor(r).astype(int);c0=np.floor(c).astype(int)
        valid=(r0>=0)&(r0<self.image.height-1)&(c0>=0)&(c0<self.image.width-1)
        r0=np.clip(r0,0,self.image.height-2);c0=np.clip(c0,0,self.image.width-2)
        fr=np.clip(r-r0,0,1);fc=np.clip(c-c0,0,1)
        a,b=self.sdf[r0,c0],self.sdf[r0,c0+1];cc,d=self.sdf[r0+1,c0],self.sdf[r0+1,c0+1]
        value=(1-fr)*((1-fc)*a+fc*b)+fr*((1-fc)*cc+fc*d)
        # Deduct pixel-center uncertainty conservatively.
        value-=self.resolution*math.sqrt(2)
        value[~valid]=-100
        if not gradient:return value
        dc=(1-fr)*(b-a)+fr*(d-cc);dr=(1-fc)*(cc-a)+fc*(d-b)
        grad=np.c_[dc,-dr]/self.resolution@self.rotation.T
        grad[~valid]=0
        return value,grad

    def widths(self,p,cap=True):
        n=normals(p)
        if np.any(self.distance(p)<0):raise PlanningError('参考线有点落在障碍物或未知区域。请确认地图与 CSV 的坐标一致。')
        out=[]
        max_dist=min(100,max(self.image.size)*self.resolution)
        step=max(self.resolution/2,.01)
        for sign in (1,-1):
            result=np.zeros(len(p));active=np.ones(len(p),bool)
            for dist in np.arange(step,max_dist,step):
                ids=np.flatnonzero(active)
                if not len(ids):break
                pts=p[ids]+sign*dist*n[ids]
                good=self.distance(pts)>0
                result[ids[good]]=dist
                active[ids[~good]]=False
            out.append(result)
        result=np.column_stack(out)
        # At a tight apex a normal ray can run longitudinally down another part
        # of the same corridor. A local cap prevents ill-defined cross-sections.
        # This only narrows the measured corridor, never invents free space.
        if cap:result=np.minimum(result,2*self.distance(p)[:,None])
        if np.any(result<step):raise PlanningError('路径过于接近地图边界，无法提取有效赛道宽度。')
        return result

    def prepare_extraction(self,enabled=True,hole_area=.01,gap_radius=.05):
        """Clean a separate topology mask; original free/sdf/image stay authoritative."""
        hole_area=positive(hole_area,'提取副本的小孔面积',low=0,high=.1,inclusive=True)
        gap_radius=positive(gap_radius,'提取副本的补缝半径',low=0,high=.15,inclusive=True)
        mask=self.free.copy()
        filled=closed=0
        if enabled:
            holes=ndi.binary_fill_holes(mask)&~mask
            labels,_=ndi.label(holes)
            sizes=np.bincount(labels.ravel());small=sizes*self.resolution**2<=hole_area+1e-12
            small[0]=False
            fill=small[labels];mask[fill]=True;filled=int(fill.sum())
            if gap_radius>0:
                radius=min(8,int(np.floor(gap_radius/self.resolution+1e-9)))
                if radius:
                    yy,xx=np.mgrid[-radius:radius+1,-radius:radius+1]
                    structure=xx*xx+yy*yy<=radius*radius
                    blocked=ndi.binary_closing(~mask,structure=structure,border_value=1)
                    close=blocked&mask;closed=int(close.sum());mask[close]=False
        mask[[0,-1],:]=False;mask[:,[0,-1]]=False
        self.extraction_free=mask
        self.cleanup_info=dict(enabled=bool(enabled),hole_area_m2=hole_area,gap_radius_m=gap_radius,
                               filled_hole_pixels=filled,closed_free_pixels=closed,
                               authority='original raster only; cleaned mask is for reference extraction')
        return mask

    def extract(self,cleanup=True,hole_area=.01,gap_radius=.05):
        extraction=self.prepare_extraction(cleanup,hole_area,gap_radius)
        labels,num=ndi.label(extraction)
        objects=ndi.find_objects(labels)
        candidates=[]
        for label,sl in enumerate(objects,1):
            if sl is None:continue
            # Exclude the unbounded exterior component.
            if sl[0].start<=1 or sl[1].start<=1 or sl[0].stop>=self.image.height-1 or sl[1].stop>=self.image.width-1:continue
            component=labels[sl]==label
            if component.sum()<200:continue
            hole=ndi.binary_fill_holes(component)&~component
            if hole.sum()>100:candidates.append((int(hole.sum()),label))
        candidates.sort(reverse=True)
        if not candidates:raise PlanningError('没有找到封闭的环形赛道。请检查墙壁缺口、未知区域；也可改用有序 CSV 指定路线。')
        if len(candidates)>1 and candidates[1][0]>.1*candidates[0][0]:raise PlanningError('地图包含多条独立闭环，无法确定目标赛道。请裁剪目标赛道并更新 YAML，或导入中心线 CSV。')
        mask=labels==candidates[0][1]
        skel=skeletonize(mask)
        coords=np.argwhere(skel);lookup={tuple(v):i for i,v in enumerate(coords)}
        g=nx.Graph();g.add_nodes_from(range(len(coords)))
        for i,(r,c) in enumerate(coords):
            for dr,dc in ((0,1),(1,0),(1,1),(1,-1)):
                j=lookup.get((r+dr,c+dc))
                if j is None:continue
                if dr and dc and ((r+dr,c) in lookup or (r,c+dc) in lookup):continue
                g.add_edge(i,j)
        core=nx.k_core(g,2)
        cycles=[x for x in nx.cycle_basis(core) if len(x)>30]
        if not cycles:raise PlanningError('骨架没有形成有效闭环，请检查地图边界是否闭合。')
        cycles.sort(key=len,reverse=True)
        if len(cycles)>1 and len(cycles[1])>.2*len(cycles[0]):raise PlanningError('赛道存在多个大闭环或岔路，请使用中心线 CSV 指定绕行路线。')
        p=self.to_world(coords[cycles[0]])
        # Deterministic CCW default and nearest-to-origin start.
        area=np.sum(p[:,0]*np.roll(p[:,1],-1)-p[:,1]*np.roll(p[:,0],-1))
        if area<0:p=p[::-1]
        p=np.roll(p,-np.argmin(np.linalg.norm(p,axis=1)),axis=0)
        p,_=resample(p,spacing=.2,smooth=.28)
        if np.any(self.distance(p)<0):raise PlanningError('提取的中心线穿过障碍物，需改善地图或提供参考 CSV。')
        return p,self.widths(p,cap=False)


def has_crossing(p):
    # Filter segment-pair candidates by midpoint distance, then exact crossings.
    q=np.roll(p,-1,axis=0);mid=(p+q)/2
    lengths=np.linalg.norm(q-p,axis=1)
    pairs=np.array(list(cKDTree(mid).query_pairs(float(np.max(lengths))+1e-9)),dtype=int)
    if pairs.size==0:return False
    i,j=pairs[:,0],pairs[:,1];keep=(j-i>1)&~((i==0)&(j==len(p)-1));i,j=i[keep],j[keep]
    cross=lambda a,b:a[:,0]*b[:,1]-a[:,1]*b[:,0]
    a,b,c,d=p[i],q[i],p[j],q[j]
    return bool(np.any((cross(b-a,c-a)*cross(b-a,d-a)<-1e-12)&(cross(d-c,a-c)*cross(d-c,b-c)<-1e-12)))


class SplineProblem:
    def __init__(self,center,widths,map_data,vehicle,nodes,algorithm="shortest"):
        if algorithm not in ("shortest","min_curvature"):raise PlanningError("未知路线算法。")
        self.algorithm=algorithm
        self.p,self.w=resample(center,widths,count=nodes)
        self.map_only=bool(map_data is not None and vehicle.get('boundary_mode')=='map')
        if self.map_only:self.w=map_data.widths(self.p,cap=False)
        self.n=normals(self.p);self.s,self.total=arc(self.p)
        self.vehicle=vehicle;self.map=map_data
        self.base=CubicSpline(self.s,np.vstack([self.p,self.p[0]]),bc_type='periodic')
        ident=np.eye(nodes)
        self.basis=CubicSpline(self.s,np.vstack([ident,ident[0]]),bc_type='periodic')
        bt=np.linspace(0,self.total,max(nodes*30,int(self.total/.03)),endpoint=False)
        bp=self.base(bt);bv=self.base(bt,1);bn=np.c_[bv[:,1],-bv[:,0]]/np.linalg.norm(bv,axis=1)[:,None]
        bw=np.column_stack([np.interp(bt,self.s,np.r_[self.w[:,j],self.w[0,j]]) for j in (0,1)])
        br=bp+bn*bw[:,0,None];bl=bp-bn*bw[:,1,None]
        self.boundary=np.vstack([br,bl]);self.boundary_tree=cKDTree(self.boundary)
        self.boundary_deduction=max(np.linalg.norm(np.roll(br,-1,axis=0)-br,axis=1).max(),np.linalg.norm(np.roll(bl,-1,axis=0)-bl,axis=1).max())/2
        self.last=None

    def setup(self,samples):
        self.t=np.unique(np.r_[np.linspace(0,self.total,samples,endpoint=False),self.s[:-1]])
        dt=np.diff(np.r_[self.t,self.total])
        self.weights=(dt+np.roll(dt,1))/2
        self.b=[self.basis(self.t,i) for i in range(3)]
        self.xy=[self.base(self.t,i) for i in range(3)]
        self.mx=[b*self.n[:,0] for b in self.b];self.my=[b*self.n[:,1] for b in self.b]
        self.tangent=self.xy[1]/np.linalg.norm(self.xy[1],axis=1)[:,None]
        self.normal=np.c_[self.tangent[:,1],-self.tangent[:,0]]
        self.width=np.column_stack([np.interp(self.t,self.s,np.r_[self.w[:,j],self.w[0,j]]) for j in (0,1)])
        self.lat=self.mx[0]*self.normal[:,0,None]+self.my[0]*self.normal[:,1,None]
        self.last=None

    def evaluate(self,a):
        if self.last is not None and np.array_equal(a,self.last[0]):return self.last[1]
        pos=np.c_[self.xy[0][:,0]+self.mx[0]@a,self.xy[0][:,1]+self.my[0]@a]
        dx=self.xy[1][:,0]+self.mx[1]@a;dy=self.xy[1][:,1]+self.my[1]@a
        ddx=self.xy[2][:,0]+self.mx[2]@a;ddy=self.xy[2][:,1]+self.my[2]@a
        speed2=np.maximum(dx*dx+dy*dy,1e-12)
        numerator=dx*ddy-dy*ddx;k=numerator/speed2**1.5
        dk=(self.mx[1]*ddy[:,None]+self.my[2]*dx[:,None]-self.my[1]*ddx[:,None]-self.mx[2]*dy[:,None])/speed2[:,None]**1.5
        dk-=3*k[:,None]*(dx[:,None]*self.mx[1]+dy[:,None]*self.my[1])/speed2[:,None]
        forward=dx*self.tangent[:,0]+dy*self.tangent[:,1]
        df=self.mx[1]*self.tangent[:,0,None]+self.my[1]*self.tangent[:,1,None]
        clearance=self.vehicle['clearance']+.025;limit=self.vehicle['curvature_limit']*.997
        lat=self.lat@a
        # Normal displacement bounds at spline samples, not only control points.
        vals=[limit-k,limit+k,forward-.2]
        jacs=[-dk,dk,df]
        if not self.map_only:
            vals.extend([self.width[:,0]-clearance-lat,self.width[:,1]-clearance+lat])
            jacs.extend([-self.lat,self.lat])
            distance,indices=self.boundary_tree.query(pos)
            grad=(pos-self.boundary[indices])/np.maximum(distance[:,None],1e-10)
            vals.append(distance-self.boundary_deduction-clearance)
            jacs.append(grad[:,0,None]*self.mx[0]+grad[:,1,None]*self.my[0])
        if self.map:
            distance,grad=self.map.distance(pos,True)
            vals.append(distance-clearance)
            jacs.append(grad[:,0,None]*self.mx[0]+grad[:,1,None]*self.my[0])
        result=(np.concatenate(vals),np.vstack(jacs),pos,k)
        self.last=(a.copy(),result)
        return result

    def objective(self,a):
        values,jac,pos,k=self.evaluate(a)
        if self.algorithm=='min_curvature':
            # Periodic trapezoidal quadrature of kappa^2 |r'(t)| dt.
            # Include the changing arc measure in the analytic gradient.
            dx=self.xy[1][:,0]+self.mx[1]@a
            dy=self.xy[1][:,1]+self.my[1]@a
            speed=np.sqrt(np.maximum(dx*dx+dy*dy,1e-12))
            dk=-jac[:len(k)]
            dspeed=(dx[:,None]*self.mx[1]+dy[:,None]*self.my[1])/speed[:,None]
            grad=self.weights@(2*k[:,None]*dk*speed[:,None]+k[:,None]**2*dspeed)
            return float(self.weights@(k*k*speed)),grad
        d=np.roll(pos,-1,axis=0)-pos
        lengths=np.maximum(np.linalg.norm(d,axis=1),1e-10);unit=d/lengths[:,None]
        gradp=np.roll(unit,1,axis=0)-unit
        grad=self.mx[0].T@gradp[:,0]+self.my[0].T@gradp[:,1]
        return lengths.sum(),grad

    def spline(self,a):return CubicSpline(self.s,np.vstack([self.p+a[:,None]*self.n,self.p[0]+a[0]*self.n[0]]),bc_type='periodic')

    def bounds(self):
        # Map rays restrict the search domain only; the original SDF enforces
        # the footprint everywhere. Ray endpoints are never connected into walls.
        inset=0. if self.map_only else self.vehicle['clearance']
        return list(zip(-self.w[:,1]+inset,self.w[:,0]-inset))


def optimization_limits(parameters):
    runtime=positive(parameters.get('max_runtime_s',300),'最大求解时间',low=1,high=3600,inclusive=True)
    window=positive(parameters.get('plateau_window',50),'停滞检查窗口',low=5,high=400,inclusive=True)
    if window!=int(window):raise PlanningError('停滞检查窗口必须是整数。')
    percent=positive(parameters.get('plateau_percent',.1),'最小改善百分比',low=0,high=5,inclusive=True)
    return runtime,int(window),percent


class _OptimizationStop(Exception):
    def __init__(self,reason):
        self.reason=reason
        super().__init__(reason)


def _validate_candidate(problem,x,spacing):
    """Use the same dense physical checks for normal and early termination."""
    vehicle=problem.vehicle
    spline=problem.spline(x)
    ncheck=max(len(x)*30,int(np.ceil(problem.total/min(.03,spacing/3))))
    t=np.linspace(0,problem.total,ncheck,endpoint=False)
    pp=spline(t);v=spline(t,1);acc=spline(t,2)
    k=(v[:,0]*acc[:,1]-v[:,1]*acc[:,0])/np.maximum(np.linalg.norm(v,axis=1)**3,1e-12)
    ref=problem.base(t);rv=problem.base(t,1)
    tangent=rv/np.maximum(np.linalg.norm(rv,axis=1)[:,None],1e-12)
    rn=np.c_[tangent[:,1],-tangent[:,0]]
    widths_dense=np.column_stack([np.interp(t,problem.s,np.r_[problem.w[:,j],problem.w[0,j]]) for j in (0,1)])
    lat=np.sum((pp-ref)*rn,axis=1)
    corridor=np.minimum(widths_dense[:,0]-lat,widths_dense[:,1]+lat)
    boundary_r=ref+rn*widths_dense[:,0,None];boundary_l=ref-rn*widths_dense[:,1,None]
    boundary=np.vstack([boundary_r,boundary_l])
    bound_gap=max(np.max(np.linalg.norm(np.roll(boundary_r,-1,axis=0)-boundary_r,axis=1)),np.max(np.linalg.norm(np.roll(boundary_l,-1,axis=0)-boundary_l,axis=1)))
    geom_clearance=cKDTree(boundary).query(pp)[0]-bound_gap/2
    map_clearance=problem.map.distance(pp) if problem.map else np.full(len(pp),np.inf)
    if problem.map_only:
        geom_clearance=np.full(len(pp),np.inf)
        corridor=np.full(len(pp),np.inf)
    dsmax=float(np.max(np.linalg.norm(np.roll(pp,-1,axis=0)-pp,axis=1)))
    min_clearance=float(min(geom_clearance.min(),map_clearance.min()))
    finite=bool(np.isfinite(pp).all() and np.isfinite(v).all() and np.isfinite(k).all())
    curve_ok=finite and bool(np.max(np.abs(k))<=vehicle['curvature_limit']+1e-5)
    boundary_ok=finite and bool(corridor.min()>=vehicle['clearance']-1e-4 and min_clearance-dsmax/2>=vehicle['clearance']-1e-4)
    forward_ok=finite and bool(np.min(np.sum(v*tangent,axis=1))>=.2-1e-4)
    closure_error=float(np.linalg.norm(spline(0)-spline(problem.total)))
    crossing=has_crossing(pp) if finite else True
    valid=bool(curve_ok and boundary_ok and forward_ok and not crossing and closure_error<=1e-8)
    return dict(valid=valid,spline=spline,t=t,pp=pp,k=k,curve_ok=curve_ok,
                boundary_ok=boundary_ok,forward_ok=forward_ok,min_clearance=min_clearance,
                closure_error=closure_error)


def optimize(center,widths,map_data,parameters,progress=lambda *a:None):
    vehicle=vehicle_parameters(parameters)
    boundary_mode=parameters.get('boundary_mode','csv')
    if boundary_mode not in ('map','csv'):raise PlanningError('未知边界约束来源。')
    if boundary_mode=='map' and map_data is None:raise PlanningError('原始地图约束需要匹配的图片与 YAML。')
    vehicle['boundary_mode']=boundary_mode
    runtime,window,percent=optimization_limits(parameters)
    started=time.monotonic()
    nodes=int(parameters.get('nodes',140))
    if nodes not in (80,140,220):raise PlanningError('请选择 80、140 或 220 个优化控制点。')
    spacing=positive(parameters.get('spacing',.1),'导出间距',low=.019,high=1)
    if boundary_mode=='csv' and np.min(np.sum(widths,axis=1))<=2*vehicle['clearance']:
        raise PlanningError(f'局部双侧赛道总宽度不足 {2*vehicle["clearance"]:.3f} m（两倍整车包络＋余量）。请确认车辆尺寸或赛道宽度。')
    algorithm=parameters.get('algorithm','shortest')
    iteration=0

    def run_stage(problem,initial,maxiter,label,allow_plateau=True,feasibility=False):
        # Reset the rolling best-objective history whenever the sample grid changes.
        history=deque(maxlen=window+1)
        last=initial.copy();best=None;best_value=float('inf')
        def check_time():
            if time.monotonic()-started>=runtime:raise _OptimizationStop('time_limit')
        def objective(a):
            check_time()
            if feasibility:
                # Phase I seeks a small displacement satisfying the constraints;
                # curvature energy is optimized only after a feasible seed exists.
                return float(np.dot(a,a)/len(a)),2*a/len(a)
            return problem.objective(a)
        def constraints(a):
            check_time()
            return problem.evaluate(a)[0]
        def constraint_jac(a):
            check_time()
            return problem.evaluate(a)[1]
        def callback(a):
            nonlocal iteration,last,best,best_value
            last=a.copy();iteration+=1
            check_time()
            value=float(problem.objective(a)[0])
            sampled_feasible=bool(np.isfinite(value) and np.min(problem.evaluate(a)[0])>=-1e-6)
            if sampled_feasible:
                if value<best_value:best_value=value;best=a.copy()
                history.append(best_value)
                if feasibility:raise _OptimizationStop('feasible_seed')
            else:
                # Flat but infeasible iterates do not satisfy the quality stop rule.
                history.clear()
            if iteration%5==0:
                name,unit=('曲率平方积分','m⁻¹') if algorithm=='min_curvature' else ('路程','m')
                progress(iteration,f'{label} · 第 {iteration} 次迭代 · {name} {value:.5f} {unit} · 已用 {time.monotonic()-started:.0f}/{runtime:g} 秒')
            if allow_plateau and percent>0 and len(history)==window+1:
                improvement=(history[0]-history[-1])/max(abs(history[0]),1e-12)
                if improvement<percent/100:raise _OptimizationStop('plateau')
        try:
            result=minimize(objective,initial,jac=True,method='SLSQP',
                bounds=problem.bounds(),
                constraints={'type':'ineq','fun':constraints,'jac':constraint_jac},callback=callback,
                options={'maxiter':maxiter,'ftol':1e-7 if algorithm=='min_curvature' else 1e-8,'disp':False})
            return result,None
        except _OptimizationStop as stopped:
            # Never retain an objective/constraint trial point as an accepted iterate.
            chosen=best.copy() if best is not None else last.copy()
            return OptimizeResult(x=chosen,success=False,message=stopped.reason,last_x=last),stopped.reason

    problem=SplineProblem(center,widths,map_data,vehicle,nodes,algorithm)
    x=np.zeros(nodes)
    feasibility_iterations=0
    if algorithm=='min_curvature' and nodes>80:
        progress(iteration,'最小曲率优化 · 正在生成粗网格初值（计入求解时限）')
        coarse=SplineProblem(center,widths,map_data,vehicle,80,algorithm)
        coarse.setup(320)
        seed,_=run_stage(coarse,np.zeros(80),300,'粗网格初值',allow_plateau=False,feasibility=boundary_mode=='map')
        if boundary_mode=='map':feasibility_iterations=iteration
        if np.isfinite(seed.x).all():
            x=np.interp(problem.s[:-1]/problem.total,coarse.s/coarse.total,np.r_[seed.x,seed.x[0]])
            bounds=np.asarray(problem.bounds())
            x=np.clip(x,bounds[:,0],bounds[:,1])

    stop_reason=None;checked=None;feasible_backup=None
    stop_labels={'time_limit':f'达到最大求解时间 {runtime:g} 秒',
                 'plateau':f'同一精度阶段连续 {window} 次迭代改善不足 {percent:g}%',
                 'feasible_fallback':'后续优化未通过，保留此前通过加密检查的可行路线'}
    for refinement in range(3):
        problem.setup(nodes*(4*2**refinement))
        label=f'第 {refinement+1}/3 轮约束检查'
        if boundary_mode=='map' and time.monotonic()-started<runtime:
            progress(iteration,f'阶段一：修复可行性 · {label}')
            before=iteration
            if np.min(problem.evaluate(x)[0])<-1e-6:
                repaired,repair_stop=run_stage(problem,x,150,label+' · 可行性修复',allow_plateau=False,feasibility=True)
                x=repaired.x
            feasibility_iterations+=iteration-before
            preliminary=_validate_candidate(problem,x,spacing)
            if preliminary['valid']:feasible_backup=(x.copy(),preliminary)
            elif time.monotonic()-started<runtime:
                # Add denser constraints before asking for a smoother route.
                if refinement<2:continue
                if feasible_backup is not None:
                    x,checked=feasible_backup
                    stop_reason='feasible_fallback'
                    result=OptimizeResult(x=x,success=False,message=stop_reason)
                    break
                raise PlanningError('阶段一未找到通过加密检查的可行路线。请检查地图净空、车辆尺寸或参考 CSV；这不是对赛道不可通行的证明。')
        progress(iteration,f'优化中 · {label}')
        result,stop_reason=run_stage(problem,x,400 if algorithm=='min_curvature' else 150,label)
        x=result.x
        progress(iteration,(stop_labels[stop_reason] if stop_reason else '本轮求解结束')+'；正在进行加密约束检查…')
        checked=_validate_candidate(problem,x,spacing)
        # The lowest sampled objective may fail dense checks; try the last accepted
        # iterate as well before discarding an early-stopped stage.
        if stop_reason and not checked['valid'] and not np.array_equal(result.last_x,x):
            alternate=_validate_candidate(problem,result.last_x,spacing)
            if alternate['valid']:
                x=result.last_x;checked=alternate
        if checked['valid'] and (result.success or stop_reason):break
        if stop_reason=='time_limit':break
        # Plateau on a coarse constraint grid is not permission to skip validation.
        # If it fails, refine the grid and start a fresh improvement window.
    if (not checked['valid'] or (not result.success and stop_reason is None)) and feasible_backup is not None:
        x,checked=feasible_backup
        stop_reason='time_limit' if stop_reason=='time_limit' else 'feasible_fallback'
        result.success=False
    if not checked['valid']:
        if stop_reason:
            raise PlanningError(stop_labels[stop_reason]+'，但候选路线未通过加密约束检查，未导出路线。请检查车辆参数、赛道宽度或提高计算精度。')
        if not result.success:
            raise PlanningError(f'优化器尚未收敛（{result.message}）。没有导出成功路线。')
        raise PlanningError('加密检查未通过（曲率、边界距离、前进方向或闭环自交），未导出路线。')
    if not result.success and stop_reason is None:
        raise PlanningError(f'优化器尚未收敛（{result.message}）。没有导出成功路线。')

    spline=checked['spline'];t=checked['t'];pp=checked['pp'];k=checked['k']
    dense_s,total=arc(pp)
    out_s=np.linspace(0,total,max(20,int(np.ceil(total/spacing))),endpoint=False)
    out_t=np.interp(out_s,dense_s,np.r_[t,problem.total])
    route=spline(out_t);v=spline(out_t,1);acc=spline(out_t,2)
    ko=(v[:,0]*acc[:,1]-v[:,1]*acc[:,0])/np.linalg.norm(v,axis=1)**3
    heading=np.arctan2(v[:,1],v[:,0])
    metrics={'length':total,'center_length':arc(center)[1],'saved':arc(center)[1]-total,
             'max_curvature':float(np.max(np.abs(k))),'curvature_limit':vehicle['curvature_limit'],
             'min_clearance':checked['min_clearance'],'required_clearance':vehicle['clearance'],
             'iterations':iteration,'validation_points':len(t),'closure_error':checked['closure_error'],
             'curvature_ok':checked['curve_ok'],'boundary_ok':checked['boundary_ok'],'forward_ok':checked['forward_ok'],
             'converged':bool(result.success),'feasible':True,'stopped_early':stop_reason is not None,
             'stop_reason':stop_reason or 'solver_converged','stop_message':stop_labels.get(stop_reason,'求解器正常收敛'),
             'elapsed_seconds':time.monotonic()-started,'max_runtime_s':runtime,
             'plateau_window':window,'plateau_percent':percent,'algorithm':algorithm,
             'boundary_mode':boundary_mode,'feasibility_iterations':feasibility_iterations,
             'curvature_energy':float(np.sum(k*k*np.linalg.norm(spline(t,1),axis=1))*problem.total/len(t)),
             'method':f'Periodic cubic spline + SLSQP; {algorithm}; termination={stop_reason or "solver_converged"}; no global optimum certificate',
             'vehicle':vehicle}
    return dict(route=route.tolist(),s=out_s.tolist(),curvature=ko.tolist(),heading=heading.tolist(),steering=np.arctan(vehicle['wheelbase']*ko).tolist(),metrics=metrics)
