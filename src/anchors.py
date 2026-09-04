import os
from pathlib import Path
from typing import Optional

def get_anchor_roots(os_family: str, custom_anchors: Optional[dict]=None, offline_root: Optional[str]=None) -> dict:
    custom_anchors = custom_anchors or {}
    if os_family == 'custom':
        base = dict(custom_anchors)
        base.update(custom_anchors)
        return base
    if offline_root:
        offline = Path(offline_root)
        if os_family == 'windows':
            base = {'PROGRAM_ROOT_X86': str(offline / 'Program Files (x86)'), 'PROGRAM_ROOT': str(offline / 'Program Files'), 'PROGRAMDATA': str(offline / 'ProgramData')}
        elif os_family == 'linux':
            base = {'PROGRAM_ROOT': str(offline / 'opt'), 'CONFIG_ROOT': str(offline / 'etc'), 'USR_LOCAL': str(offline / 'usr/local'), 'USR_BIN': str(offline / 'usr/bin')}
        else:
            base = {}
        base.update(custom_anchors)
        return base
    if os_family == 'windows':
        base = {'PROGRAM_ROOT_X86': os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'), 'PROGRAM_ROOT': os.environ.get('PROGRAMFILES', 'C:\\Program Files'), 'APPDATA': os.environ.get('APPDATA', ''), 'LOCALAPPDATA': os.environ.get('LOCALAPPDATA', ''), 'PROGRAMDATA': os.environ.get('PROGRAMDATA', 'C:\\ProgramData'), 'HOME': os.path.expanduser('~')}
    elif os_family == 'linux':
        base = {'PROGRAM_ROOT': '/opt', 'CONFIG_ROOT': '/etc', 'USR_LOCAL': '/usr/local', 'USR_BIN': '/usr/bin', 'HOME': os.path.expanduser('~')}
    else:
        base = {'HOME': os.path.expanduser('~')}
    base.update(custom_anchors)
    return base

def detect_current_os_family() -> str:
    import platform
    system = platform.system().lower()
    if system == 'windows':
        return 'windows'
    if system in ('linux', 'darwin'):
        return 'linux'
    return 'unknown'

def detect_current_os_version_label() -> str:
    import platform
    system = platform.system()
    if system == 'Windows':
        detailed = _detect_windows_detailed_version()
        if detailed:
            return detailed
        release = platform.release()
        return f'Windows {release}'
    if system == 'Linux':
        try:
            os_release = {}
            with open('/etc/os-release', 'r', encoding='utf-8') as f:
                for line in f:
                    if '=' in line:
                        k, _, v = line.strip().partition('=')
                        os_release[k] = v.strip('"')
            pretty = os_release.get('PRETTY_NAME')
            if pretty:
                return pretty
        except (FileNotFoundError, OSError):
            pass
        return f'Linux {platform.release()}'
    if system == 'Darwin':
        return f'macOS {platform.mac_ver()[0]}'
    return system or 'Unknown OS'

def _detect_windows_detailed_version() -> Optional[str]:
    try:
        import winreg
    except ImportError:
        return None
    try:
        key_path = 'SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion'
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:

            def read(name, default=''):
                try:
                    return winreg.QueryValueEx(key, name)[0]
                except FileNotFoundError:
                    return default
            product_name = read('ProductName', 'Windows')
            display_version = read('DisplayVersion') or read('ReleaseId')
            build = read('CurrentBuildNumber', '')
            ubr = read('UBR', '')
            try:
                build_num = int(build)
            except (TypeError, ValueError):
                build_num = 0
            if build_num >= 22000 and product_name.startswith('Windows 10'):
                product_name = product_name.replace('Windows 10', 'Windows 11', 1)
            label = product_name
            if display_version:
                label += f' {display_version}'
            if build:
                build_str = f'{build}.{ubr}' if ubr else str(build)
                label += f' (Build {build_str})'
            return label
    except OSError:
        return None

def os_version_looks_compatible(profile_os_type: str, detected_version: str) -> bool:
    import re
    if not profile_os_type:
        return True

    def extract_version_tokens(s: str):
        return set(re.findall('\\d+(?:\\.\\d+)*', s))
    profile_versions = extract_version_tokens(profile_os_type)
    detected_versions = extract_version_tokens(detected_version)
    if not profile_versions or not detected_versions:
        return True
    for pv in profile_versions:
        for dv in detected_versions:
            if pv == dv or pv.startswith(dv) or dv.startswith(pv):
                return True
    return False

def to_anchor_path(path: Path, os_family: str, custom_anchors: Optional[dict]=None) -> str:
    roots = get_anchor_roots(os_family, custom_anchors)
    path_str = str(path)
    sorted_roots = sorted([(name, root) for name, root in roots.items() if root], key=lambda kv: -len(kv[1]))
    for name, root in sorted_roots:
        norm_root = root.replace('\\', '/')
        norm_path = path_str.replace('\\', '/')
        if norm_path.startswith(norm_root):
            rest = norm_path[len(norm_root):].lstrip('/')
            return '{' + name + '}/' + rest if rest else '{' + name + '}'
    return path_str

def resolve_anchor_path(anchor_path: str, os_family: Optional[str]=None, custom_anchors: Optional[dict]=None, offline_root: Optional[str]=None) -> Path:
    if os_family is None:
        os_family = detect_current_os_family()
    if not anchor_path.startswith('{'):
        return Path(anchor_path)
    end = anchor_path.find('}')
    if end == -1:
        return Path(anchor_path)
    anchor_name = anchor_path[1:end]
    rest = anchor_path[end + 1:].lstrip('/')
    roots = get_anchor_roots(os_family, custom_anchors, offline_root)
    root = roots.get(anchor_name)
    if not root:
        return Path(anchor_path)
    return Path(root) / rest if rest else Path(root)
_PERSONAL_ZONE_FOLDER_NAMES = {'Desktop', 'Documents', 'Downloads', 'Pictures', 'Videos', 'Music', 'เดสก์ท็อป', 'เอกสาร', 'ดาวน์โหลด', 'รูปภาพ', 'วิดีโอ', 'เพลง'}

def is_in_personal_zone(path: Path, os_family: str, custom_anchors: Optional[dict]=None, offline_root: Optional[str]=None) -> bool:
    try:
        target_path = path.resolve()
    except OSError:
        return False
    if offline_root:
        offline = Path(offline_root)
        candidate_user_dirs = []
        for users_folder_name in ('Users', 'home'):
            users_root = offline / users_folder_name
            if users_root.is_dir():
                candidate_user_dirs.extend([d for d in users_root.iterdir() if d.is_dir()])
        for user_dir in candidate_user_dirs:
            try:
                rel = target_path.relative_to(user_dir.resolve())
            except (ValueError, OSError):
                continue
            if len(rel.parts) == 0 or rel.parts[0] in _PERSONAL_ZONE_FOLDER_NAMES:
                return True
        return False
    roots = get_anchor_roots(os_family, custom_anchors)
    home = roots.get('HOME')
    if not home:
        return False
    try:
        home_path = Path(home).resolve()
        target_path = path.resolve()
        rel = target_path.relative_to(home_path)
    except (ValueError, OSError):
        return False
    if len(rel.parts) == 0:
        return True
    return rel.parts[0] in _PERSONAL_ZONE_FOLDER_NAMES
