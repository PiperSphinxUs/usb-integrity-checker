import json
import platform
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
try:
    import winreg
    _WINREG_AVAILABLE = True
except ImportError:
    winreg = None
    _WINREG_AVAILABLE = False
HIVE_NAME_MAP = {'HKEY_CURRENT_USER': 'HKCU', 'HKEY_LOCAL_MACHINE': 'HKLM', 'HKEY_CLASSES_ROOT': 'HKCR', 'HKEY_USERS': 'HKU', 'HKEY_CURRENT_CONFIG': 'HKCC'}
PROTECTED_KEY_RULES = [('HKEY_LOCAL_MACHINE', 'system'), ('HKEY_LOCAL_MACHINE', 'security'), ('HKEY_LOCAL_MACHINE', 'sam'), ('HKEY_LOCAL_MACHINE', 'software\\microsoft\\windows\\currentversion\\run'), ('HKEY_LOCAL_MACHINE', 'software\\microsoft\\windows\\currentversion\\runonce'), ('HKEY_LOCAL_MACHINE', 'software\\microsoft\\windows nt\\currentversion\\winlogon'), ('HKEY_LOCAL_MACHINE', 'software\\policies'), ('HKEY_CURRENT_USER', 'software\\microsoft\\windows\\currentversion\\run'), ('HKEY_CURRENT_USER', 'software\\microsoft\\windows\\currentversion\\runonce'), ('HKEY_USERS', '')]

def is_protected_registry_key(hive_name: str, key_path: str) -> bool:
    key_lower = key_path.lower().strip('\\')
    for protected_hive, protected_prefix in PROTECTED_KEY_RULES:
        if hive_name != protected_hive:
            continue
        if protected_prefix == '':
            return True
        if key_lower.startswith(protected_prefix):
            return True
    return False
REG_TYPE_NAME_MAP = {}
SUPPORTED_CAPTURE_TYPES = set()
if _WINREG_AVAILABLE:
    REG_TYPE_NAME_MAP = {winreg.REG_SZ: 'REG_SZ', winreg.REG_EXPAND_SZ: 'REG_EXPAND_SZ', winreg.REG_DWORD: 'REG_DWORD'}
    SUPPORTED_CAPTURE_TYPES = set(REG_TYPE_NAME_MAP.keys())

class RegistryStatus(str, Enum):
    OK = 'ok'
    MISSING = 'missing'
    MISMATCHED = 'mismatched'
    PROTECTED = 'protected'
    UNSUPPORTED_OS = 'unsupported_os'

@dataclass
class RegistryScanResult:
    rule_id: str
    hive: str
    key_path: str
    value_name: str
    status: RegistryStatus
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None
    detail: str = ''
    detail_key: str = ''
    detail_params: dict = field(default_factory=dict)

    def to_dict(self):
        d = asdict(self)
        d['status'] = self.status.value
        return d

def _get_hive_constant(hive_name: str):
    mapping = {'HKEY_CURRENT_USER': winreg.HKEY_CURRENT_USER, 'HKEY_LOCAL_MACHINE': winreg.HKEY_LOCAL_MACHINE, 'HKEY_CLASSES_ROOT': winreg.HKEY_CLASSES_ROOT, 'HKEY_USERS': winreg.HKEY_USERS, 'HKEY_CURRENT_CONFIG': winreg.HKEY_CURRENT_CONFIG}
    if hive_name not in mapping:
        raise ValueError(f'Unknown hive: {hive_name}')
    return mapping[hive_name]

def read_registry_value(hive_name: str, key_path: str, value_name: str):
    if not _WINREG_AVAILABLE:
        raise RuntimeError('Registry Module only works on Windows (winreg not found)')
    hive = _get_hive_constant(hive_name)
    try:
        with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ) as key:
            value, reg_type = winreg.QueryValueEx(key, value_name)
            return (value, reg_type)
    except FileNotFoundError:
        return (None, None)

def write_registry_value(hive_name: str, key_path: str, value_name: str, value, reg_type: int):
    if not _WINREG_AVAILABLE:
        raise RuntimeError('Registry Module only works on Windows (winreg not found)')
    hive = _get_hive_constant(hive_name)
    with winreg.CreateKeyEx(hive, key_path, 0, winreg.KEY_WRITE) as key:
        winreg.SetValueEx(key, value_name, 0, reg_type, value)

