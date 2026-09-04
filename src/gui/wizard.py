import json
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import i18n
from profile_builder import ProfileBuilder
from .constants import COLOR_BG, COLOR_PANEL, COLOR_BORDER, COLOR_ACCENT, COLOR_ACCENT_HOVER, COLOR_TEXT, COLOR_TEXT_MUTED, STATUS_COLORS, STATUS_TEXT_COLORS, PROFILES_DIR, REFERENCE_ROOT_DIR, get_os_type_options
from .config import _load_gui_config, _save_gui_config, _slugify
from .helpers import _attach_locate_menu, _show_add_target_menu
from .registry_dialog import RegistryEntryDialog

class ProfileWizard(ctk.CTkToplevel):

    def __init__(self, master, on_created, lang='en'):
        super().__init__(master)
        self.lang = lang
        self.title(i18n.t('wizard_title', lang=lang))
        self.geometry('520x720')
        self.minsize(480, 600)
        self.configure(fg_color=COLOR_BG)
        self.on_created = on_created
        self.targets = []
        self.pending_registry = []
        self.grab_set()
        scroll = ctk.CTkScrollableFrame(self, fg_color='transparent')
        scroll.pack(fill='both', expand=True, padx=0, pady=0)
        ctk.CTkLabel(scroll, text=i18n.t('wizard_title', lang=lang), font=('', 18, 'bold')).pack(pady=(20, 10), padx=20, anchor='w')
        ctk.CTkLabel(scroll, text=i18n.t('wizard_name_label', lang=lang), text_color=COLOR_TEXT_MUTED).pack(padx=20, anchor='w')
        self.name_entry = ctk.CTkEntry(scroll, placeholder_text='e.g. HIS Billing App')
        self.name_entry.pack(padx=20, fill='x', pady=(4, 14))
        ctk.CTkLabel(scroll, text=i18n.t('wizard_os_label', lang=lang), text_color=COLOR_TEXT_MUTED).pack(padx=20, anchor='w')
        self.os_options = get_os_type_options(lang)
        self.os_var = tk.StringVar(value=self.os_options[0][0])
        self.os_menu = ctk.CTkOptionMenu(scroll, values=[o[0] for o in self.os_options], variable=self.os_var)
        self.os_menu.pack(padx=20, fill='x', pady=(4, 14))
        ctk.CTkLabel(scroll, text=i18n.t('wizard_target_label', lang=lang), text_color=COLOR_TEXT_MUTED).pack(padx=20, anchor='w')
        self.add_target_btn = ctk.CTkButton(scroll, text=i18n.t('wizard_add_target', lang=lang), command=self._show_add_menu, fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, text_color='#06231a')
        self.add_target_btn.pack(padx=20, anchor='w', pady=(4, 8))
        self.targets_frame = ctk.CTkFrame(scroll, fg_color=COLOR_PANEL, corner_radius=8)
        self.targets_frame.pack(fill='x', padx=20, pady=(0, 8))
        self._refresh_targets_list()
        self.allow_personal_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(scroll, text=i18n.t('wizard_allow_personal', lang=lang), variable=self.allow_personal_var, fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER).pack(padx=20, anchor='w', pady=(0, 16))
        ctk.CTkFrame(scroll, fg_color=COLOR_BORDER, height=1).pack(fill='x', padx=20, pady=(0, 16))
        ctk.CTkLabel(scroll, text=i18n.t('wizard_registry_section', lang=lang), text_color=COLOR_TEXT_MUTED).pack(padx=20, anchor='w')
        ctk.CTkLabel(scroll, text=i18n.t('wizard_registry_hint', lang=lang), text_color=COLOR_TEXT_MUTED, font=('', 10)).pack(padx=20, anchor='w', pady=(0, 6))
        self.registry_list_frame = ctk.CTkFrame(scroll, fg_color=COLOR_PANEL, corner_radius=8)
        self.registry_list_frame.pack(fill='x', padx=20, pady=(0, 8))
        self.registry_empty_label = ctk.CTkLabel(self.registry_list_frame, text=i18n.t('wizard_targets_empty', lang=lang), text_color=COLOR_TEXT_MUTED)
        self.registry_empty_label.pack(pady=10)
        ctk.CTkButton(scroll, text=i18n.t('wizard_add_registry', lang=lang), command=self._open_registry_entry_dialog, fg_color=COLOR_PANEL, hover_color=COLOR_BORDER).pack(padx=20, anchor='w', pady=(0, 16))
        self.result_label = ctk.CTkLabel(scroll, text='', text_color=COLOR_TEXT_MUTED, wraplength=440, justify='left')
        self.result_label.pack(padx=20, anchor='w', fill='x', pady=(0, 16))
        footer = ctk.CTkFrame(self, fg_color=COLOR_BG)
        footer.pack(side='bottom', fill='x', padx=20, pady=20)
        ctk.CTkButton(footer, text=i18n.t('wizard_cancel', lang=lang), command=self.destroy, fg_color=COLOR_PANEL, hover_color=COLOR_BORDER).pack(side='left')
        self.confirm_btn = ctk.CTkButton(footer, text=i18n.t('wizard_create', lang=lang), command=self._confirm, fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, text_color='#06231a')
        self.confirm_btn.pack(side='right')

    def _show_add_menu(self):
        _show_add_target_menu(self.add_target_btn, self.lang, self._pick_files, self._pick_folder)

    def _pick_files(self):
        paths = filedialog.askopenfilenames()
        for path in paths:
            self.targets.append({'path': path, 'is_folder': False})
        if paths:
            self._refresh_targets_list()

    def _pick_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.targets.append({'path': path, 'is_folder': True})
            self._refresh_targets_list()

    def _refresh_targets_list(self):
        for widget in self.targets_frame.winfo_children():
            widget.destroy()
        if not self.targets:
            ctk.CTkLabel(self.targets_frame, text=i18n.t('wizard_targets_empty', lang=self.lang), text_color=COLOR_TEXT_MUTED).pack(pady=10)
            return
        for idx, target in enumerate(self.targets):
            row = ctk.CTkFrame(self.targets_frame, fg_color='transparent')
            row.pack(fill='x', padx=8, pady=4)
            icon = '[Folder]' if target['is_folder'] else '[File]'
            label = ctk.CTkLabel(row, text=f'{icon} {target['path']}', anchor='w', font=('', 11))
            label.pack(side='left', fill='x', expand=True)
            _attach_locate_menu(label, lambda p=target['path']: p, lang=self.lang)
            ctk.CTkButton(row, text='x', width=28, fg_color='transparent', hover_color=STATUS_COLORS['missing'], command=lambda i=idx: self._remove_target(i)).pack(side='right')

    def _remove_target(self, idx):
        del self.targets[idx]
        self._refresh_targets_list()

    def _open_registry_entry_dialog(self):
        RegistryEntryDialog(self, on_confirm=self._add_pending_registry, lang=self.lang)

    def _add_pending_registry(self, rules: list):
        for rule_partial in rules:
            rule_partial['id'] = f'reg_{len(self.pending_registry) + 1:03d}'
            self.pending_registry.append(rule_partial)
        self._refresh_registry_list()

    def _refresh_registry_list(self):
        for widget in self.registry_list_frame.winfo_children():
            widget.destroy()
        if not self.pending_registry:
            self.registry_empty_label = ctk.CTkLabel(self.registry_list_frame, text=i18n.t('wizard_targets_empty', lang=self.lang), text_color=COLOR_TEXT_MUTED)
            self.registry_empty_label.pack(pady=10)
            return
        for rule in self.pending_registry:
            row = ctk.CTkFrame(self.registry_list_frame, fg_color='transparent')
            row.pack(fill='x', padx=8, pady=4)
            text = f'{rule['hive']}\\{rule['key_path']} -> {rule['value_name']} = {rule['expected_value']}'
            ctk.CTkLabel(row, text=text, anchor='w', font=('', 11)).pack(side='left', fill='x', expand=True)
            ctk.CTkButton(row, text='x', width=28, fg_color='transparent', hover_color=STATUS_COLORS['missing'], command=lambda rid=rule['id']: self._remove_pending_registry(rid)).pack(side='right')

    def _remove_pending_registry(self, rule_id: str):
        self.pending_registry = [r for r in self.pending_registry if r['id'] != rule_id]
        self._refresh_registry_list()

    def _confirm(self):
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showwarning('', 'Please enter a profile name', parent=self)
            return
        if not self.targets and (not self.pending_registry):
            messagebox.showwarning('', 'Please add at least one file/folder or registry value', parent=self)
            return
        os_type = self.os_var.get()
        os_family = dict(self.os_options)[os_type]
        safe_name = _slugify(name)
        reference_dir = REFERENCE_ROOT_DIR / safe_name
        builder = ProfileBuilder(profile_name=name, reference_dir=reference_dir, profiles_dir=PROFILES_DIR, os_type=os_type, os_family=os_family)
        added_count = 0
        for target in self.targets:
            try:
                if target['is_folder']:
                    builder.add_folder(target['path'], allow_personal_path=self.allow_personal_var.get())
                else:
                    builder.add_file(target['path'], allow_personal_path=self.allow_personal_var.get())
                added_count += 1
            except (FileNotFoundError, NotADirectoryError, PermissionError) as e:
                self.result_label.configure(text=f'{target['path']}: {e}', text_color=STATUS_TEXT_COLORS['missing'])
        if len(builder.rules) == 0 and len(self.pending_registry) == 0:
            self.result_label.configure(text='No files were added to the profile, and no registry values either (they may have been blocked as personal files, or nothing was added yet).', text_color=STATUS_TEXT_COLORS['missing'])
            return
        out_path = builder.save()
        if self.pending_registry:
            with open(out_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            data['registry_rules'] = self.pending_registry
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        msg = f'Created successfully — added {len(builder.rules)} file(s)'
        if self.pending_registry:
            msg += f' + {len(self.pending_registry)} registry value(s)'
        if builder.last_skipped_personal:
            msg += f'\nSkipped {len(builder.last_skipped_personal)} file(s) in personal folders'
        self.result_label.configure(text=msg, text_color=COLOR_TEXT)
        entries = _load_gui_config()
        entries.append({'profile_path': str(out_path), 'reference_dir': str(reference_dir)})
        _save_gui_config(entries)
        self.after(1200, lambda: (self.destroy(), self.on_created()))
