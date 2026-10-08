"""Editable Jetson paths. Read each time the remote file tree refreshes."""
import json
from pathlib import Path

def read_paths(root):
    file=Path(root)/'remote_paths.json'
    data=json.loads(file.read_text()) if file.exists() else {}
    if not isinstance(data,dict):raise ValueError('路径配置必须是 JSON 对象。')
    result={}
    for key in ('waypoint_directory','map_directory'):
        value=data.get(key,'~')
        if not isinstance(value,str) or not value.strip() or '\x00' in value:raise ValueError('请填写有效的 Jetson 目录。')
        result[key]=value.strip()
    return result
