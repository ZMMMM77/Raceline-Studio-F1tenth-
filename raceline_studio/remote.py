"""Local-only SSH/SFTP support. Passwords live only in macOS Keychain."""
import atexit
import base64
import hashlib
import json
import os
import posixpath
import stat
import threading
import uuid
from pathlib import Path
from functools import wraps
from flask import Blueprint, jsonify, request
import paramiko
from keyring.backends.macOS import Keyring

LIMIT = 40 * 1024 * 1024
SERVICE = 'Raceline Studio SSH'

class RemoteError(Exception):
    def __init__(self, message, code=400, **details):
        self.message, self.code, self.details = message, code, details

def digest(data):
    return hashlib.sha256(data).hexdigest()

class Remote:
    def __init__(self, root, vault=None):
        self.root = Path(root) / '.remote'
        self.root.mkdir(mode=0o700, exist_ok=True)
        self.config_path = self.root / 'connection.json'
        self.hosts = self.root / 'known_hosts'
        self.vault = vault or Keyring()
        self.lock = threading.RLock()
        self.client = self.sftp = None
        self.identity = None
        atexit.register(self.close)

    def config(self):
        if not self.config_path.exists(): return {}
        return json.loads(self.config_path.read_text())

    def close(self):
        if self.sftp: self.sftp.close()
        if self.client: self.client.close()
        self.client = self.sftp = None
        self.identity = None

    def status(self):
        from .remote_paths import read_paths
        config_paths = read_paths(self.root.parent)
        connected = bool(self.client and self.client.get_transport() and self.client.get_transport().is_active())
        return dict(connected=connected, profile=self.config(), identity=self.identity if connected else None, directories=[dict(label='路线 / CSV', path=config_paths['waypoint_directory']), dict(label='地图 / MAPS', path=config_paths['map_directory'])])

    def connect(self, data):
        host = str(data.get('host', '')).strip()
        user = str(data.get('username', '')).strip()
        try: port = int(data.get('port', 22))
        except (ValueError, TypeError): raise RemoteError('SSH 端口无效。')
        if not host or not user or any(c in host + user for c in '\r\n\x00') or not 1 <= port <= 65535:
            raise RemoteError('请填写主机地址、用户名及有效端口。')
        account = json.dumps([host, port, user], ensure_ascii=True)
        password = data.get('password') or self.vault.get_password(SERVICE, account)
        if not password: raise RemoteError('首次连接请填写密码。')
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        if self.hosts.exists(): client.load_host_keys(str(self.hosts))
        accepted = data.get('fingerprint')
        class Verify(paramiko.MissingHostKeyPolicy):
            def missing_host_key(policy, ssh, hostname, key):
                fingerprint = 'SHA256:' + base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
                if accepted != fingerprint:
                    raise RemoteError('首次连接：请核对并信任主机指纹。', 409, fingerprint=fingerprint)
                ssh.get_host_keys().add(hostname, key.get_name(), key)
        client.set_missing_host_key_policy(Verify())
        try:
            client.connect(host, port=port, username=user, password=password, timeout=8,
                           banner_timeout=8, auth_timeout=12, channel_timeout=10,
                           allow_agent=False, look_for_keys=False)
            sftp = client.open_sftp()
            sftp.get_channel().settimeout(15)
            home = sftp.normalize('.')
            client.get_transport().set_keepalive(20)
            # Persist only after successful authentication and SFTP setup.
            self.vault.set_password(SERVICE, account, password)
            client.save_host_keys(str(self.hosts))
            os.chmod(self.hosts, 0o600)
            profile = dict(host=host, port=port, username=user, directory=data.get('directory') or home,
                           auto_connect=data.get('auto_connect') is True)
            temp = self.config_path.with_suffix('.tmp')
            temp.write_text(json.dumps(profile, ensure_ascii=False, indent=2))
            os.chmod(temp, 0o600)
            temp.replace(self.config_path)
        except Exception:
            client.close()
            raise
        self.close()
        self.client, self.sftp = client, sftp
        self.identity = dict(host=host, port=port, username=user)
        return self.status()

    def path(self, path):
        if not self.status()['connected']: raise RemoteError('SSH 未连接，请先连接 Jetson。', 409)
        if not isinstance(path, str) or not path or '\x00' in path: raise RemoteError('远程路径无效。')
        home = self.sftp.normalize('.')
        if path == '~': path = home
        elif path.startswith('~/'): path = posixpath.join(home, path[2:])
        elif not path.startswith('/'): path = posixpath.join(home, path)
        return posixpath.normpath(path)

    def read(self, path):
        attr = self.sftp.stat(path)
        if not stat.S_ISREG(attr.st_mode) or attr.st_size > LIMIT:
            raise RemoteError('请选择不超过 40 MB 的普通文件。')
        with self.sftp.open(path, 'rb') as f: data = f.read(LIMIT + 1)
        if len(data) > LIMIT: raise RemoteError('文件超过 40 MB。')
        return data

    def save(self, path, data, expected=None):
        if len(data) > LIMIT or not data: raise RemoteError('文件为空或超过 40 MB。')
        try: attr = self.sftp.lstat(path)
        except OSError as e:
            if e.errno != 2: raise
            attr = None
        backup = None
        if attr:
            if not stat.S_ISREG(attr.st_mode): raise RemoteError('只能覆盖普通文件，不能覆盖目录或符号链接。')
            old = self.read(path)
            current = digest(old)
            if expected != current:
                raise RemoteError('目标文件已存在或发生变化，请确认覆盖。', 409, revision=current, path=path)
            backup = path + '.bak-' + uuid.uuid4().hex
            with self.sftp.open(backup, 'wx') as f: f.write(old)
            self.sftp.chmod(backup, stat.S_IMODE(attr.st_mode))
        elif expected is not None:
            raise RemoteError('原文件已被删除，请刷新后另存。', 409)
        temp = path + '.tmp-' + uuid.uuid4().hex
        try:
            with self.sftp.open(temp, 'wx') as f: f.write(data)
            self.sftp.chmod(temp, stat.S_IMODE(attr.st_mode) if attr else 0o600)
            if attr:
                if digest(self.read(path)) != expected:
                    raise RemoteError('写入期间文件发生变化，已取消覆盖。', 409)
                self.sftp.posix_rename(temp, path)
            else: self.sftp.rename(temp, path)
        finally:
            try: self.sftp.remove(temp)
            except OSError: pass
        return dict(path=path, backup=backup, revision=digest(data))

