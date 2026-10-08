import json,tempfile,unittest
from pathlib import Path
from raceline_studio.remote_paths import read_paths
class PathTests(unittest.TestCase):
    def test_reads_edited_paths_immediately(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'remote_paths.json';self.assertEqual(read_paths(t)['waypoint_directory'],'~')
            p.write_text(json.dumps({'waypoint_directory':'/home/jetson/waypoints','map_directory':'/home/jetson/maps'}));self.assertEqual(read_paths(t)['map_directory'],'/home/jetson/maps')
            p.write_text(json.dumps({'map_directory':'~/new_maps'}));self.assertEqual(read_paths(t)['map_directory'],'~/new_maps')
    def test_rejects_invalid_config(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'remote_paths.json'
            for data in [[],{'map_directory':None},{'waypoint_directory':''}]:
                p.write_text(json.dumps(data))
                with self.assertRaises(ValueError):read_paths(t)
