import json
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from scanner import compute_sha256
from anchors import to_anchor_path, is_in_personal_zone, detect_current_os_version_label

@dataclass
class ProfileBuilder:
    profile_name: str
    reference_dir: Path
    profiles_dir: Path
    os_type: str = 'Windows 11'
    os_family: str = 'windows'
    custom_anchors: dict = field(default_factory=dict)
    watched_folders: list = field(default_factory=list)
    rules: list = field(default_factory=list)
    _seen_watch_files: set = field(default_factory=set)
    last_skipped_personal: list = field(default_factory=list)

    def add_file(self, source_path: str, expected_location: Optional[str]=None, action_on_mismatch: str='auto_repair', allow_personal_path: bool=False) -> dict:
        src = Path(source_path)
        if not src.is_file():
            raise FileNotFoundError(f'Source file not found: {source_path}')
        if is_in_personal_zone(src, self.os_family, self.custom_anchors) and (not allow_personal_path):
            raise PermissionError(f"Refused to add file: '{src}' is in a personal folder (Desktop/Documents/Downloads or HOME root). This type of file is not added automatically, to protect personal/work files from being overwritten. If this is intentional, pass allow_personal_path=True")
        watch_file = src.name
        raw_location = expected_location or str(src.resolve())
        location = to_anchor_path(Path(raw_location), self.os_family, self.custom_anchors)
        reference_id = f'ref_{src.stem}_{uuid.uuid4().hex[:8]}'
        reference_filename = f'{reference_id}.bin'
        self.reference_dir.mkdir(parents=True, exist_ok=True)
        dest = self.reference_dir / reference_filename
        shutil.copy2(src, dest)
        file_hash = compute_sha256(dest)
        rule = {'id': f'rule_{len(self.rules) + 1:03d}', 'watch_file': watch_file, 'expected_location': location, 'reference_id': reference_id, 'reference_filename': reference_filename, 'expected_hash': file_hash, 'action_on_mismatch': action_on_mismatch, 'allow_personal_path': allow_personal_path}
        self.rules.append(rule)
        return rule

    def add_folder(self, source_folder: str, action_on_mismatch: str='auto_repair', allow_personal_path: bool=False) -> list:
        added = []
        skipped_personal = []
        folder = Path(source_folder)
        if not folder.is_dir():
            raise NotADirectoryError(f'Folder not found: {source_folder}')
        folder_anchor = to_anchor_path(folder.resolve(), self.os_family, self.custom_anchors)
        if folder_anchor not in self.watched_folders:
            self.watched_folders.append(folder_anchor)
        for file_path in sorted(folder.rglob('*')):
            if file_path.is_file():
                try:
                    rule = self.add_file(str(file_path), action_on_mismatch=action_on_mismatch, allow_personal_path=allow_personal_path)
                    added.append(rule)
                except PermissionError:
                    skipped_personal.append(str(file_path))
        self.last_skipped_personal = skipped_personal
        if skipped_personal:
            print(f'Skipped {len(skipped_personal)} file(s) in personal folders (not added as rules):')
            for p in skipped_personal:
                print(f'    - {p}')
        return added

    def remove_rule(self, rule_id: str) -> bool:
        before = len(self.rules)
        self.rules = [r for r in self.rules if r['id'] != rule_id]
        return len(self.rules) < before

    def save(self) -> Path:
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        safe_name = self.profile_name.replace(' ', '_')
        out_path = self.profiles_dir / f'{safe_name}.json'
        data = {'profile_name': self.profile_name, 'os_type': self.os_type, 'os_family': self.os_family, 'custom_anchors': self.custom_anchors, 'watched_folders': self.watched_folders, 'rules': self.rules, 'created_os_version': detect_current_os_version_label()}
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return out_path
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Profile Builder - automatically capture a golden-machine baseline profile')
    parser.add_argument('--profile-name', required=True)
    parser.add_argument('--reference-dir', required=True)
    parser.add_argument('--profiles-dir', required=True)
    parser.add_argument('--os-type', default='Windows 11', help="Display label, e.g. 'Windows 11', 'Windows 10', 'Ubuntu 22.04', or a custom OS/program name")
    parser.add_argument('--os-family', default='windows', choices=['windows', 'linux', 'custom'], help='OS family: windows/linux use standard anchors, custom uses user-defined anchors (suited for niche OSes or single-program repair mode)')
    parser.add_argument('--custom-anchor', action='append', default=[], help='Define a custom anchor as NAME=PATH, e.g. --custom-anchor APP_ROOT=/srv/myapp. Can be repeated. Used with --os-family custom (leave empty if no anchors are needed)')
    parser.add_argument('--file', action='append', default=[], help='Add a single file. Can be repeated, e.g. --file /path/a.ini')
    parser.add_argument('--folder', action='append', default=[], help='Add an entire folder (recursively). Can be repeated')
    args = parser.parse_args()
    custom_anchors = {}
    for entry in args.custom_anchor:
        if '=' not in entry:
            raise ValueError(f'Invalid --custom-anchor format (must be NAME=PATH): {entry}')
        name, _, value = entry.partition('=')
        custom_anchors[name.strip()] = value.strip()
    builder = ProfileBuilder(profile_name=args.profile_name, reference_dir=Path(args.reference_dir), profiles_dir=Path(args.profiles_dir), os_type=args.os_type, os_family=args.os_family, custom_anchors=custom_anchors)
    for f in args.file:
        rule = builder.add_file(f)
        print(f'+ Added file: {rule['watch_file']}  (id: {rule['id']})')
    for folder in args.folder:
        rules = builder.add_folder(folder)
        print(f'+ Added folder {folder}: {len(rules)} file(s)')
    out_path = builder.save()
    print(f'\nProfile created successfully: {out_path}  ({len(builder.rules)} rules)')
