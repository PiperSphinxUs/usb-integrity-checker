import hashlib
import json
import os
import platform
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
from anchors import resolve_anchor_path, detect_current_os_family, detect_current_os_version_label, os_version_looks_compatible

class RuleStatus(str, Enum):
    OK = 'ok'
    MISSING = 'missing'
    CORRUPTED = 'corrupted'
    MISPLACED = 'misplaced'
    REF_BROKEN = 'ref_broken'

@dataclass
class ScanResult:
    rule_id: str
    watch_file: str
    expected_location: str
    status: RuleStatus
    resolved_location: Optional[str] = None
    found_location: Optional[str] = None
    expected_hash: Optional[str] = None
    actual_hash: Optional[str] = None
    detail: str = ''
    detail_key: str = ''
    detail_params: dict = field(default_factory=dict)

    def to_dict(self):
        d = asdict(self)
        d['status'] = self.status.value
        return d

@dataclass
class ScanReport:
    profile_name: str
    scanned_at: str
    os_name: str
    profile_os_type: str = ''
    detected_os_version: str = ''
    os_mismatch: bool = False
    os_version_mismatch: bool = False
    results: list = field(default_factory=list)
    unknown_files: list = field(default_factory=list)

    def summary(self):
        counts = {s.value: 0 for s in RuleStatus}
        for r in self.results:
            counts[r.status.value] += 1
        return counts

    def to_dict(self):
        return {'profile_name': self.profile_name, 'scanned_at': self.scanned_at, 'os_name': self.os_name, 'profile_os_type': self.profile_os_type, 'detected_os_version': self.detected_os_version, 'os_mismatch': self.os_mismatch, 'os_version_mismatch': self.os_version_mismatch, 'summary': self.summary(), 'results': [r.to_dict() for r in self.results], 'unknown_files': self.unknown_files}

def compute_sha256(filepath: Path, chunk_size: int=65536) -> Optional[str]:
    if not filepath.is_file():
        return None
    h = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(chunk_size), b''):
                h.update(chunk)
        return h.hexdigest()
    except (PermissionError, OSError):
        return None

