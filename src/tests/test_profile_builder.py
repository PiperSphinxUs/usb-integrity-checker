import shutil
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from profile_builder import ProfileBuilder


class TestProfileBuilder(unittest.TestCase):
    def setUp(self):
        self.tmp = Path('/tmp/uic_test_builder')
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.tmp.mkdir(parents=True)
        self.ref_dir = self.tmp / 'ref'
        self.profiles_dir = self.tmp / 'profiles'

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_add_folder_captures_every_file_recursively(self):
        folder = self.tmp / 'app'
        (folder / 'sub').mkdir(parents=True)
        (folder / 'a.txt').write_text('a')
        (folder / 'sub' / 'b.txt').write_text('b')

        builder = ProfileBuilder(profile_name='builder_test', reference_dir=self.ref_dir,
                                 profiles_dir=self.profiles_dir, os_family='linux')
        builder.add_folder(str(folder))
        self.assertEqual(len(builder.rules), 2, 'must capture every file, including in subfolders')

    def test_personal_zone_skipped_by_default(self):
        import os
        home = self.tmp / 'home_sim'
        desktop = home / 'Desktop'
        desktop.mkdir(parents=True)
        (desktop / 'game_save.dat').write_text('save data')
        os.environ['HOME'] = str(home)

        builder = ProfileBuilder(profile_name='personal_test', reference_dir=self.ref_dir,
                                 profiles_dir=self.profiles_dir, os_family='linux')
        builder.add_folder(str(desktop))
        self.assertEqual(len(builder.rules), 0, 'personal-zone files must be skipped by default')
        self.assertEqual(len(builder.last_skipped_personal), 1)

    def test_personal_zone_included_when_explicitly_allowed(self):
        import os
        home = self.tmp / 'home_sim2'
        desktop = home / 'Desktop'
        desktop.mkdir(parents=True)
        (desktop / 'game_save.dat').write_text('save data')
        os.environ['HOME'] = str(home)

        builder = ProfileBuilder(profile_name='personal_allowed_test', reference_dir=self.ref_dir,
                                 profiles_dir=self.profiles_dir, os_family='linux')
        builder.add_folder(str(desktop), allow_personal_path=True)
        self.assertEqual(len(builder.rules), 1, 'must capture the file when the user explicitly allows the personal zone')

    def test_anchor_path_is_portable_not_absolute(self):
        import os
        home = self.tmp / 'home_sim3'
        app_dir = home / 'myapp'
        app_dir.mkdir(parents=True)
        (app_dir / 'x.txt').write_text('x')
        os.environ['HOME'] = str(home)

        builder = ProfileBuilder(profile_name='anchor_test', reference_dir=self.ref_dir,
                                 profiles_dir=self.profiles_dir, os_family='linux')
        builder.add_folder(str(app_dir))
        expected_location = builder.rules[0]['expected_location']
        self.assertNotEqual(expected_location, str(app_dir / 'x.txt'),
                            'files under $HOME must be converted to an anchor path ({HOME}/...), not a literal path')
        self.assertIn('{HOME}', expected_location)


    def test_created_os_version_is_recorded_in_saved_profile(self):
        folder = self.tmp / 'app3'
        folder.mkdir()
        (folder / 'x.txt').write_text('x')
        builder = ProfileBuilder(profile_name='os_version_test', reference_dir=self.ref_dir,
                                 profiles_dir=self.profiles_dir, os_family='linux')
        builder.add_folder(str(folder))
        out_path = builder.save()
        import json
        data = json.loads(out_path.read_text())
        self.assertIn('created_os_version', data)
        self.assertTrue(data['created_os_version'], 'must record the OS version of the machine that created the profile')


if __name__ == '__main__':
    unittest.main()