def backup_registry_value(backup_dir: Path, hive_name: str, key_path: str, value_name: str, old_value, old_type: Optional[int]):
    backup_dir.mkdir(parents=True, exist_ok=True)
    log_path = backup_dir / 'registry_backup.jsonl'
    entry = {'timestamp': datetime.now().isoformat(timespec='seconds'), 'hive': hive_name, 'key_path': key_path, 'value_name': value_name, 'old_value': old_value, 'old_type': old_type}
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    return log_path

def capture_registry_subtree(hive_name: str, root_key_path: str, max_depth: int=10, max_rules: int=500) -> dict:
    if not _WINREG_AVAILABLE:
        raise RuntimeError('Registry Module only works on Windows (winreg not found)')
    if is_protected_registry_key(hive_name, root_key_path):
        raise PermissionError('This location is in the protected zone and cannot be captured')
    rules = []
    skipped_protected = []
    skipped_unsupported_type = 0
    truncated = {'value': False}

    def walk(key_path: str, depth: int):
        nonlocal skipped_unsupported_type
        if truncated['value'] or depth > max_depth:
            return
        if is_protected_registry_key(hive_name, key_path):
            skipped_protected.append(f'{hive_name}\\{key_path}')
            return
        hive = _get_hive_constant(hive_name)
        try:
            with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ) as key:
                i = 0
                while True:
                    try:
                        value_name, value, value_type = winreg.EnumValue(key, i)
                    except OSError:
                        break
                    i += 1
                    if len(rules) >= max_rules:
                        truncated['value'] = True
                        break
                    if value_type not in SUPPORTED_CAPTURE_TYPES:
                        skipped_unsupported_type += 1
                        continue
                    rules.append({'hive': hive_name, 'key_path': key_path, 'value_name': value_name or '(Default)', 'value_type': REG_TYPE_NAME_MAP[value_type], 'expected_value': str(value), 'action_on_mismatch': 'auto_repair'})
                subkeys = []
                j = 0
                while True:
                    try:
                        subkeys.append(winreg.EnumKey(key, j))
                    except OSError:
                        break
                    j += 1
        except (FileNotFoundError, PermissionError, OSError):
            return
        for sub in subkeys:
            walk(f'{key_path}\\{sub}' if key_path else sub, depth + 1)
    walk(root_key_path.strip('\\'), 0)
    return {'rules': rules, 'skipped_protected': skipped_protected, 'skipped_unsupported_type': skipped_unsupported_type, 'truncated': truncated['value']}

def find_candidate_keys(app_name_hint: str) -> list:
    if not _WINREG_AVAILABLE:
        return []
    hint_words = [w.lower() for w in app_name_hint.split() if len(w) > 1]
    if not hint_words:
        return []
    candidates = []
    roots = [('HKEY_CURRENT_USER', 'Software'), ('HKEY_LOCAL_MACHINE', 'SOFTWARE')]
    for hive_name, root_path in roots:
        hive = _get_hive_constant(hive_name)
        try:
            with winreg.OpenKey(hive, root_path, 0, winreg.KEY_READ) as root_key:
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(root_key, i)
                    except OSError:
                        break
                    i += 1
                    full_path = f'{root_path}\\{subkey_name}'
                    if is_protected_registry_key(hive_name, full_path):
                        continue
                    name_lower = subkey_name.lower()
                    if any((w in name_lower for w in hint_words)):
                        candidates.append((hive_name, full_path))
        except OSError:
            continue
    return candidates

def scan_registry_rule(rule: dict) -> RegistryScanResult:
    rule_id = rule['id']
    hive = rule['hive']
    key_path = rule['key_path']
    value_name = rule['value_name']
    expected_value = rule.get('expected_value')
    if platform.system() != 'Windows':
        return RegistryScanResult(rule_id=rule_id, hive=hive, key_path=key_path, value_name=value_name, status=RegistryStatus.UNSUPPORTED_OS, detail='Registry rules only work on Windows (this machine is not Windows)', detail_key='registry_detail_unsupported_os')
    if is_protected_registry_key(hive, key_path):
        return RegistryScanResult(rule_id=rule_id, hive=hive, key_path=key_path, value_name=value_name, status=RegistryStatus.PROTECTED, detail='This key is in the protected zone (core system / common malware target); checking/repairing is refused outright.', detail_key='registry_detail_protected')
    actual_value, actual_type = read_registry_value(hive, key_path, value_name)
    if actual_value is None:
        return RegistryScanResult(rule_id=rule_id, hive=hive, key_path=key_path, value_name=value_name, status=RegistryStatus.MISSING, expected_value=str(expected_value), detail='This key/value was not found on the machine', detail_key='registry_detail_missing')
    if str(actual_value) != str(expected_value):
        return RegistryScanResult(rule_id=rule_id, hive=hive, key_path=key_path, value_name=value_name, status=RegistryStatus.MISMATCHED, expected_value=str(expected_value), actual_value=str(actual_value), detail=f"Current value is '{actual_value}' but should be '{expected_value}'", detail_key='registry_detail_mismatched', detail_params={'actual': str(actual_value), 'expected': str(expected_value)})
    return RegistryScanResult(rule_id=rule_id, hive=hive, key_path=key_path, value_name=value_name, status=RegistryStatus.OK, expected_value=str(expected_value), actual_value=str(actual_value), detail='The value matches what was saved', detail_key='registry_detail_ok')

