import json
import shutil
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from scanner import ScanResult, RuleStatus, compute_sha256
from anchors import is_in_personal_zone

class RepairAction(str):
    RESTORE_MISSING = 'restore_missing'
    OVERWRITE_CORRUPTED = 'overwrite_corrupted'
    MOVE_MISPLACED = 'move_misplaced'
    SKIP = 'skip'
    BLOCKED_PERSONAL_ZONE = 'blocked_personal_zone'

@dataclass
class RepairPlanItem:
    rule_id: str
    action: str
    source: Optional[str]
    destination: Optional[str]
    backup_path: Optional[str] = None
    reason: str = ''
    reason_key: str = ''
    reason_params: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)

@dataclass
class RepairOutcome:
    rule_id: str
    action: str
    success: bool
    message: str
    backup_path: Optional[str] = None
    message_key: str = ''
    message_params: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)

def build_repair_plan(scan_result: ScanResult, reference_dir: Path, rule: dict, os_family: str='windows', custom_anchors: Optional[dict]=None, offline_root: Optional[str]=None) -> RepairPlanItem:
    ref_file = reference_dir / rule.get('reference_filename', f'{rule['reference_id']}.bin')
    allow_personal = rule.get('allow_personal_path', False)
    destination_check = scan_result.resolved_location or scan_result.expected_location
    if destination_check and (not allow_personal) and is_in_personal_zone(Path(destination_check), os_family, custom_anchors, offline_root):
        return RepairPlanItem(rule_id=scan_result.rule_id, action=RepairAction.BLOCKED_PERSONAL_ZONE, source=None, destination=destination_check, reason=f"Repair refused: destination '{destination_check}' is in a personal folder (Desktop/Documents/Downloads or HOME root). This type of file will never be touched, to protect personal/work files.", reason_key='repair_reason_blocked_personal', reason_params={'destination': str(destination_check)})
    if scan_result.status == RuleStatus.OK:
        return RepairPlanItem(rule_id=scan_result.rule_id, action=RepairAction.SKIP, source=None, destination=None, reason='The file is already fine, nothing to do.', reason_key='repair_reason_ok_skip')
    if scan_result.status == RuleStatus.REF_BROKEN:
        return RepairPlanItem(rule_id=scan_result.rule_id, action=RepairAction.SKIP, source=None, destination=None, reason='The reference file on the USB itself is damaged; refusing to repair for safety.', reason_key='repair_reason_ref_broken')
    destination = scan_result.resolved_location or scan_result.expected_location
    if scan_result.status == RuleStatus.MISSING:
        return RepairPlanItem(rule_id=scan_result.rule_id, action=RepairAction.RESTORE_MISSING, source=str(ref_file), destination=destination, reason='File not found on this machine; will copy it from the original to the correct location.', reason_key='repair_reason_missing')
    if scan_result.status == RuleStatus.CORRUPTED:
        return RepairPlanItem(rule_id=scan_result.rule_id, action=RepairAction.OVERWRITE_CORRUPTED, source=str(ref_file), destination=destination, reason='The file at the correct location has different content; will back it up and overwrite with the original.', reason_key='repair_reason_corrupted')
    if scan_result.status == RuleStatus.MISPLACED:
        return RepairPlanItem(rule_id=scan_result.rule_id, action=RepairAction.MOVE_MISPLACED, source=scan_result.found_location, destination=destination, reason=f'A correct copy of the file was found in the wrong location (at {scan_result.found_location}); will move it to the correct location.', reason_key='repair_reason_misplaced', reason_params={'found': str(scan_result.found_location)})
    return RepairPlanItem(rule_id=scan_result.rule_id, action=RepairAction.SKIP, source=None, destination=None, reason=f'Unknown status ({scan_result.status}); skipping for safety.', reason_key='repair_reason_unknown_status', reason_params={'status': str(scan_result.status)})

def make_backup(target_path: Path, backup_dir: Path) -> Optional[Path]:
    if not target_path.is_file():
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = backup_dir / f'{target_path.name}.{ts}.bak'
    shutil.copy2(target_path, backup_path)
    return backup_path

