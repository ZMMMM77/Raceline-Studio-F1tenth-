"""Executed via SSH on Jetson; only manages this Studio's isolated tmux sessions."""
import json
import os
import re
import shlex
import shutil
import subprocess
import sys


def run(payload):
    if not shutil.which('tmux'):
        raise ValueError('TMUX_MISSING')
    namespace = payload['namespace']
    if not re.fullmatch(r'[a-f0-9]{32}', namespace):
        raise ValueError('INVALID_CONFIG')
    prefix = 'rs_' + namespace + '_'

    def tmux(*args, check=True):
        p = subprocess.run(['tmux', '-L', 'raceline-studio', '-f', '/dev/null', *args],
                           capture_output=True, text=True, errors='replace', timeout=5)
        if check and p.returncode:
            raise ValueError(p.stderr.strip()[:500] or 'TMUX_FAILED')
        return p

    def name(task):
        if not re.fullmatch(r'[a-f0-9]{12}', task['id']):
            raise ValueError('INVALID_CONFIG')
        return prefix + task['id']

    def panes():
        p = tmux('list-panes', '-a', '-F', '#{session_name}\t#{pane_dead}\t#{pane_dead_status}\t#{pane_dead_signal}', check=False)
        if p.returncode:
            if 'no server running' in p.stderr or 'No such file' in p.stderr:
                return {}
            raise ValueError(p.stderr.strip()[:500] or 'TMUX_FAILED')
        return {line.split('\t')[0]: line.split('\t')[1:] for line in p.stdout.splitlines()}

    def snapshot(tasks, selected):
        existing = panes()
        result = []
        output = ''
        for task in tasks:
            session = name(task)
            row = {'id': task['id'], 'state': 'idle', 'exit_code': None, 'signal': None}
            if session in existing:
                dead, status, signal = (existing[session] + ['', '', ''])[:3]
                row.update(state='exited' if dead == '1' else 'running',
                           exit_code=int(status) if status.isdigit() else None,
                           signal=signal or None)
                log = ''
                if task['id'] == selected or task.get('ready_text'):
                    log = tmux('capture-pane', '-p', '-J', '-S', '-300', '-t', session + ':0.0').stdout[-100000:]
                if task['id'] == selected:
                    output = log
                if dead != '1' and task.get('ready_text') and task['ready_text'] in log:
                    row['state'] = 'ready_log'
                if dead == '1' and (row['exit_code'] not in (None, 0) or row['signal']):
                    row['state'] = 'failed'
            result.append(row)
        return {'sessions': result, 'output': output}

    tasks = payload['tasks']
    action = payload['action']
    target = payload.get('target')
    chosen = [t for t in tasks if t['id'] == target]
    if action in ('start', 'input', 'interrupt') and not chosen:
        raise ValueError('UNKNOWN_TASK')
    existing = panes()
    if action in ('start', 'start_all'):
        launching = chosen if action == 'start' else [t for t in tasks if t.get('enabled')]
        errors = []
        for task in launching:
            session = name(task)
            if session in existing and existing[session][0] != '1':
                continue  # Idempotent: never launch a second copy of a live task.
            if not task['command'].strip():
                errors.append(task['name'] + ': EMPTY_COMMAND')
                continue
            script = 'set -e\ncd -- ' + shlex.quote(os.path.expanduser(task['directory'])) + '\n'
            script += task['setup'] + '\n' + task['command']
            created = False
            try:
                if session not in existing:
                    tmux('new-session', '-d', '-s', session, '-x', '160', '-y', '30', 'sleep 60')
                    created = True
                    tmux('set-option', '-p', '-t', session + ':0.0', 'remain-on-exit', 'on')
                args = ['respawn-pane'] + (['-k'] if created else [])
                tmux(*args, '-t', session + ':0.0', 'bash', '-lc', script)
            except Exception as e:
                if created:
                    tmux('kill-session', '-t', session, check=False)
                errors.append(task['name'] + ': ' + str(e))
        result = snapshot(tasks, payload.get('selected'))
        result['errors'] = errors
        return result
    if action in ('input', 'interrupt'):
        session = name(chosen[0])
        if session not in existing or existing[session][0] == '1':
            raise ValueError('NOT_RUNNING')
        if action == 'interrupt':
            tmux('send-keys', '-t', session + ':0.0', 'C-c')
        else:
            text = payload.get('text', '')
            if not isinstance(text, str) or len(text) > 4096 or any(ord(c) < 32 for c in text):
                raise ValueError('INVALID_INPUT')
            if text:
                tmux('send-keys', '-t', session + ':0.0', '-l', '--', text)
            tmux('send-keys', '-t', session + ':0.0', 'Enter')
    return snapshot(tasks, payload.get('selected'))


if __name__ == '__main__':
    try:
        print(json.dumps(run(json.load(sys.stdin)), ensure_ascii=False))
    except Exception as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False))
