import io
import json
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from flask import Flask
from raceline_studio.remote import Remote, RemoteError, digest, install_remote

class SFTP:
    def __init__(self, root): self.root=Path(root)
    def file(self,p): return self.root/p.lstrip('/')
    def lstat(self,p): return self.file(p).lstat()
    def stat(self,p): return self.file(p).stat()
    def open(self,p,m): return self.file(p).open('xb' if m=='wx' else m)
    def chmod(self,p,m): self.file(p).chmod(m)
    def posix_rename(self,a,b): self.file(a).replace(self.file(b))
    def rename(self,a,b):
        if self.file(b).exists(): raise FileExistsError(b)
        self.file(a).rename(self.file(b))
    def remove(self,p): self.file(p).unlink()
    def normalize(self,p): return '/'
    def close(self): pass

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.remote=Remote(self.root,vault=Mock());self.remote.sftp=SFTP(self.root)
        self.remote.client=Mock()
    def tearDown(self): self.remote.close();self.tmp.cleanup()
    def test_save_new(self):
        r=self.remote.save('/new.csv',b'1,2,3\n')
        self.assertIsNone(r['backup']);self.assertEqual((self.root/'new.csv').read_bytes(),b'1,2,3\n')
    def test_overwrite_requires_revision_and_preserves_backup(self):
        p=self.root/'a.csv';p.write_bytes(b'old');p.chmod(0o640)
        with self.assertRaises(RemoteError) as ctx:self.remote.save('/a.csv',b'new')
        self.assertEqual(ctx.exception.details['revision'],digest(b'old'))
        self.assertEqual(p.read_bytes(),b'old')
        r=self.remote.save('/a.csv',b'new',digest(b'old'))
        self.assertEqual((self.root/r['backup'].lstrip('/')).read_bytes(),b'old')
        self.assertEqual(p.read_bytes(),b'new');self.assertEqual(stat.S_IMODE(p.stat().st_mode),0o640)
    def test_stale_revision_and_symlink(self):
        (self.root/'a.csv').write_bytes(b'changed')
        with self.assertRaises(RemoteError):self.remote.save('/a.csv',b'new',digest(b'old'))
        (self.root/'link.csv').symlink_to(self.root/'a.csv')
        with self.assertRaises(RemoteError):self.remote.save('/link.csv',b'new',digest(b'changed'))
    def test_rename_failure_keeps_original(self):
        (self.root/'a.csv').write_bytes(b'old')
        with patch.object(self.remote.sftp,'posix_rename',side_effect=OSError('unsupported')):
            with self.assertRaises(OSError):self.remote.save('/a.csv',b'new',digest(b'old'))
        self.assertEqual((self.root/'a.csv').read_bytes(),b'old')
        self.assertFalse(list(self.root.glob('*.tmp-*')))
    def test_read_limit(self):
        (self.root/'a.csv').write_bytes(b'abcd')
        with patch('raceline_studio.remote.LIMIT',3):
            with self.assertRaises(RemoteError):self.remote.read('/a.csv')
    def test_connect_persists_no_password(self):
        ssh=Mock();ssh.open_sftp.return_value.normalize.return_value='/home/jetson'
        ssh.save_host_keys.side_effect=lambda p:Path(p).write_text('host key')
        with patch('raceline_studio.remote.paramiko.SSHClient',return_value=ssh):
            self.remote.connect(dict(host='jetson.local',username='jetson',password='secret',auto_connect=True))
        self.remote.vault.set_password.assert_called_once()
        self.assertNotIn('secret',self.remote.config_path.read_text())
        self.assertNotIn('password',self.remote.status()['profile'])
    def test_failed_auth_does_not_store_password(self):
        ssh=Mock();ssh.connect.side_effect=OSError('offline')
        with patch('raceline_studio.remote.paramiko.SSHClient',return_value=ssh):
            with self.assertRaises(OSError): self.remote.connect(dict(host='car',username='u',password='secret'))
        self.remote.vault.set_password.assert_not_called();self.assertFalse(self.remote.config_path.exists())
    def test_api_blocks_local_path_traversal(self):
        app=Flask(__name__);remote=install_remote(app,self.root);remote.client=Mock();remote.sftp=SFTP(self.root)
        with app.test_client() as c:
            for source in ['/etc/passwd','/outputs/../app.csv','/outputs/test/../app.csv']:
                r=c.post('/api/remote/save',json={'path':'/a.csv','source':source})
                self.assertEqual(r.status_code,400)
        remote.close()

if __name__=='__main__':unittest.main()
