import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR',str(Path(__file__).resolve().parent.parent/'.cache'/'matplotlib'))
import json
import io
import uuid
import threading
import zipfile
from datetime import datetime
import numpy as np
from PIL import Image
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.transforms import Affine2D
from raceline_studio.planner import PlanningError, MapData, parse_csv, resample, arc, normals, optimize, has_crossing, plan_speed_profile, route_geometry

ROOT=Path(__file__).resolve().parent.parent
OUTPUT=ROOT/'outputs';OUTPUT.mkdir(exist_ok=True)
app=Flask(__name__,static_folder='static',static_url_path='/static')
app.config['MAX_CONTENT_LENGTH']=45*1024*1024
TRACKS={};JOBS={};RESULTS={};PLOT_LOCK=threading.Lock();COMPUTE_LOCK=threading.Lock()

@app.before_request
def local_only():
    if request.host.split(':')[0] not in ('127.0.0.1','localhost'):
        return jsonify(error='仅允许本机访问。'),403
    if request.method=='POST' and request.headers.get('X-Raceline-Local')!='1':
        return jsonify(error='请通过本地网页操作。'),403
    origin=request.headers.get('Origin')
    if origin and origin not in ('http://127.0.0.1:8766','http://localhost:8766'):
        return jsonify(error='不允许跨站请求。'),403

@app.errorhandler(Exception)
def error(e):
    if isinstance(e,PlanningError):return jsonify(error=str(e)),400
    if isinstance(e,HTTPException):return jsonify(error=e.description),e.code
    app.logger.exception('Request failed')
    return jsonify(error='处理失败，请检查输入文件。详细信息见运行终端。'),500

@app.get('/')
def index():return app.send_static_file('index.html')

@app.after_request
def no_stale_ui(response):
    if request.path=='/' or request.path.startswith('/static/'):
        response.headers['Cache-Control']='no-cache'
    return response

def directory(label):
    ident=datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]
    path=OUTPUT/ident;path.mkdir()
    return ident,path

