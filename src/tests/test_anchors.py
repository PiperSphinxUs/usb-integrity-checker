import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from anchors import to_anchor_path, resolve_anchor_path, is_in_personal_zone, os_version_looks_compatible


class TestAnchors(unittest.TestCase):
    def test_home_path_becomes_anchor(self):
        import os
        os.environ['HOME'] = '/home/testuser'
        anchor = to_anchor_path('/home/testuser/app/config.ini', os_family='linux')
        self.assertEqual(anchor, '{HOME}/app/config.ini')

    def test_anchor_resolves_back_to_real_path(self):
        import os
        os.environ['HOME'] = '/home/testuser'
        real_path = resolve_anchor_path('{HOME}/app/config.ini', os_family='linux')
        self.assertEqual(str(real_path), str(Path('/home/testuser/app/config.ini')))

    def test_round_trip_conversion_is_consistent(self):
        import os
        os.environ['HOME'] = '/home/testuser'
        original = '/home/testuser/data/file.txt'
        anchor = to_anchor_path(original, os_family='linux')
        resolved = resolve_anchor_path(anchor, os_family='linux')
        self.assertEqual(str(resolved), str(Path(original)))

    def test_desktop_is_personal_zone(self):
        import os
        os.environ['HOME'] = '/home/testuser'
        self.assertTrue(is_in_personal_zone(Path('/home/testuser/Desktop/file.txt'), os_family='linux'))

    def test_documents_is_personal_zone(self):
        import os
        os.environ['HOME'] = '/home/testuser'
        self.assertTrue(is_in_personal_zone(Path('/home/testuser/Documents/report.docx'), os_family='linux'))

    def test_program_folder_is_not_personal_zone(self):
        import os
        os.environ['HOME'] = '/home/testuser'
        self.assertFalse(is_in_personal_zone(Path('/opt/myapp/config.ini'), os_family='linux'))

    def test_matching_os_version_is_compatible(self):
        self.assertTrue(os_version_looks_compatible('Windows 11', 'Windows 11 Pro 23H2 (Build 22631.2861)'))

    def test_mismatched_os_version_is_flagged(self):
        self.assertFalse(os_version_looks_compatible('Windows 11', 'Windows 10 Home (Build 19045.1)'))


if __name__ == '__main__':
    unittest.main()