def install_remote(app, root):
    remote = Remote(root)
    bp = Blueprint('remote', __name__, url_prefix='/api/remote')
    def endpoint(fn):
        @wraps(fn)
        def guarded(*args, **kwargs):
            with remote.lock:
                try: return jsonify(fn(*args, **kwargs))
                except RemoteError as e: return jsonify(error=e.message, **e.details), e.code
                except (ValueError, TypeError): return jsonify(error='请检查 remote_paths.json 的格式和读取路径。'), 400
                except paramiko.BadHostKeyException: return jsonify(error='主机指纹已改变，请核实 Jetson 身份后再连接。'), 409
                except paramiko.AuthenticationException: return jsonify(error='SSH 登录失败，请检查用户名和密码。'), 401
                except (OSError, paramiko.SSHException, EOFError): return jsonify(error='SSH/SFTP 操作失败：请检查网络、远程路径、权限及 SFTP 服务。'), 400
                except Exception: return jsonify(error='连接设置失败，请检查 macOS 钥匙串是否允许此 Python 程序访问。'), 400
        return guarded
    @bp.get('/status')
    @endpoint
    def status(): return remote.status()
    @bp.post('/connect')
    @endpoint
    def connect(): return remote.connect(request.get_json() or {})
    @bp.post('/disconnect')
    @endpoint
    def disconnect():
        remote.close()
        return remote.status()
    @bp.post('/forget')
    @endpoint
    def forget():
        p = remote.config()
        if p:
            account = json.dumps([p['host'], p['port'], p['username']], ensure_ascii=True)
            if remote.vault.get_password(SERVICE, account) is not None: remote.vault.delete_password(SERVICE, account)
            remote.config_path.unlink(missing_ok=True)
        remote.close()
        return remote.status()
    @bp.post('/list')
    @endpoint
    def listing():
        path = remote.path(request.json.get('path', '~'))
        entries = []
        for item in remote.sftp.listdir_iter(path):
            if len(entries) >= 2000: raise RemoteError('目录超过 2000 项，请输入更具体的目录。')
            entries.append(dict(name=item.filename, directory=stat.S_ISDIR(item.st_mode), size=item.st_size))
        entries.sort(key=lambda e:(not e['directory'], e['name'].lower()))
        return dict(path=path, entries=entries)
    @bp.post('/preview')
    @endpoint
    def preview_file():
        from .file_preview import preview
        payload = request.get_json() or {}
        return preview(remote, remote.path(payload.get('path')), payload.get('format', 'auto'))
    @bp.post('/read')
    @endpoint
    def read():
        path = remote.path(request.json.get('path'))
        if Path(path).suffix.lower() not in ('.csv','.txt','.yaml','.yml','.png','.pgm','.jpg','.jpeg'):
            raise RemoteError('请选择 CSV/TXT waypoint 或地图图片/YAML。')
        data = remote.read(path)
        return dict(path=path, name=posixpath.basename(path), content=base64.b64encode(data).decode(), revision=digest(data))
    @bp.post('/save')
    @endpoint
    def save():
        payload = request.get_json()
        path = remote.path(payload.get('path'))
        if Path(path).suffix.lower() not in ('.csv', '.txt'): raise RemoteError('本阶段仅写入 CSV/TXT waypoint。')
        source = payload.get('source', '')
        # Only serve generated output CSV files, never arbitrary local paths.
        parts = source.split('/')
        if len(parts) != 4 or parts[:2] != ['', 'outputs'] or not parts[2].replace('_','').isalnum() or Path(parts[3]).name != parts[3] or not parts[3].endswith('.csv'):
            raise RemoteError('请先选择已生成的 CSV 结果。')
        local = Path(root) / 'outputs' / parts[2] / parts[3]
        if not local.is_file() or local.stat().st_size > LIMIT: raise RemoteError('本地结果不存在或过大。')
        return remote.save(path, local.read_bytes(), payload.get('revision'))
    app.register_blueprint(bp)
    return remote