def repair_registry_rule(rule: dict, scan_result: RegistryScanResult, backup_dir: Path, apply: bool=False) -> dict:
    if scan_result.status in (RegistryStatus.PROTECTED, RegistryStatus.UNSUPPORTED_OS):
        return {'rule_id': rule['id'], 'success': False, 'message': scan_result.detail, 'message_key': scan_result.detail_key, 'message_params': scan_result.detail_params}
    if scan_result.status == RegistryStatus.OK:
        return {'rule_id': rule['id'], 'success': True, 'message': 'Value is already fine, nothing to do', 'message_key': 'registry_repair_msg_ok_skip', 'message_params': {}}
    hive = rule['hive']
    key_path = rule['key_path']
    value_name = rule['value_name']
    expected_value = rule.get('expected_value')
    reg_type = getattr(winreg, rule.get('value_type', 'REG_SZ'), None) if _WINREG_AVAILABLE else None
    if not apply:
        return {'rule_id': rule['id'], 'success': True, 'message': f"[DRY-RUN] Will set {hive}\\{key_path} -> {value_name} = '{expected_value}'", 'message_key': 'registry_repair_msg_dry_run', 'message_params': {'hive': hive, 'key_path': key_path, 'value_name': value_name, 'expected_value': str(expected_value)}}
    old_value, old_type = read_registry_value(hive, key_path, value_name)
    backup_path = backup_registry_value(backup_dir, hive, key_path, value_name, old_value, old_type)
    try:
        write_registry_value(hive, key_path, value_name, expected_value, reg_type)
        return {'rule_id': rule['id'], 'success': True, 'message': f"Repair succeeded: set {value_name} = '{expected_value}'", 'message_key': 'registry_repair_msg_success', 'message_params': {'value_name': value_name, 'expected_value': str(expected_value)}, 'backup_path': str(backup_path)}
    except OSError as e:
        return {'rule_id': rule['id'], 'success': False, 'message': f'Repair failed: {e}', 'message_key': 'repair_msg_failed', 'message_params': {'error': str(e)}}

def run_registry_scan(registry_rules: list) -> list:
    return [scan_registry_rule(rule) for rule in registry_rules]

def run_registry_repair(registry_rules: list, scan_results: list, backup_dir: Path, apply: bool=False) -> list:
    results_by_id = {r.rule_id: r for r in scan_results}
    outcomes = []
    for rule in registry_rules:
        scan_result = results_by_id[rule['id']]
        outcomes.append(repair_registry_rule(rule, scan_result, backup_dir, apply=apply))
    return outcomes
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Registry Rule Module - check/repair Windows Registry values')
    parser.add_argument('--profile', required=True, help='Path to the profile (.json) file containing registry_rules')
    parser.add_argument('--backup-dir', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    with open(args.profile, 'r', encoding='utf-8') as f:
        profile = json.load(f)
    registry_rules = profile.get('registry_rules', [])
    if not registry_rules:
        print('No registry_rules in this profile')
    else:
        scan_results = run_registry_scan(registry_rules)
        for r in scan_results:
            icon = {'ok': '[OK]', 'missing': '[MISSING]', 'mismatched': '[MISMATCH]', 'protected': '[PROTECTED]', 'unsupported_os': '[UNSUPPORTED]'}[r.status.value]
            print(f'{icon} [{r.rule_id}] {r.hive}\\{r.key_path} -> {r.value_name}: {r.status.value}')
            print(f'    {r.detail}')
        outcomes = run_registry_repair(registry_rules, scan_results, Path(args.backup_dir), apply=args.apply)
        print(f'\n=== {('apply' if args.apply else 'Dry-run')} ===')
        for o in outcomes:
            print(f'[{o['rule_id']}] {('[OK]' if o['success'] else '[FAILED]')} {o['message']}')
