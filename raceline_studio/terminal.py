"""Saved launch recipes and scoped remote tmux sessions over the existing SSH client."""
import json
import os
import re
import shlex
import uuid
from pathlib import Path
from functools import wraps
from flask import Blueprint, jsonify, request
from .remote import RemoteError


def validate_config(data, namespace):
    if not isinstance(data, dict) or not isinstance(data.get('tasks'), list) or len(data['tasks']) > 12:
        raise RemoteError('INVALID_CONFIG')
    result = {'namespace': namespace, 'name': str(data.get('name', 'Jetson'))[:60], 'tasks': []}
    ids = set()
    for raw in data['tasks']:
        if not isinstance(raw, dict):
            raise RemoteError('INVALID_CONFIG')
        ident = raw.get('id') or uuid.uuid4().hex[:12]
        if not isinstance(ident, str) or not re.fullmatch(r'[a-f0-9]{12}', ident) or ident in ids:
            raise RemoteError('INVALID_CONFIG')
        ids.add(ident)
        task = {'id': ident, 'enabled': raw.get('enabled', True) is True}
        for key, limit, default in [('name', 60, 'Terminal'), ('directory', 1024, '~'),
                                    ('setup', 8000, ''), ('command', 16000, ''), ('ready_text', 200, '')]:
            value = raw.get(key, default)
            if not isinstance(value, str) or len(value) > limit or '\x00' in value:
                raise RemoteError('INVALID_CONFIG')
            task[key] = value.strip()
        task['directory'] = task['directory'] or '~'
        task['name'] = task['name'] or 'Terminal'
        result['tasks'].append(task)
    return result


class Terminals:
    def __init__(self, remote):
        self.remote = remote
        self.path = remote.root / 'terminals.json'
        self.agent = Path(__file__).with_name('terminal_agent.py').read_text()

    def config(self):
        if self.path.exists():
            return json.loads(self.path.read_text())
        config = {'namespace': uuid.uuid4().hex, 'name': 'Jetson', 'tasks': []}
        self.write(config)
        return config

    def write(self, config):
        temp = self.path.with_suffix('.tmp')
        with open(temp, 'w', encoding='utf-8') as f:
            os.chmod(temp, 0o600)
            json.dump(config, f, ensure_ascii=False, indent=2)
        temp.replace(self.path)

    def call(self, action, config=None, **kwargs):
        if not self.remote.status()['connected']:
            raise RemoteError('SSH_DISCONNECTED', 409)
        config = config or self.config()
        payload = dict(config, action=action, **kwargs)
        # Only a fixed helper is executed; user commands are JSON, not interpolated into SSH shell syntax.
        stdin, stdout, stderr = self.remote.client.exec_command(
            'python3 -c ' + shlex.quote(self.agent), timeout=25)
        try:
            stdin.write(json.dumps(payload, ensure_ascii=False))
            stdin.flush()
            stdin.channel.shutdown_write()
            raw = stdout.read(500000)
            error = stderr.read(4000).decode('utf-8', 'replace')
            code = stdout.channel.recv_exit_status()
            if code:
                raise RemoteError('REMOTE_HELPER_FAILED: ' + error[:500], 400)
            result = json.loads(raw)
            if result.get('error'):
                raise RemoteError(result['error'], 400)
            return result
        finally:
            stdout.channel.close()

    def save(self, data):
        old = self.config()
        new = validate_config(data, old['namespace'])
        removed = {t['id'] for t in old['tasks']} - {t['id'] for t in new['tasks']}
        if removed:
            # Avoid orphaning live sessions when a recipe is removed.
            status = self.call('status', old)
            if any(s['id'] in removed and s['state'] in ('running', 'ready_log') for s in status['sessions']):
                raise RemoteError('STOP_BEFORE_REMOVE', 409)
        self.write(new)
        return new


def install_terminals(app, remote):
    manager = Terminals(remote)
    bp = Blueprint('terminals', __name__, url_prefix='/api/terminals')

    def endpoint(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            with remote.lock:
                try:
                    return jsonify(fn(*args, **kwargs))
                except RemoteError as e:
                    return jsonify(error=e.message), e.code
                except Exception as e:
                    app.logger.warning('Terminal request failed: %s', type(e).__name__)
                    return jsonify(error='TERMINAL_REQUEST_FAILED'), 400
        return wrapped

    @bp.get('/config')
    @endpoint
    def config():
        return manager.config()

    @bp.post('/config')
    @endpoint
    def save():
        return manager.save(request.get_json() or {})

    @bp.post('/action')
    @endpoint
    def action():
        data = request.get_json() or {}
        action = data.get('action')
        if action not in ('status', 'start', 'start_all', 'interrupt', 'input'):
            raise RemoteError('INVALID_ACTION')
        return manager.call(action, target=data.get('target'), selected=data.get('selected'), text=data.get('text', ''))

    app.register_blueprint(bp)
    return manager
