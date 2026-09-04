import json
import re
import i18n
from .constants import GUI_CONFIG_PATH, GUI_SETTINGS_PATH

def _load_language() -> str:
    if not GUI_SETTINGS_PATH.is_file():
        return i18n.DEFAULT_LANG
    try:
        with open(GUI_SETTINGS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('language', i18n.DEFAULT_LANG)
    except (json.JSONDecodeError, OSError):
        return i18n.DEFAULT_LANG

def _save_language(lang: str):
    with open(GUI_SETTINGS_PATH, 'w', encoding='utf-8') as f:
        json.dump({'language': lang}, f, ensure_ascii=False, indent=2)

def _load_gui_config() -> list:
    if not GUI_CONFIG_PATH.is_file():
        return []
    with open(GUI_CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def _save_gui_config(entries: list):
    with open(GUI_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

def _slugify(name: str) -> str:
    safe = re.sub('[^\\w\\-ก-๙]', '_', name.strip())
    return safe or 'profile'
