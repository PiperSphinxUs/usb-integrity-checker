import shutil
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from audit_log import append_audit_entry, read_audit_log
import i18n


class TestAuditLog(unittest.TestCase):
    def setUp(self):
        self.tmp = Path('/tmp/uic_test_audit')
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.tmp.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_appended_entry_can_be_read_back(self):
        append_audit_entry(self.tmp, 'scan', 'test_profile', {'ok': 5, 'missing': 1})
        entries = read_audit_log(self.tmp)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['event_type'], 'scan')
        self.assertEqual(entries[0]['profile_name'], 'test_profile')

    def test_entries_accumulate_append_only(self):
        append_audit_entry(self.tmp, 'scan', 'test_profile', {})
        append_audit_entry(self.tmp, 'repair_apply', 'test_profile', {})
        entries = read_audit_log(self.tmp)
        self.assertEqual(len(entries), 2)

    def test_entry_has_timestamp_and_actor(self):
        append_audit_entry(self.tmp, 'scan', 'test_profile', {})
        entries = read_audit_log(self.tmp)
        self.assertIn('timestamp', entries[0])
        self.assertIn('actor', entries[0])


class TestI18n(unittest.TestCase):
    def test_all_languages_have_the_same_keys_as_english(self):
        english_keys = set(i18n.STRINGS.keys())
        for lang in i18n.LANGUAGES:
            for key in english_keys:
                entry = i18n.STRINGS[key]
                self.assertIn(lang, entry, f"language '{lang}' is missing a translation for key '{key}'")

    def test_t_falls_back_to_english_when_translation_missing(self):
        result = i18n.t('app_name', lang='xx-nonexistent')
        self.assertEqual(result, i18n.t('app_name', lang='en'))

    def test_t_returns_key_itself_when_key_missing(self):
        result = i18n.t('this_key_does_not_exist_anywhere')
        self.assertEqual(result, 'this_key_does_not_exist_anywhere')

    def test_t_formats_placeholders_correctly(self):
        result = i18n.t('remove_profile_confirm', lang='en', name='MyProfile')
        self.assertIn('MyProfile', result)

    def test_t_does_not_crash_on_missing_format_args(self):
        result = i18n.t('remove_profile_confirm', lang='en')
        self.assertIsInstance(result, str)


if __name__ == '__main__':
    unittest.main()
