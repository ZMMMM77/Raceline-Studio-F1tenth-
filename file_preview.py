"""Read-only previews of remote maps and routes, independent of optimization."""
import base64
import csv
import io
import math
import posixpath
from pathlib import PurePosixPath
import numpy as np
import yaml
from PIL import Image
from remote import RemoteError

IMAGE_EXTS = {'.png', '.pgm', '.jpg', '.jpeg'}

def route_preview(data, file_format='auto'):
    try:
        lines=[line.strip() for line in data.decode('utf-8-sig').splitlines() if line.strip()]
        comments=[line.lstrip('# ').strip() for line in lines if line.startswith('#')]
        rows=[line for line in lines if not line.startswith('#')]
        if not rows: raise ValueError()
        delimiter=';' if rows[0].count(';')>rows[0].count(',') else ','
        records=list(csv.reader(rows,delimiter=delimiter))
        header=None
        try:float(records[0][0])
        except ValueError:header=[v.strip().lower() for v in records.pop(0)]
        if header is None:
            for comment in reversed(comments):
                fields=[v.strip().lower() for v in comment.split(delimiter)]
                if ('x_m' in fields and 'y_m' in fields) or ('x' in fields and 'y' in fields):header=fields;break
        values=np.asarray([[float(v) for v in row] for row in records],dtype=float)
        if values.ndim!=2 or len(values)<2 or len(values)>100000 or values.shape[1]<2:raise ValueError()
        cols=values.shape[1]
        if file_format=='pure_pursuit':
            if cols not in (4,5):raise ValueError()
            indices=[0,1];label='Pure Pursuit'
        elif file_format=='mppi':
            if cols not in (9,10):raise ValueError()
            indices=[1,2];label='Levine MPPI'
        elif file_format!='auto':raise ValueError()
        elif header and 'x_m' in header and 'y_m' in header:indices=[header.index('x_m'),header.index('y_m')];label='按表头'
        elif header and 'x' in header and 'y' in header:indices=[header.index('x'),header.index('y')];label='按表头'
        elif cols in (7,9,10):indices=[1,2];label='s,x,y,…'
        elif cols in (2,4,5):indices=[0,1];label='x,y,…'
        else:raise ValueError()
        points=values[:,indices]
        if not np.isfinite(points).all():raise ValueError()
    except (ValueError,IndexError,UnicodeError,TypeError):
        raise RemoteError('无法预览路线。请检查 CSV 列格式及有效的 x/y 坐标（2–100000 点）。')
    boundaries=None
    if header and 'w_tr_right_m' in header and 'w_tr_left_m' in header:
        from planner import normals
        try:
            widths=values[:,[header.index('w_tr_right_m'),header.index('w_tr_left_m')]]
            if np.isfinite(widths).all() and np.all(widths>0):
                normal=normals(points)
                boundaries=[(points+normal*widths[:,0,None]).tolist(),(points-normal*widths[:,1,None]).tolist()]
        except IndexError:pass
    velocity={}
    if header:
        for name,key in [('speed_ratio','ratio'),('vx_mps','speed'),('friction','friction')]:
            if name in header and header.index(name)<cols:
                col=values[:,header.index(name)]
                if np.isfinite(col).all():velocity[key]=col.tolist()
    if file_format=='pure_pursuit':
        velocity['ratio']=values[:,3].tolist()
        if cols==5:velocity['friction']=values[:,4].tolist()
    if file_format=='mppi':
        velocity['speed']=values[:,5].tolist()
        if cols==10:velocity['friction']=values[:,9].tolist()
    import re
    parameters={}
    for comment in comments:
        for key,value in re.findall(r'(v_min|v_max|a_max|a_brake|mu_min|mu_max|width)\s*=\s*([0-9.eE+-]+)',comment):
            try:
                number=float(value)
                if math.isfinite(number) and number>0:parameters[key]=number
            except ValueError:pass
    if parameters:velocity['parameters']=parameters
    return dict(kind='route',velocity=velocity,boundaries=boundaries,points=points.tolist(),count=len(points),format=label,
                note='路线预览；未进行闭环、宽度或可行性检查。')

def png_preview(raw):
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.width*image.height>20_000_000 or max(image.size)>6000:
                raise RemoteError('地图图片过大，最大 6000 像素、2000 万像素。')
            image.load();width,height=image.size
            buf=io.BytesIO();image.convert('RGB').save(buf,format='PNG')
    except RemoteError:raise
    except Exception:raise RemoteError('无法读取地图图片。支持 PNG、PGM、JPG。')
    return dict(url='data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode(),width=width,height=height)

def yaml_map(remote, path):
    try:
        config=yaml.safe_load(remote.read(path))
        if not isinstance(config,dict):raise ValueError()
        image=config.get('image');resolution=float(config['resolution']);origin=[float(x) for x in config['origin']]
        if not isinstance(image,str) or not image or len(origin)!=3 or not all(math.isfinite(x) for x in origin) or not math.isfinite(resolution) or resolution<=0:raise ValueError()
        image_path=remote.path(image if image.startswith(('/','~/')) else posixpath.join(posixpath.dirname(path),image))
        result=png_preview(remote.read(image_path))
    except (KeyError,ValueError,TypeError,yaml.YAMLError,UnicodeError):
        raise RemoteError('地图 YAML 需要有效的 image、resolution 和 origin: [x,y,yaw]。')
    result.update(resolution=resolution,origin=origin,image_path=image_path,yaml_path=path)
    return result

def preview(remote,path,file_format='auto'):
    ext=PurePosixPath(path).suffix.lower()
    if ext in ('.csv','.txt'):
        result=route_preview(remote.read(path),file_format)
    elif ext in ('.yaml','.yml'):
        result=dict(kind='map',map=yaml_map(remote,path),note='已按 YAML 分辨率及原点加载地图。')
    elif ext in IMAGE_EXTS:
        result=dict(kind='map',map=png_preview(remote.read(path)),note='图片预览（像素坐标）。同名 YAML 可提供米制坐标。')
        warnings=[]
        for suffix in ('.yaml','.yml'):
            sibling=str(PurePosixPath(path).with_suffix(suffix))
            try:
                remote.sftp.stat(sibling)
            except OSError as e:
                if e.errno==2:continue
                raise
            try:
                mapped=yaml_map(remote,sibling)
                if remote.sftp.normalize(mapped['image_path'])==remote.sftp.normalize(path):
                    result.update(map=mapped,note='已自动匹配同名 YAML，按米制坐标显示。');break
                warnings.append('同名 YAML 指向另一张图片，保持像素预览。')
            except (RemoteError,OSError):warnings.append('同名 YAML 无法加载，保持像素预览。')
        if warnings:result['note']+=' '+ ' '.join(warnings)
    else:raise RemoteError('请选择 CSV/TXT、地图图片或地图 YAML。')
    result.update(path=path,name=posixpath.basename(path))
    return result