def load_profile(profile_path: Path) -> dict:
    with open(profile_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def verify_reference_files(rules: list, reference_dir: Path) -> dict:
    status = {}
    for rule in rules:
        ref_id = rule['reference_id']
        ref_file = reference_dir / rule.get('reference_filename', f'{ref_id}.bin')
        expected_hash = rule.get('expected_hash')
        actual_hash = compute_sha256(ref_file)
        if actual_hash is None:
            status[ref_id] = False
        elif expected_hash and actual_hash != expected_hash:
            status[ref_id] = False
        else:
            status[ref_id] = True
    return status

def find_file_anywhere(filename: str, search_roots: list, max_depth: int=6) -> Optional[Path]:
    for root in search_roots:
        root_path = Path(root)
        if not root_path.exists():
            continue
        base_depth = len(root_path.parts)
        for dirpath, dirnames, filenames in os.walk(root_path):
            current_depth = len(Path(dirpath).parts) - base_depth
            if current_depth >= max_depth:
                dirnames[:] = []
                continue
            if filename in filenames:
                return Path(dirpath) / filename
    return None

def scan_rule(rule: dict, reference_dir: Path, ref_ok: bool, search_roots: Optional[list]=None, os_family: Optional[str]=None, custom_anchors: Optional[dict]=None, offline_root: Optional[str]=None) -> ScanResult:
    rule_id = rule['id']
    watch_file = rule['watch_file']
    expected_location = rule['expected_location']
    reference_id = rule['reference_id']
    if not ref_ok:
        return ScanResult(rule_id=rule_id, watch_file=watch_file, expected_location=expected_location, status=RuleStatus.REF_BROKEN, detail='The reference file on the USB itself is damaged and cannot be used to check/repair. Please repair the USB first.', detail_key='detail_ref_broken')
    ref_file = reference_dir / rule.get('reference_filename', f'{reference_id}.bin')
    expected_hash = compute_sha256(ref_file)
    expected_path = resolve_anchor_path(expected_location, os_family, custom_anchors, offline_root)
    actual_hash_at_expected = compute_sha256(expected_path)
    if actual_hash_at_expected == expected_hash:
        return ScanResult(rule_id=rule_id, watch_file=watch_file, expected_location=expected_location, status=RuleStatus.OK, resolved_location=str(expected_path), found_location=str(expected_path), expected_hash=expected_hash, actual_hash=actual_hash_at_expected, detail='The file is correct and in the right location.', detail_key='detail_ok')
    if expected_path.is_file() and actual_hash_at_expected != expected_hash:
        return ScanResult(rule_id=rule_id, watch_file=watch_file, expected_location=expected_location, status=RuleStatus.CORRUPTED, resolved_location=str(expected_path), found_location=str(expected_path), expected_hash=expected_hash, actual_hash=actual_hash_at_expected, detail='The file was found in the correct location, but its content does not match the original (it may have been modified or damaged).', detail_key='detail_corrupted')
    if search_roots:
        found = find_file_anywhere(watch_file, search_roots)
        if found is not None:
            found_hash = compute_sha256(found)
            if found_hash == expected_hash:
                return ScanResult(rule_id=rule_id, watch_file=watch_file, expected_location=expected_location, status=RuleStatus.MISPLACED, resolved_location=str(expected_path), found_location=str(found), expected_hash=expected_hash, actual_hash=found_hash, detail=f'A correct copy of the file was found, but in the wrong location (found at {found}).', detail_key='detail_misplaced', detail_params={'found': str(found)})
    return ScanResult(rule_id=rule_id, watch_file=watch_file, expected_location=expected_location, status=RuleStatus.MISSING, resolved_location=str(expected_path), expected_hash=expected_hash, actual_hash=None, detail='This file was not found on the machine, either at the expected location or nearby.', detail_key='detail_missing')

def find_unknown_files(watched_folders: list, known_paths: set, os_family: str, custom_anchors: Optional[dict]=None, offline_root: Optional[str]=None) -> list:
    unknown = []
    for anchor_folder in watched_folders:
        real_folder = resolve_anchor_path(anchor_folder, os_family, custom_anchors, offline_root)
        if not real_folder.is_dir():
            continue
        for file_path in real_folder.rglob('*'):
            if file_path.is_file():
                normalized = str(file_path.resolve())
                if normalized not in known_paths:
                    unknown.append(normalized)
    return unknown

def run_scan(profile_path: Path, reference_dir: Path, search_roots: Optional[list]=None, offline_root: Optional[str]=None) -> ScanReport:
    profile = load_profile(profile_path)
    rules = profile['rules']
    os_family = profile.get('os_family', 'windows')
    profile_os_type = profile.get('os_type', '')
    custom_anchors = profile.get('custom_anchors', {})
    current_os_family = detect_current_os_family()
    os_mismatch = not offline_root and current_os_family != 'unknown' and (os_family != 'custom') and (current_os_family != os_family)
    detected_version = detect_current_os_version_label()
    os_version_mismatch = not os_mismatch and os_family != 'custom' and (not os_version_looks_compatible(profile_os_type, detected_version))
    ref_status = verify_reference_files(rules, reference_dir)
    results = []
    for rule in rules:
        ref_ok = ref_status.get(rule['reference_id'], False)
        result = scan_rule(rule, reference_dir, ref_ok, search_roots, os_family=os_family, custom_anchors=custom_anchors, offline_root=offline_root)
        results.append(result)
    known_paths = {str(Path(r.resolved_location).resolve()) for r in results if r.resolved_location}
    watched_folders = profile.get('watched_folders', [])
    unknown_files = find_unknown_files(watched_folders, known_paths, os_family, custom_anchors, offline_root) if watched_folders else []
    report = ScanReport(profile_name=profile.get('profile_name', profile_path.stem), scanned_at=datetime.now().isoformat(timespec='seconds'), os_name=platform.system(), profile_os_type=profile_os_type, detected_os_version=detected_version, os_mismatch=os_mismatch, os_version_mismatch=os_version_mismatch, results=results, unknown_files=unknown_files)
    return report
if __name__ == '__main__':
    import argparse
    from audit_log import append_audit_entry
    parser = argparse.ArgumentParser(description='USB Integrity Checker - Scanner Module')
    parser.add_argument('--profile', required=True, help='Path to the profile (.json) file')
    parser.add_argument('--reference-dir', required=True, help='Path to the reference_files folder')
    parser.add_argument('--search-root', action='append', default=None, help='Folder(s) to search for misplaced files (can be repeated)')
    parser.add_argument('--json-out', help='If given, write results as a JSON file at this path')
    parser.add_argument('--logs-dir', default=None, help='Audit log folder (if given, every run is logged automatically, no need for --json-out)')
    parser.add_argument('--offline-root', default=None, help='Used when booting directly from USB: the path where the target drive is mounted (e.g. /mnt/target or D:\\\\), instead of scanning the currently running machine directly')
    args = parser.parse_args()
    report = run_scan(profile_path=Path(args.profile), reference_dir=Path(args.reference_dir), search_roots=args.search_root, offline_root=args.offline_root)
    print(f'\n=== Scan results: {report.profile_name} ===')
    print(f'Time: {report.scanned_at} | This machine: {report.detected_os_version} | Profile for: {report.profile_os_type}\n')
    if report.os_mismatch:
        print('WARNING: This profile was created for a different OS family; scan results may be inaccurate!\n')
    elif report.os_version_mismatch:
        print(f"NOTE: This profile was created for '{report.profile_os_type}' but this machine appears to be '{report.detected_os_version}' - most paths should still work, but minor details (e.g. some registry keys) may differ slightly. Review results before repairing.\n")
    for r in report.results:
        icon = {'ok': '[OK]', 'missing': '[MISSING]', 'corrupted': '[CORRUPTED]', 'misplaced': '[MISPLACED]', 'ref_broken': '[REF_BROKEN]'}[r.status.value]
        print(f'{icon} [{r.rule_id}] {r.watch_file}: {r.status.value}')
        print(f'    {r.detail}')
    print('\nSummary:', report.summary())
    if report.unknown_files:
        print(f'\nFound {len(report.unknown_files)} unknown file(s) in watched folder(s) (not in the baseline - review yourself, this is NOT confirmation of a virus):')
        for f in report.unknown_files:
            print(f'    - {f}')
    if args.json_out:
        with open(args.json_out, 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
        print(f'\nSaved report as JSON to: {args.json_out}')
    if args.logs_dir:
        append_audit_entry(logs_dir=Path(args.logs_dir), event_type='scan', profile_name=report.profile_name, summary=report.summary())