def json_write(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def save_center(track):
    np.savetxt(track['dir']/'centerline.csv',np.c_[track['center'],track['widths']],delimiter=',',header='x_m,y_m,w_tr_right_m,w_tr_left_m',fmt='%.7f')
    np.savetxt(track['dir']/'reference_path.csv',track['center'],delimiter=',',header='x_m,y_m',fmt='%.7f')
    plot(track,None,track['dir']/'centerline.png')
    json_write(track['dir']/'import_report.json',{'name':track['name'],'warnings':track['warnings'],'diagnostics':track['diagnostics'],'boundary_mode':track['boundary_mode'],'length_m':arc(track['center'])[1],'centerline_columns':['x_m','y_m','w_tr_right_m','w_tr_left_m'],'closed_loop':'last point connects to first; no duplicated endpoint','map_origin':track['map'].origin.tolist() if track['map'] else None,'map_resolution':track['map'].resolution if track['map'] else None})

def plot(track,result,path):
    with PLOT_LOCK:
        plt.rcParams.update({'font.family':'DejaVu Sans','axes.spines.top':False,'axes.spines.right':False})
        fig,ax=plt.subplots(figsize=(12,9),facecolor='#f5f8fb')
        p=track['center'];w=track['widths'];n=normals(p)
        m=track['map']
        if m:
            transform=Affine2D().rotate(m.origin[2]).translate(*m.origin[:2])+ax.transData
            ax.imshow(m.image,cmap='gray',vmin=0,vmax=255,origin='upper',extent=(0,m.image.width*m.resolution,0,m.image.height*m.resolution),transform=transform,alpha=.62)
        if track.get('boundary_mode','csv')!='map':
            for pts in (p+n*w[:,0,None],p-n*w[:,1,None]):ax.plot(*np.vstack([pts,pts[0]]).T,color='#8293a6',lw=.8)
        ax.plot(*np.vstack([p,p[0]]).T,'--',color='#149b85',lw=1.2,label='Centerline')
        if result:
            q=np.array(result['route']);ax.plot(*np.vstack([q,q[0]]).T,color='#e68136',lw=1.6,label='Minimum-curvature line' if result['metrics'].get('algorithm')=='min_curvature' else 'Curvature-constrained shortest line')
        ax.scatter(*p[0],color='#213c52',s=25,zorder=5);ax.annotate('START',p[0],xytext=(5,7),textcoords='offset points',fontsize=9)
        ax.set_xlim(p[:,0].min()-4,p[:,0].max()+4);ax.set_ylim(p[:,1].min()-4,p[:,1].max()+4)
        ax.set_aspect('equal');ax.set_xlabel('Map x [m]');ax.set_ylabel('Map y [m]');ax.grid(alpha=.12);ax.legend(loc='best',framealpha=.9)
        ax.set_title('RACELINE STUDIO / '+('Path comparison' if result else 'Centerline'),loc='left',pad=18,fontweight='bold')
        if result:
            me=result['metrics'];fig.text(.12,.025,f'Length {me["length"]:.2f} m   |   max |curvature| {me["max_curvature"]:.4f} / {me["curvature_limit"]:.4f} 1/m   |   Validated feasible route',fontsize=9,color='#5b7088')
        fig.tight_layout(rect=(0,.045,1,1));fig.savefig(path,dpi=170);plt.close(fig)

def plot_speed(result,profile,path):
    with PLOT_LOCK:
        s=np.asarray(result['s']);total=result['metrics']['length']
        speed=profile['speed'];cap=profile['corner_limit'];k=np.abs(result['curvature'])
        x=np.r_[s,total];v=np.r_[speed,speed[0]];limit=np.r_[cap,cap[0]]
        fig,(ax,ak)=plt.subplots(2,1,figsize=(12,6),sharex=True,gridspec_kw={'height_ratios':[2,1]},facecolor='#f5f8fb')
        ax.plot(x,limit,'--',color='#9aaabb',lw=1,label='Local curve speed cap')
        ax.plot(x,v,color='#177f77',lw=2,label='Planned waypoint speed')
        ax.axhline(profile['metrics']['base_speed'],color='#df9253',lw=1,ls=':',label='Straight baseline')
        ax.set_ylabel('Speed [m/s]');ax.set_ylim(bottom=0);ax.legend(frameon=False);ax.grid(alpha=.2)
        ak.plot(x,np.r_[k,k[0]],color='#db8554',lw=1.4);ak.set_ylabel('|Curvature| [1/m]')
        ak.set_xlabel('Distance along closed lap [m]');ak.grid(alpha=.2)
        fig.suptitle('RACELINE STUDIO / Planned speed profile',fontweight='bold')
        fig.tight_layout();fig.savefig(path,dpi=170);plt.close(fig)

def pack(path):
    with zipfile.ZipFile(path/'results.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(path.iterdir()):
            if p.suffix in ('.csv','.png','.json','.yaml'):z.write(p,p.name)

def public(track):
    ident=track['id'];m=track['map']
    return {'id':ident,'name':track['name'],'boundary_mode':track['boundary_mode'],'diagnostics':track['diagnostics'],'source_kind':'csv' if track['source_route'] is not None else 'centerline','center':track['center'].tolist(),'widths':track['widths'].tolist(),'length':arc(track['center'])[1],'warnings':track['warnings'],'output_dir':str(track['dir']),'map':{'url':f'/outputs/{ident}/map.png','resolution':m.resolution,'origin':m.origin.tolist(),'width':m.image.width,'height':m.image.height} if m else None,'reference_image':f'/outputs/{ident}/reference_image.png' if track['reference_image'] else None,'files':{'center':f'/outputs/{ident}/centerline.csv','png':f'/outputs/{ident}/centerline.png','zip':f'/outputs/{ident}/results.zip'}}

def register(name,p,w,m,warnings,reference_image=None,source_route=None,boundary_mode='csv'):
    if has_crossing(p):raise PlanningError('参考路径自交。请提供一条按顺序排列、不自交的闭合赛道。')
    ident,path=directory(name)
    diagnostics=dict(boundary_mode=boundary_mode,max_adjacent_width_change_m=float(np.abs(np.roll(w,-1,axis=0)-w).max()),
                     min_reference_map_clearance_m=float(m.distance(p).min()) if m else None,
                     cleanup=m.cleanup_info if m else None)
    track=dict(id=ident,name=name,boundary_mode=boundary_mode,diagnostics=diagnostics,center=p,widths=w,map=m,warnings=warnings,dir=path,source_route=source_route,
               reference_image=reference_image is not None)
    if m:
        m.image.save(path/'map.png')
        if m.extraction_free is not None:
            Image.fromarray(np.where(m.extraction_free,254,0).astype(np.uint8)).save(path/'extraction_mask.png')
    if reference_image is not None:reference_image.save(path/'reference_image.png')
    save_center(track);pack(path);TRACKS[ident]=track
    return track

@app.get('/api/demo')
def demo():
    t=np.linspace(0,2*np.pi,300,endpoint=False)
    p=np.c_[15*np.cos(t)+3*np.cos(2*t),10*np.sin(t)+2*np.sin(3*t)]
    p,w=resample(p,np.full((len(p),2),1.8),spacing=.2)
    return jsonify(public(register('示例 · Harbor Loop',p,w,None,['内置合成赛道，不代表真实车辆能力。'])))

@app.post('/api/import')
def import_track():
    mode=request.form.get('mode','csv');reverse=request.form.get('reverse')=='true'
    csvfile=request.files.get('csv');image=request.files.get('image');yamlfile=request.files.get('yaml')
    if yamlfile and not image:raise PlanningError('已选择 YAML，还需要选择它对应的地图图片。')
    m=None;warnings=[];reference_image=None;source_route=None;boundary_mode='csv'
    boundary_source=request.form.get('boundary_source','auto')
    if boundary_source not in ('auto','csv'):raise PlanningError('未知的 CSV 边界来源。')
    if image and yamlfile:m=MapData.read(image.read(),yamlfile.read())
    elif image and mode=='csv':
        try:
            reference_image=Image.open(io.BytesIO(image.read()))
            reference_image.load()
            if max(reference_image.size)>6000 or reference_image.width*reference_image.height>20_000_000:
                raise PlanningError('地图图片太大，请缩小至 6000 像素以内。')
            reference_image=reference_image.convert('RGB')
        except PlanningError:raise
        except Exception as e:raise PlanningError('无法读取地图图片。') from e
        warnings.append('未提供 YAML：PNG 仅作原图参考，不参与地图边界校验或米制坐标叠加。')
    if mode=='map':
        if not m:raise PlanningError('仅从 SLAM 地图提取中心线需要地图图片和 YAML，以确定米制比例与原点。')
        p,w=m.extract(cleanup=request.form.get('cleanup_map','true')!='false',
                      hole_area=request.form.get('cleanup_hole_area',.01),gap_radius=request.form.get('cleanup_gap_radius',.05))
        boundary_mode='map';name=Path(image.filename).stem+' · 地图提取'
        info=m.cleanup_info
        warnings.append(f'提取副本填补 {info["filled_hole_pixels"]} 个小孔像素、补缝封闭 {info["closed_free_pixels"]} 个空闲像素；原始地图用于全部净空检查。')
        warnings.append('默认逆时针；宽度射线仅限制搜索范围，不连接成虚构墙壁。仅支持单一封闭赛道。')
    elif mode=='csv':
        if not csvfile:raise PlanningError('请选择中心线 CSV 文件。')
        p,w,path_only=parse_csv(csvfile.read(), request.form.get("csv_format", "auto"));name=Path(csvfile.filename).stem
        source_route=p.copy()
        p,w=resample(p,w,spacing=.2)
        # Keep the supplied path geometry; no automatic cross-section recentering.
        if m and np.min(m.distance(p))<0:
            raise PlanningError('CSV 参考线与原始地图不对齐或净空不足，请检查 resolution、origin 和 CSV 坐标；不会自动平移路线。')
        if m and (boundary_source=='auto' or w is None):
            w=m.widths(p,cap=False);boundary_mode='map'
            warnings.append('保留 CSV 路线形状，仅按弧长重采样；边界以原始地图为准，CSV 自带宽度不作为障碍边界。')
        elif w is None:
            from raceline_studio.planner import positive
            width=positive(request.form.get('fallback_width'),'缺失时的单侧赛道宽度',high=100)
            w=np.full((len(p),2),width)
            warnings.append('使用手动填写的统一宽度。结果只针对该假定走廊，未检查真实墙壁。')
        elif not m:
            warnings.append('仅检查 CSV 给出的赛道宽度；没有使用图片像素验证墙壁。')
        else:
            warnings.append('保留 CSV 路线形状；同时检查所选 CSV 宽度约束与原始地图净空。')
    else:raise PlanningError('未知导入方式。')
    if reverse:
        p=p[::-1].copy();w=w[::-1,::-1].copy()
        if source_route is not None:source_route=source_route[::-1].copy()
    return jsonify(public(register(name,p,w,m,warnings,reference_image,source_route,boundary_mode)))

@app.post('/api/optimize')
def start():
    data=request.get_json();ident=data.get('track_id')
    if ident not in TRACKS:raise PlanningError('请重新导入地图，原会话可能已过期。')
    data['parameters']=dict(data.get('parameters') or {},boundary_mode=TRACKS[ident]['boundary_mode'])
    from raceline_studio.planner import vehicle_parameters, optimization_limits
    optimization_limits(data.get('parameters',{}))
    vehicle_parameters(data.get('parameters',{}))
    if not COMPUTE_LOCK.acquire(blocking=False):raise PlanningError('已有一项计算正在运行，请等待它完成。')
    jobid=uuid.uuid4().hex;track=TRACKS[ident];JOBS[jobid]={'status':'running','message':'正在准备约束…','iteration':0}
    def worker():
        try:
            def progress(iteration,message):JOBS[jobid].update(iteration=iteration,message=message)
            result=optimize(track['center'],track['widths'],track['map'],data['parameters'],progress)
            result_id,path=directory('result')
            np.savetxt(path/'centerline.csv',np.c_[track['center'],track['widths']],delimiter=',',header='x_m,y_m,w_tr_right_m,w_tr_left_m',fmt='%.7f')
            np.savetxt(path/'reference_path.csv',track['center'],delimiter=',',header='x_m,y_m',fmt='%.7f')
            route_filename='min_curvature_path.csv' if result['metrics']['algorithm']=='min_curvature' else 'shortest_path.csv'
            np.savetxt(path/route_filename,np.c_[result['route'],result['s'],result['heading'],result['curvature'],result['steering']],delimiter=',',header='x_m,y_m,s_m,psi_rad,kappa_radpm,steering_rad',fmt='%.7f')
            plot(track,result,path/'raceline_comparison.png')
            json_write(path/'report.json',{'track':track['name'],'source_dir':str(track['dir']),'parameters':data['parameters'],'metrics':result['metrics'],'warnings':track['warnings'],'heading_convention':'atan2(dy,dx), zero = +x, CCW positive; NOT TUM north-zero convention','route_format':'comma separated, x/y first, comment header, no duplicated closing point; speed profile generated separately','boundary_model':('original raster SDF only; ray endpoints are not walls' if track['boundary_mode']=='map' else 'CSV corridor and optional original raster')+'; circumscribed disk plus margin; dense validation','import_diagnostics':track['diagnostics'],'limitations':['Validated feasible numerical route. Early stopping does not imply solver convergence or global optimality.','Kinematic curvature constraint only; speed must be planned separately.','Raster correctness depends on resolution/origin/thresholds and supplied map.','Curvature is densely sampled, not an analytic interval certificate.']})
            pack(path)
            result.update(result_id=result_id,output_dir=str(path),files={'center':f'/outputs/{result_id}/centerline.csv','route':f'/outputs/{result_id}/{route_filename}','png':f'/outputs/{result_id}/raceline_comparison.png','zip':f'/outputs/{result_id}/results.zip'})
            RESULTS[result_id]=dict(track=track,result=result,path=path)
            JOBS[jobid].update(status='done',message=result['metrics']['stop_message']+'；路线已通过加密约束检查并保存。',result=result)
        except PlanningError as e:JOBS[jobid].update(status='error',message=str(e))
        except Exception:
            app.logger.exception('Optimizer failed');JOBS[jobid].update(status='error',message='计算失败，详细信息见终端。中心线仍可导出。')
        finally:COMPUTE_LOCK.release()
    threading.Thread(target=worker,daemon=True).start()
    return jsonify(job_id=jobid)

@app.post('/api/speed-profile')
def speed_profile():
    data=request.get_json(silent=True) or {}
    saved=RESULTS.get(data.get('result_id'))
    track=TRACKS.get(data.get('track_id')) if not saved else None
    if not saved and not track:raise PlanningError('请先导入地图或计算路线。')
    result=saved['result'] if saved else route_geometry(track['source_route'] if track['source_route'] is not None else track['center'])
    path=saved['path'] if saved else track['dir'];ident=result['result_id'] if saved else track['id']
    params=data.get('parameters') or {}
    # Compatibility endpoint; the UI uses /api/velocity/* for the active edit copy.
    from raceline_studio.velocity import calculate
    v=calculate({'points':result['route'],'parameters':{
        'v_max':params.get('base_speed',7.6),'v_min':params.get('v_min',.01),
        'mu_min':float(params.get('lateral_accel',4.0221))/9.81,
        'mu_max':max(.7,float(params.get('lateral_accel',4.0221))/9.81),
        'a_max':params.get('acceleration',6),'a_brake':params.get('braking',8)}})
    vp=v['parameters'];speeds=np.asarray(v['speed'])
    profile={'speed':speeds,'acceleration':np.asarray(v['acceleration']),'corner_limit':speeds,
             'metrics':{'base_speed':vp['v_max'],'lateral_accel':vp['mu_min']*9.81,
             'acceleration_limit':vp['a_max'],'braking_limit':vp['a_brake'],
             'min_speed':float(speeds.min()),'max_speed':float(speeds.max()),
             'estimated_lap_time':v['lap_time'],'limited_points':int(np.sum(speeds<vp['v_max']))}}
    speed=profile['speed'];acc=profile['acceleration']
    columns=np.c_[result['route'],speed,result['s'],result['heading'],result['curvature'],acc]
    header='x_m,y_m,vx_mps,s_m,psi_rad,kappa_radpm,ax_mps2'
    if saved:
        columns=np.c_[columns,result['steering']]
        header+=',steering_rad'
    np.savetxt(path/'speed_waypoints.csv',columns,delimiter=',',header=header,fmt='%.7f')
    plot_speed(result,profile,path/'speed_profile.png')
    report_path=path/('report.json' if saved else 'import_report.json')
    report=json.loads(report_path.read_text(encoding='utf-8'))
    report['speed_profile']={'parameters':{k:profile['metrics'][k] for k in ('base_speed','lateral_accel','acceleration_limit','braking_limit')},
                             'metrics':profile['metrics'],
                             'method':'Menger curvature, wrapped box smoothing, per-point friction, two forward/backward closed-loop passes',
                             'limitations':'Illustrative model: grip, actuator lag, steering rate and real vehicle tracking are unmeasured; validate in simulation and on the car.'}
    json_write(report_path,report);pack(path)
    result.update(speed=speed.tolist(),speed_metrics=profile['metrics'])
    files=result['files'] if saved else {'speed':f'/outputs/{ident}/speed_waypoints.csv','speed_png':f'/outputs/{ident}/speed_profile.png','zip':f'/outputs/{ident}/results.zip'}
    files.update(speed=f"/outputs/{ident}/speed_waypoints.csv",speed_png=f"/outputs/{ident}/speed_profile.png")
    return jsonify(route=result['route'],s=result['s'],length=result['metrics']['length'],curvature=result['curvature'],speed=result['speed'],speed_metrics=result['speed_metrics'],files=files,output_dir=str(path))

@app.get('/api/jobs/<job>')
def job(job):
    if job not in JOBS:raise PlanningError('计算任务不存在，请重新导入。')
    return jsonify(JOBS[job])

@app.get('/outputs/<ident>/<filename>')
def download(ident,filename):
    if not (len(ident)==24 and all(c.isalnum() or c=='_' for c in ident)):
        return jsonify(error='无效结果目录。'),404
    allowed={'pure_pursuit.csv','mppi.csv','edited_waypoints.csv','min_curvature_path.csv','centerline.csv','reference_path.csv','extraction_mask.png','shortest_path.csv','speed_waypoints.csv','centerline.png','raceline_comparison.png','speed_profile.png','map.png','reference_image.png','results.zip','report.json','import_report.json'}
    if filename not in allowed:return jsonify(error='文件不存在。'),404
    return send_from_directory(OUTPUT/ident,filename,as_attachment=request.args.get('download')=='1')

from raceline_studio.waypoint_edit import install_waypoint_edit
install_waypoint_edit(app, directory, json_write, pack)

from raceline_studio.velocity import install_velocity
install_velocity(app, directory, json_write, pack)

from raceline_studio.remote import install_remote
REMOTE = install_remote(app, ROOT)

if __name__=='__main__':app.run(host='127.0.0.1',port=8766,debug=False,threaded=True)
