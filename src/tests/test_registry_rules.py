import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from registry_rules import is_protected_registry_key


class TestRegistryProtectedKeys(unittest.TestCase):
    def test_system_hive_is_protected(self):
        self.assertTrue(is_protected_registry_key('HKEY_LOCAL_MACHINE', 'SYSTEM\\CurrentControlSet'))

    def test_security_hive_is_protected(self):
        self.assertTrue(is_protected_registry_key('HKEY_LOCAL_MACHINE', 'SECURITY'))

    def test_sam_hive_is_protected(self):
        self.assertTrue(is_protected_registry_key('HKEY_LOCAL_MACHINE', 'SAM'))

    def test_run_key_is_protected(self):
        self.assertTrue(is_protected_registry_key(
            'HKEY_LOCAL_MACHINE', 'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run'))

    def test_winlogon_is_protected(self):
        self.assertTrue(is_protected_registry_key(
            'HKEY_LOCAL_MACHINE', 'SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon'))

    def test_hkey_users_is_entirely_protected(self):
        self.assertTrue(is_protected_registry_key('HKEY_USERS', 'anything_at_all'))

    def test_ordinary_app_settings_are_not_protected(self):
        self.assertFalse(is_protected_registry_key('HKEY_CURRENT_USER', 'Software\\MyPrinterApp\\Settings'))

    def test_ordinary_hklm_software_key_is_not_protected(self):
        self.assertFalse(is_protected_registry_key('HKEY_LOCAL_MACHINE', 'SOFTWARE\\MyPrinterApp'))

    def test_case_insensitive_matching(self):
        self.assertTrue(is_protected_registry_key('HKEY_LOCAL_MACHINE', 'system\\CurrentControlSet'))


if __name__ == '__main__':
    unittest.main()
