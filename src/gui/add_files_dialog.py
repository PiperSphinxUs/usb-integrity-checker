import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
import i18n
from .constants import COLOR_BG, COLOR_PANEL, COLOR_BORDER, COLOR_ACCENT, COLOR_ACCENT_HOVER, COLOR_TEXT_MUTED, STATUS_COLORS
from .helpers import _attach_locate_menu, _show_add_target_menu

class AddFilesDialog(ctk.CTkToplevel):

    def __init__(self, master, on_confirm, lang='en'):
        super().__init__(master)
        self.lang = lang
        self.title(i18n.t('dashboard_add_files', lang=lang))
        self.geometry('640x560')
        self.minsize(560, 480)
        self.configure(fg_color=COLOR_BG)
        self.on_confirm = on_confirm
        self.targets = []
        self.grab_set()
        ctk.CTkLabel(self, text=i18n.t('wizard_target_label', lang=lang), font=('', 16, 'bold')).pack(padx=20, pady=(20, 10), anchor='w')
        self.add_btn = ctk.CTkButton(self, text=i18n.t('wizard_add_target', lang=lang), command=self._show_add_menu, fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, text_color='#06231a')
        self.add_btn.pack(padx=20, anchor='w', pady=(0, 10))
        self.list_frame = ctk.CTkScrollableFrame(self, fg_color=COLOR_PANEL, corner_radius=8)
        self.list_frame.pack(fill='both', expand=True, padx=20, pady=(0, 10))
        self._refresh_list()
        self.allow_personal_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(self, text=i18n.t('wizard_allow_personal', lang=lang), variable=self.allow_personal_var, fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER).pack(padx=20, anchor='w', pady=(0, 10))
        footer = ctk.CTkFrame(self, fg_color='transparent')
        footer.pack(side='bottom', fill='x', padx=20, pady=20)
        ctk.CTkButton(footer, text=i18n.t('wizard_cancel', lang=lang), command=self.destroy, fg_color=COLOR_PANEL, hover_color=COLOR_BORDER).pack(side='left')
        ctk.CTkButton(footer, text=i18n.t('dashboard_add_files', lang=lang), command=self._confirm, fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, text_color='#06231a').pack(side='right')

    def _show_add_menu(self):
        _show_add_target_menu(self.add_btn, self.lang, self._pick_files, self._pick_folder)

    def _pick_files(self):
        paths = filedialog.askopenfilenames()
        for path in paths:
            self.targets.append({'path': path, 'is_folder': False})
        if paths:
            self._refresh_list()

    def _pick_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.targets.append({'path': path, 'is_folder': True})
            self._refresh_list()

    def _refresh_list(self):
        for widget in self.list_frame.winfo_children():
            widget.destroy()
        if not self.targets:
            ctk.CTkLabel(self.list_frame, text=i18n.t('wizard_targets_empty', lang=self.lang), text_color=COLOR_TEXT_MUTED).pack(pady=10)
            return
        for idx, target in enumerate(self.targets):
            row = ctk.CTkFrame(self.list_frame, fg_color='transparent')
            row.pack(fill='x', padx=8, pady=4)
            icon = '[Folder]' if target['is_folder'] else '[File]'
            label = ctk.CTkLabel(row, text=f'{icon} {target['path']}', anchor='w', font=('', 11))
            label.pack(side='left', fill='x', expand=True)
            _attach_locate_menu(label, lambda p=target['path']: p, lang=self.lang)
            ctk.CTkButton(row, text='x', width=28, fg_color='transparent', hover_color=STATUS_COLORS['missing'], command=lambda i=idx: self._remove_target(i)).pack(side='right')

    def _remove_target(self, idx):
        del self.targets[idx]
        self._refresh_list()

    def _confirm(self):
        if not self.targets:
            self.destroy()
            return
        self.on_confirm(self.targets, self.allow_personal_var.get())
        self.destroy()
