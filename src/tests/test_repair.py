import shutil
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from profile_builder import ProfileBuilder
from scanner import run_scan
from repair import run_repair


class TestRepair(unittest.TestCase):
    def setUp(self):
        self.tmp = Path('/tmp/uic_test_repair')
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.tmp.mkdir(parents=True)
        self.watched = self.tmp / 'app'
        self.watched.mkdir()
        (self.watched / 'config.ini').write_text('setting=1')
        self.ref_dir = self.tmp / 'ref'
        self.profiles_dir = self.tmp / 'profiles'
        self.backup_dir = self.tmp / 'backup'

        self.builder = ProfileBuilder(
            profile_name='repair_test', reference_dir=self.ref_dir,
            profiles_dir=self.profiles_dir, os_family='linux',
        )
        self.builder.add_folder(str(self.watched))
        self.profile_path = self.builder.save()
        self.rules_by_id = {r['id']: r for r in self.builder.rules}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_dry_run_does_not_modify_file(self):
        (self.watched / 'config.ini').write_text('TAMPERED')
        report = run_scan(self.profile_path, self.ref_dir)
        run_repair(report.results, self.rules_by_id, self.ref_dir, self.backup_dir,
                   apply=False, os_family='linux')
        self.assertEqual((self.watched / 'config.ini').read_text(), 'TAMPERED',
                         'dry-run must never touch the real file')

    def test_apply_restores_corrupted_file(self):
        (self.watched / 'config.ini').write_text('TAMPERED')
        report = run_scan(self.profile_path, self.ref_dir)
        result = run_repair(report.results, self.rules_by_id, self.ref_dir, self.backup_dir,
                            apply=True, os_family='linux')
        self.assertTrue(result['outcomes'][0]['success'])
        self.assertEqual((self.watched / 'config.ini').read_text(), 'setting=1')

    def test_apply_creates_backup_before_overwrite(self):
        (self.watched / 'config.ini').write_text('TAMPERED')
        report = run_scan(self.profile_path, self.ref_dir)
        run_repair(report.results, self.rules_by_id, self.ref_dir, self.backup_dir,
                  apply=True, os_family='linux')
        backups = list(self.backup_dir.glob('*.bak'))
        self.assertTrue(backups, 'a backup file must always be created before overwriting')

    def test_repair_restores_missing_file(self):
        (self.watched / 'config.ini').unlink()
        report = run_scan(self.profile_path, self.ref_dir)
        result = run_repair(report.results, self.rules_by_id, self.ref_dir, self.backup_dir,
                            apply=True, os_family='linux')
        self.assertTrue(result['outcomes'][0]['success'])
        self.assertTrue((self.watched / 'config.ini').exists())

    def test_personal_zone_is_never_touched(self):
        # Simulate a personal-zone file directly (bypassing profile-creation guard) to
        # verify the Repair module has its own independent safety layer, not just profile creation
        home = self.tmp / 'home_sim'
        desktop = home / 'Desktop'
        desktop.mkdir(parents=True)
        (desktop / 'personal.txt').write_text('original')

        rule = {
            'id': 'rule_personal', 'watch_file': 'personal.txt',
            'expected_location': str(desktop / 'personal.txt'),
            'reference_id': 'ref_personal', 'reference_filename': 'ref_personal.bin',
            'expected_hash': 'anyhash', 'action_on_mismatch': 'auto_repair',
            'allow_personal_path': False,
        }
        rules_by_id = {'rule_personal': rule}

        import os
        os.environ['HOME'] = str(home)
        from scanner import ScanResult, RuleStatus
        fake_result = ScanResult(
            rule_id='rule_personal', watch_file='personal.txt',
            expected_location=str(desktop / 'personal.txt'), status=RuleStatus.CORRUPTED,
            resolved_location=str(desktop / 'personal.txt'),
        )
        run_repair([fake_result], rules_by_id, self.ref_dir, self.backup_dir,
                  apply=True, os_family='linux')
        self.assertEqual((desktop / 'personal.txt').read_text(), 'original',
                         'personal-zone files must never be touched, even when repair is applied')


if __name__ == '__main__':
    unittest.main()
