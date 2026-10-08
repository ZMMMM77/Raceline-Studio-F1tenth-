import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from PIL import Image
from raceline_studio.file_preview import preview, route_preview
from raceline_studio.remote import RemoteError
class Reader:
    def __init__(self,root):self.root=Path(root);self.sftp=self
    def read(self,path):return (self.root/path.lstrip('/')).read_bytes()
    def path(self,path):return path
    def stat(self,path):return (self.root/path.lstrip('/')).stat()
    def normalize(self,path):return str(Path(path))
class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.remote=Reader(self.root)
        Image.new('L',(30,20),200).save(self.root/'track.pgm')
        (self.root/'track.yaml').write_text('image: track.pgm\nresolution: 0.05\norigin: [-1, 2, 0.4]\n')
    def tearDown(self):self.tmp.cleanup()
    def test_yaml_loads_relative_pgm_and_origin(self):
        r=preview(self.remote,'/track.yaml');self.assertEqual(r['kind'],'map');self.assertTrue(r['map']['url'].startswith('data:image/png;base64,'));self.assertEqual(r['map']['origin'],[-1,2,.4])
    def test_image_automatically_matches_yaml(self):
        r=preview(self.remote,'/track.pgm');self.assertEqual(r['map']['resolution'],.05)
    def test_image_without_yaml_stays_previewable(self):
        (self.root/'track.yaml').unlink();r=preview(self.remote,'/track.pgm');self.assertNotIn('resolution',r['map'])
    def test_unrelated_yaml_does_not_replace_clicked_image(self):
        Image.new('L',(40,40)).save(self.root/'other.png');(self.root/'track.yaml').write_text('image: other.png\nresolution: 1\norigin: [0,0,0]')
        r=preview(self.remote,'/track.pgm');self.assertEqual(r['map']['width'],30);self.assertNotIn('resolution',r['map'])
    def test_bad_yaml_does_not_prevent_image_preview(self):
        (self.root/'track.yaml').write_text('bad yaml');self.assertNotIn('resolution',preview(self.remote,'/track.pgm')['map'])
    def test_csv_open_route_needs_no_width_or_closed_loop(self):
        r=route_preview(b'x,y,yaw,speed\n1,2,0,3\n2,3,0,4');self.assertEqual(r['points'],[[1,2],[2,3]])
    def test_mppi_and_comment_headers(self):
        self.assertEqual(route_preview(b'0;1;2;0;0;3;0;1;1\n1;2;3;0;0;3;0;1;1')['points'],[[1,2],[2,3]])
        self.assertEqual(route_preview(b'# y_m,x_m\n1,2\n3,4')['points'],[[2,1],[4,3]])
    def test_invalid_coordinates_and_format(self):
        for content,fmt in [(b'nan,1\n2,3','auto'),(b'1,2\n2,3','mppi'),(b'one,two','auto')]:
            with self.assertRaises(RemoteError):route_preview(content,fmt)
    def test_invalid_yaml_resolution(self):
        (self.root/'track.yaml').write_text('image: track.pgm\nresolution: -.1\norigin: [0,0,0]')
        with self.assertRaises(RemoteError):preview(self.remote,'/track.yaml')
