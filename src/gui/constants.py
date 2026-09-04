from pathlib import Path
import i18n
APP_VERSION = '1.0.0'
BASE_DIR = Path(__file__).resolve().parent.parent.parent
GUI_CONFIG_PATH = BASE_DIR / 'gui_config.json'
GUI_SETTINGS_PATH = BASE_DIR / 'gui_settings.json'
BACKUP_DIR = BASE_DIR / 'backup'
LOGS_DIR = BASE_DIR / 'logs'
PROFILES_DIR = BASE_DIR / 'profiles'
REFERENCE_ROOT_DIR = BASE_DIR / 'reference_files'
COLOR_BG = '#0f1319'
COLOR_SIDEBAR = '#12171f'
COLOR_PANEL = '#161c25'
COLOR_ACCENT = '#35b8ad'
COLOR_ACCENT_HOVER = '#2a9990'
COLOR_TEXT = '#e8edf3'
COLOR_TEXT_MUTED = '#8b95a5'
COLOR_BORDER = '#232b36'
STATUS_COLORS = {'ok': '#1c3a2e', 'missing': '#3a1c20', 'corrupted': '#3a2f14', 'misplaced': '#3a2818', 'ref_broken': '#2c1c3a'}
STATUS_TEXT_COLORS = {'ok': '#3ecf8e', 'missing': '#ef5760', 'corrupted': '#f5a623', 'misplaced': '#ff8f4d', 'ref_broken': '#b57bf0'}
STATUS_KEY_MAP = {'ok': 'status_ok', 'missing': 'status_missing', 'corrupted': 'status_corrupted', 'misplaced': 'status_misplaced', 'ref_broken': 'status_ref_broken'}

def get_os_type_options(lang='en'):
    return [('Windows 11', 'windows'), ('Windows 10', 'windows'), ('Ubuntu / Linux', 'linux'), (i18n.t('os_option_custom', lang=lang), 'custom')]
REGISTRY_HIVE_OPTIONS = ['HKEY_CURRENT_USER', 'HKEY_LOCAL_MACHINE']
REGISTRY_TYPE_OPTIONS = ['REG_SZ', 'REG_DWORD', 'REG_EXPAND_SZ']
REGISTRY_STATUS_KEY_MAP = {'ok': 'status_ok', 'missing': 'status_missing', 'mismatched': 'status_mismatched', 'protected': 'status_protected', 'unsupported_os': 'status_unsupported_os'}
REGISTRY_STATUS_TEXT_COLORS = {'ok': STATUS_TEXT_COLORS['ok'], 'missing': STATUS_TEXT_COLORS['missing'], 'mismatched': STATUS_TEXT_COLORS['corrupted'], 'protected': STATUS_TEXT_COLORS['ref_broken'], 'unsupported_os': COLOR_TEXT_MUTED}
REGISTRY_STATUS_BG_COLORS = {'ok': STATUS_COLORS['ok'], 'missing': STATUS_COLORS['missing'], 'mismatched': STATUS_COLORS['corrupted'], 'protected': STATUS_COLORS['ref_broken'], 'unsupported_os': COLOR_PANEL}
