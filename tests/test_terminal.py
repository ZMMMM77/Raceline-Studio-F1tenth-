import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from flask import Flask
from raceline_studio.remote import RemoteError
from raceline_studio.terminal import Terminals, validate_config, install_terminals
from raceline_studio.terminal_agent import run
import threading

NS='a'*32
ID='b'*12

def task(**extra):
    return dict(id=ID,name='Localization',directory='~/a space',setup='source /opt/ros/setup.bash',command='printf ready',ready_text='ready',enabled=True,**extra)

class AgentTests(unittest.TestCase):
    def setUp(self):
        self.calls=[];self.existing={};self.logs={};self.missing=False
        self.patch=patch('raceline_studio.terminal_agent.shutil.which',return_value='/usr/bin/tmux');self.patch.start()
        self.proc=patch('raceline_studio.terminal_agent.subprocess.run',side_effect=self.tmux);self.proc.start()
    def tearDown(self):self.patch.stop();self.proc.stop()
    def tmux(self,args,**kwargs):
        self.calls.append(args);cmd=args[5];out='';err='';code=0
        if cmd=='list-panes':out='\n'.join(k+'\t'+v for k,v in self.existing.items())
        elif cmd=='new-session':self.existing[args[args.index('-s')+1]]='0\t\t'
        elif cmd=='capture-pane':out=self.logs.get(args[-1].removesuffix(':0.0'),'')
        return SimpleNamespace(stdout=out,stderr=err,returncode=code)
    def run_action(self,action='status',**extra):return run(dict(namespace=NS,tasks=[task()],action=action,selected=ID,target=ID,**extra))
    def test_start_is_idempotent_and_scoped(self):
        self.run_action('start');self.run_action('start')
        self.assertEqual(sum(c[5]=='new-session' for c in self.calls),1)
        self.assertTrue(all(c[:3]==['tmux','-L','raceline-studio'] for c in self.calls))
        respawn=next(c for c in self.calls if c[5]=='respawn-pane')
        self.assertEqual(respawn[-3:-1],['bash','-lc']);self.assertIn("cd -- '/",respawn[-1]);self.assertIn('a space',respawn[-1])
    def test_failure_exit_and_log(self):
        name='rs_'+NS+'_'+ID;self.existing[name]='1\t2\t';self.logs[name]='[ERROR] bad map'
        result=self.run_action();self.assertEqual(result['sessions'][0]['state'],'failed');self.assertEqual(result['sessions'][0]['exit_code'],2);self.assertIn('bad map',result['output'])
    def test_ready_requires_keyword_and_live_process(self):
        name='rs_'+NS+'_'+ID;self.existing[name]='0\t\t';self.logs[name]='ready'
        self.assertEqual(self.run_action()['sessions'][0]['state'],'ready_log')
        self.existing[name]='1\t0\t';self.assertEqual(self.run_action()['sessions'][0]['state'],'exited')
    def test_interrupt_targets_only_named_session(self):
        self.existing['rs_'+NS+'_'+ID]='0\t\t';self.run_action('interrupt')
        self.assertEqual(next(c for c in self.calls if c[5]=='send-keys')[-1],'C-c')
        self.assertFalse(any(c[5]=='kill-server' for c in self.calls))
    def test_literal_input_not_shell_interpolated(self):
        self.existing['rs_'+NS+'_'+ID]='0\t\t';self.run_action('input',text='$(touch /tmp/no)')
        literal=next(c for c in self.calls if '-l' in c)
        self.assertEqual(literal[-2:],['--','$(touch /tmp/no)'])
    def test_no_control_char_input(self):
        self.existing['rs_'+NS+'_'+ID]='0\t\t'
        with self.assertRaisesRegex(ValueError,'INVALID_INPUT'):self.run_action('input',text='x\ny')
    def test_missing_tmux_does_not_install(self):
        with patch('raceline_studio.terminal_agent.shutil.which',return_value=None):
            with self.assertRaisesRegex(ValueError,'TMUX_MISSING'):self.run_action('start')
        self.assertEqual(self.calls,[])
    def test_empty_start_reports_per_task_error(self):
        t=task();t['command']='';r=run(dict(namespace=NS,tasks=[t],action='start_all'))
        self.assertIn('EMPTY_COMMAND',r['errors'][0]);self.assertFalse(any(c[5]=='new-session' for c in self.calls))
    def test_shell_failure_not_masked(self):
        # This is the actual shell contract used by the helper: failed setup prevents launch.
        p=subprocess.Popen(['bash','-lc','set -e\nfalse\nprintf should-not-run'],stdout=subprocess.PIPE)
        out,_=p.communicate();self.assertNotEqual(p.returncode,0);self.assertEqual(out,b'')

class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.remote=Mock();self.remote.root=Path(self.tmp.name);self.remote.lock=threading.RLock();self.manager=Terminals(self.remote)
    def tearDown(self):self.tmp.cleanup()
    def test_config_persists_and_is_private(self):
        original=self.manager.config();data=self.manager.save({'tasks':[task()], 'namespace':'evil','name':'Track'})
        self.assertEqual(data['namespace'],original['namespace']);self.assertEqual(Terminals(self.remote).config(),data)
        self.assertEqual(self.manager.path.stat().st_mode&0o777,0o600)
    def test_duplicate_ids_and_bad_input_rejected(self):
        for data in ({'tasks':[task(),task()]},{'tasks':[{'id':'x; kill-server'}]},{'tasks':'no'}):
            with self.assertRaises(RemoteError):validate_config(data,NS)
    def test_disconnected_never_executes(self):
        self.remote.status.return_value={'connected':False}
        with self.assertRaisesRegex(RemoteError,'SSH_DISCONNECTED'):self.manager.call('start')
        self.remote.client.exec_command.assert_not_called()
    def test_active_recipe_cannot_be_removed(self):
        self.manager.save({'tasks':[task()]})
        with patch.object(self.manager,'call',return_value={'sessions':[{'id':ID,'state':'running'}]}):
            with self.assertRaises(RemoteError):self.manager.save({'tasks':[]})
        self.assertEqual(len(self.manager.config()['tasks']),1)
    def test_api_invalid_action(self):
        app=Flask(__name__);install_terminals(app,self.remote)
        response=app.test_client().post('/api/terminals/action',json={'action':'kill_all'})
        self.assertEqual(response.status_code,400);self.remote.client.exec_command.assert_not_called()

if __name__=='__main__':unittest.main()
