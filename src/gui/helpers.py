import tkinter as tk
from pathlib import Path
import i18n

def _open_file_location(path: str):
    import platform
    import subprocess
    p = Path(path)
    try:
        if platform.system() == 'Windows':
            if p.is_dir():
                subprocess.Popen(['explorer', str(p)])
            else:
                subprocess.Popen(['explorer', '/select,', str(p)])
        elif platform.system() == 'Darwin':
            subprocess.Popen(['open', '-R', str(p)])
        else:
            subprocess.Popen(['xdg-open', str(p.parent if p.is_file() else p)])
    except OSError:
        pass

def _attach_locate_menu(widget, get_path_callable, lang='en'):
    menu = tk.Menu(widget, tearoff=0)
    menu.add_command(label=i18n.t('context_open_location', lang=lang), command=lambda: _open_file_location(get_path_callable()))

    def show_menu(event):
        path = get_path_callable()
        if path:
            menu.tk_popup(event.x_root, event.y_root)
    widget.bind('<Button-3>', show_menu)
    return menu

def _show_add_target_menu(button, lang, on_pick_files, on_pick_folder):
    menu = tk.Menu(button, tearoff=0)
    menu.add_command(label=i18n.t('wizard_add_files_menu', lang=lang), command=on_pick_files)
    menu.add_command(label=i18n.t('wizard_add_folder_menu', lang=lang), command=on_pick_folder)
    x = button.winfo_rootx()
    y = button.winfo_rooty() + button.winfo_height()
    menu.tk_popup(x, y)
