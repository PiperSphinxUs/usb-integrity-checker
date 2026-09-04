import shutil
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from profile_builder import ProfileBuilder
from scanner import run_scan, RuleStatus


class TestScanner(unittest.TestCase):
    def setUp(self):
        self.tmp = Path('/tmp/uic_test_scanner')
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.tmp.mkdir(parents=True)
        self.watched = self.tmp / 'app'
        self.watched.mkdir()
        (self.watched / 'config.ini').write_text('setting=1')
        self.ref_dir = self.tmp / 'ref'
        self.profiles_dir = self.tmp / 'profiles'

        self.builder = ProfileBuilder(
            profile_name='scanner_test', reference_dir=self.ref_dir,
            profiles_dir=self.profiles_dir, os_family='linux',
        )
        self.builder.add_folder(str(self.watched))
        self.profile_path = self.builder.save()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_ok_status_when_unchanged(self):
        report = run_scan(self.profile_path, self.ref_dir)
        self.assertEqual(report.results[0].status, RuleStatus.OK)

    def test_corrupted_status_when_content_changed(self):
        (self.watched / 'config.ini').write_text('TAMPERED')
        report = run_scan(self.profile_path, self.ref_dir)
        self.assertEqual(report.results[0].status, RuleStatus.CORRUPTED)

    def test_missing_status_when_file_deleted(self):
        (self.watched / 'config.ini').unlink()
        report = run_scan(self.profile_path, self.ref_dir)
        self.assertEqual(report.results[0].status, RuleStatus.MISSING)

    def test_misplaced_status_when_moved(self):
        moved_dir = self.tmp / 'elsewhere'
        moved_dir.mkdir()
        original = self.watched / 'config.ini'
        shutil.move(str(original), str(moved_dir / 'config.ini'))
        report = run_scan(self.profile_path, self.ref_dir, search_roots=[str(moved_dir)])
        self.assertEqual(report.results[0].status, RuleStatus.MISPLACED)

    def test_ref_broken_when_reference_file_corrupted(self):
        ref_files = list(self.ref_dir.glob('*.bin'))
        self.assertTrue(ref_files, 'should have at least one reference file')
        ref_files[0].write_text('CORRUPTED REFERENCE')
        report = run_scan(self.profile_path, self.ref_dir)
        self.assertEqual(report.results[0].status, RuleStatus.REF_BROKEN)

    def test_detail_key_is_populated_for_i18n(self):
        report = run_scan(self.profile_path, self.ref_dir)
        self.assertTrue(report.results[0].detail_key, 'must have a detail_key so the GUI can translate it')

    def test_unknown_file_detection(self):
        (self.watched / 'surprise.txt').write_text('unexpected file')
        report = run_scan(self.profile_path, self.ref_dir)
        self.assertIn(str(self.watched / 'surprise.txt'), [str(Path(p)) for p in report.unknown_files])


if __name__ == '__main__':
    unittest.main()