def execute_repair_item(plan_item: RepairPlanItem, backup_dir: Path, apply: bool) -> RepairOutcome:
    if plan_item.action == RepairAction.SKIP:
        return RepairOutcome(rule_id=plan_item.rule_id, action=plan_item.action, success=True, message=plan_item.reason, message_key=plan_item.reason_key, message_params=plan_item.reason_params)
    if plan_item.action == RepairAction.BLOCKED_PERSONAL_ZONE:
        return RepairOutcome(rule_id=plan_item.rule_id, action=plan_item.action, success=False, message=plan_item.reason, message_key=plan_item.reason_key, message_params=plan_item.reason_params)
    destination = Path(plan_item.destination)
    source = Path(plan_item.source)
    if not apply:
        would_backup = destination.is_file()
        return RepairOutcome(rule_id=plan_item.rule_id, action=plan_item.action, success=True, message=f"[DRY-RUN] Will {_action_verb(plan_item.action)} from '{source}' to '{destination}'" + (' (will back up the existing file first)' if would_backup else ''), message_key='repair_msg_dry_run', message_params={'action': plan_item.action, 'source': str(source), 'destination': str(destination), 'would_backup': would_backup})
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        backup_path = make_backup(destination, backup_dir)
        if not source.is_file():
            return RepairOutcome(rule_id=plan_item.rule_id, action=plan_item.action, success=False, message=f"Repair cancelled: source file '{source}' not found", message_key='repair_msg_source_missing', message_params={'source': str(source)}, backup_path=str(backup_path) if backup_path else None)
        if plan_item.action == RepairAction.MOVE_MISPLACED:
            shutil.move(str(source), str(destination))
        else:
            shutil.copy2(source, destination)
        if compute_sha256(destination) != compute_sha256(source if plan_item.action != RepairAction.MOVE_MISPLACED else destination):
            pass
        return RepairOutcome(rule_id=plan_item.rule_id, action=plan_item.action, success=True, message=f"Repair succeeded: {_action_verb(plan_item.action)} completed at '{destination}'", message_key='repair_msg_success', message_params={'action': plan_item.action, 'destination': str(destination)}, backup_path=str(backup_path) if backup_path else None)
    except (OSError, PermissionError, shutil.Error) as e:
        return RepairOutcome(rule_id=plan_item.rule_id, action=plan_item.action, success=False, message=f'Repair failed: {e}', message_key='repair_msg_failed', message_params={'error': str(e)})

def _action_verb(action: str) -> str:
    return {RepairAction.RESTORE_MISSING: 'restore the missing file', RepairAction.OVERWRITE_CORRUPTED: 'overwrite the corrupted file with the original', RepairAction.MOVE_MISPLACED: 'move the misplaced file back'}.get(action, action)

def run_repair(scan_results: list, rules_by_id: dict, reference_dir: Path, backup_dir: Path, apply: bool=False, os_family: str='windows', custom_anchors: Optional[dict]=None, offline_root: Optional[str]=None) -> dict:
    plan_items = []
    outcomes = []
    for result in scan_results:
        rule = rules_by_id[result.rule_id]
        plan_item = build_repair_plan(result, reference_dir, rule, os_family=os_family, custom_anchors=custom_anchors, offline_root=offline_root)
        plan_items.append(plan_item)
        outcome = execute_repair_item(plan_item, backup_dir, apply=apply)
        outcomes.append(outcome)
    return {'mode': 'apply' if apply else 'dry_run', 'executed_at': datetime.now().isoformat(timespec='seconds'), 'plan': [p.to_dict() for p in plan_items], 'outcomes': [o.to_dict() for o in outcomes]}
if __name__ == '__main__':
    import argparse
    from scanner import run_scan
    from audit_log import append_audit_entry
    parser = argparse.ArgumentParser(description='USB Integrity Checker - Repair Module')
    parser.add_argument('--profile', required=True)
    parser.add_argument('--reference-dir', required=True)
    parser.add_argument('--backup-dir', required=True)
    parser.add_argument('--search-root', action='append', default=None)
    parser.add_argument('--apply', action='store_true', help='If this flag is omitted, always runs as a dry-run (safe default)')
    parser.add_argument('--json-out')
    parser.add_argument('--logs-dir', default=None, help='Audit log folder (if given, every run is logged automatically)')
    parser.add_argument('--offline-root', default=None, help='Used when booting directly from USB: the path where the target drive is mounted')
    args = parser.parse_args()
    profile_path = Path(args.profile)
    reference_dir = Path(args.reference_dir)
    backup_dir = Path(args.backup_dir)
    with open(profile_path, 'r', encoding='utf-8') as f:
        profile = json.load(f)
    rules_by_id = {r['id']: r for r in profile['rules']}
    os_family = profile.get('os_family', 'windows')
    custom_anchors = profile.get('custom_anchors', {})
    report = run_scan(profile_path, reference_dir, args.search_root, offline_root=args.offline_root)
    result = run_repair(report.results, rules_by_id, reference_dir, backup_dir, apply=args.apply, os_family=os_family, custom_anchors=custom_anchors, offline_root=args.offline_root)
    mode_label = 'APPLY' if args.apply else 'DRY-RUN — no files touched yet'
    print(f'\n=== Repair plan: {mode_label} ===\n')
    for outcome in result['outcomes']:
        if outcome['action'] == 'blocked_personal_zone':
            icon = '[BLOCKED]'
        else:
            icon = '[OK]' if outcome['success'] else '[FAILED]'
        print(f'{icon} [{outcome['rule_id']}] {outcome['action']}: {outcome['message']}')
        if outcome.get('backup_path'):
            print(f'    (backed up original to: {outcome['backup_path']})')
    if args.json_out:
        with open(args.json_out, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f'\nSaved results as JSON to: {args.json_out}')
    if args.logs_dir:
        action_counts = {}
        for outcome in result['outcomes']:
            action_counts[outcome['action']] = action_counts.get(outcome['action'], 0) + 1
        append_audit_entry(logs_dir=Path(args.logs_dir), event_type='repair_apply' if args.apply else 'repair_dry_run', profile_name=profile.get('profile_name', profile_path.stem), summary=action_counts, extra={'outcomes': result['outcomes']})
