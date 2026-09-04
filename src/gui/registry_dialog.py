import tkinter as tk
import customtkinter as ctk
import i18n
from registry_rules import is_protected_registry_key, read_registry_value, _WINREG_AVAILABLE, find_candidate_keys, capture_registry_subtree
from .constants import COLOR_BG, COLOR_PANEL, COLOR_BORDER, COLOR_ACCENT, COLOR_ACCENT_HOVER, COLOR_TEXT, COLOR_TEXT_MUTED, STATUS_TEXT_COLORS, REGISTRY_HIVE_OPTIONS, REGISTRY_TYPE_OPTIONS

class RegistryEntryDialog(ctk.CTkToplevel):

    def __init__(self, master, on_confirm, lang='en'):
        super().__init__(master)
        self.lang = lang
        self.title(i18n.t('registry_dialog_title', lang=lang))
        self.geometry('520x560')
        self.minsize(480, 500)
        self.configure(fg_color=COLOR_BG)
        self.on_confirm = on_confirm
        self.selected_candidate = None
        self.grab_set()
        ctk.CTkLabel(self, text=i18n.t('registry_dialog_title', lang=lang), font=('', 16, 'bold')).pack(padx=20, pady=(20, 10), anchor='w')
        mode_row = ctk.CTkFrame(self, fg_color='transparent')
        mode_row.pack(padx=20, fill='x', pady=(0, 10))
        self.simple_tab_btn = ctk.CTkButton(mode_row, text=i18n.t('registry_mode_simple', lang=lang), command=self._show_simple_mode, fg_color=COLOR_ACCENT, text_color='#06231a')
        self.simple_tab_btn.pack(side='left', padx=(0, 6))
        self.advanced_tab_btn = ctk.CTkButton(mode_row, text=i18n.t('registry_mode_advanced', lang=lang), command=self._show_advanced_mode, fg_color=COLOR_PANEL, hover_color=COLOR_BORDER)
        self.advanced_tab_btn.pack(side='left')
        self.body = ctk.CTkFrame(self, fg_color='transparent')
        self.body.pack(fill='both', expand=True, padx=20)
        self.simple_frame = self._build_simple_mode()
        self.advanced_frame = self._build_advanced_mode()
        self.advanced_frame.pack_forget()
        if not _WINREG_AVAILABLE:
            ctk.CTkLabel(self, text=i18n.t('registry_no_winreg', lang=lang), text_color=STATUS_TEXT_COLORS['corrupted'], wraplength=470).pack(padx=20, pady=(4, 0))
        ctk.CTkButton(self, text=i18n.t('wizard_cancel', lang=lang), command=self.destroy, fg_color=COLOR_PANEL, hover_color=COLOR_BORDER).pack(side='bottom', anchor='w', padx=20, pady=20)

    def _show_simple_mode(self):
        self.advanced_frame.pack_forget()
        self.simple_frame.pack(fill='both', expand=True)
        self.simple_tab_btn.configure(fg_color=COLOR_ACCENT, text_color='#06231a')
        self.advanced_tab_btn.configure(fg_color=COLOR_PANEL, text_color=COLOR_TEXT)

    def _show_advanced_mode(self):
        self.simple_frame.pack_forget()
        self.advanced_frame.pack(fill='both', expand=True)
        self.advanced_tab_btn.configure(fg_color=COLOR_ACCENT, text_color='#06231a')
        self.simple_tab_btn.configure(fg_color=COLOR_PANEL, text_color=COLOR_TEXT)

    def _build_simple_mode(self):
        frame = ctk.CTkFrame(self.body, fg_color='transparent')
        frame.pack(fill='both', expand=True)
        ctk.CTkLabel(frame, text=i18n.t('registry_app_name_label', lang=self.lang), text_color=COLOR_TEXT_MUTED).pack(anchor='w')
        search_row = ctk.CTkFrame(frame, fg_color='transparent')
        search_row.pack(fill='x', pady=(4, 10))
        self.app_name_entry = ctk.CTkEntry(search_row, placeholder_text='e.g. TestPrinterApp')
        self.app_name_entry.pack(side='left', fill='x', expand=True, padx=(0, 6))
        ctk.CTkButton(search_row, text=i18n.t('registry_search', lang=self.lang), width=100, command=self._search_candidates, fg_color=COLOR_PANEL, hover_color=COLOR_BORDER).pack(side='left')
        ctk.CTkLabel(frame, text=i18n.t('registry_results_label', lang=self.lang), text_color=COLOR_TEXT_MUTED).pack(anchor='w')
        self.candidates_frame = ctk.CTkScrollableFrame(frame, fg_color=COLOR_PANEL, corner_radius=8, height=140)
        self.candidates_frame.pack(fill='x', pady=(4, 10))
        self.candidates_empty_label = ctk.CTkLabel(self.candidates_frame, text=i18n.t('registry_not_searched', lang=self.lang), text_color=COLOR_TEXT_MUTED)
        self.candidates_empty_label.pack(pady=10)
        ctk.CTkLabel(frame, text=i18n.t('registry_manual_label', lang=self.lang), text_color=COLOR_TEXT_MUTED).pack(anchor='w')
        manual_row = ctk.CTkFrame(frame, fg_color='transparent')
        manual_row.pack(fill='x', pady=(4, 10))
        self.manual_hive_var = tk.StringVar(value=REGISTRY_HIVE_OPTIONS[0])
        ctk.CTkOptionMenu(manual_row, values=REGISTRY_HIVE_OPTIONS, variable=self.manual_hive_var, width=170).pack(side='left', padx=(0, 6))
        self.manual_key_entry = ctk.CTkEntry(manual_row, placeholder_text='Software\\MyApp')
        self.manual_key_entry.pack(side='left', fill='x', expand=True)
        self.simple_note_label = ctk.CTkLabel(frame, text='', wraplength=460, justify='left', text_color=COLOR_TEXT_MUTED)
        self.simple_note_label.pack(anchor='w', pady=(4, 10))
        ctk.CTkButton(frame, text=i18n.t('registry_capture_all', lang=self.lang), command=self._capture_from_selected, fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, text_color='#06231a').pack(fill='x')
        return frame

    def _search_candidates(self):
        for widget in self.candidates_frame.winfo_children():
            widget.destroy()
        if not _WINREG_AVAILABLE:
            ctk.CTkLabel(self.candidates_frame, text=i18n.t('registry_capture_only_windows', lang=self.lang), text_color=COLOR_TEXT_MUTED).pack(pady=10)
            return
        app_name = self.app_name_entry.get().strip()
        if not app_name:
            ctk.CTkLabel(self.candidates_frame, text=i18n.t('registry_need_app_name', lang=self.lang), text_color=COLOR_TEXT_MUTED).pack(pady=10)
            return
        candidates = find_candidate_keys(app_name)
        if not candidates:
            ctk.CTkLabel(self.candidates_frame, text=i18n.t('registry_no_candidates', lang=self.lang), text_color=COLOR_TEXT_MUTED).pack(pady=10)
            return
        for hive, key_path in candidates:
            row = ctk.CTkButton(self.candidates_frame, text=f'{hive}\\{key_path}', anchor='w', fg_color=COLOR_BG, hover_color=COLOR_BORDER, command=lambda h=hive, k=key_path: self._select_candidate(h, k))
            row.pack(fill='x', pady=2, padx=4)

    def _select_candidate(self, hive, key_path):
        self.selected_candidate = (hive, key_path)
        self.manual_hive_var.set(hive)
        self.manual_key_entry.delete(0, 'end')
        self.manual_key_entry.insert(0, key_path)
        self.simple_note_label.configure(text=i18n.t('registry_selected_prefix', lang=self.lang, value=f'{hive}\\{key_path}'), text_color=COLOR_TEXT)

    def _capture_from_selected(self):
        if not _WINREG_AVAILABLE:
            self.simple_note_label.configure(text=i18n.t('registry_capture_only_windows', lang=self.lang), text_color=STATUS_TEXT_COLORS['corrupted'])
            return
        hive = self.manual_hive_var.get()
        key_path = self.manual_key_entry.get().strip()
        if not key_path:
            self.simple_note_label.configure(text=i18n.t('registry_need_key_first', lang=self.lang), text_color=STATUS_TEXT_COLORS['corrupted'])
            return
        try:
            result = capture_registry_subtree(hive, key_path)
        except (PermissionError, RuntimeError) as e:
            self.simple_note_label.configure(text=f'{e}', text_color=STATUS_TEXT_COLORS['missing'])
            return
        if not result['rules']:
            self.simple_note_label.configure(text=i18n.t('registry_capture_nothing', lang=self.lang), text_color=STATUS_TEXT_COLORS['corrupted'])
            return
        msg = i18n.t('registry_capture_success', lang=self.lang, count=len(result['rules']))
        if result['skipped_unsupported_type']:
            msg += '\n' + i18n.t('registry_capture_skipped_type', lang=self.lang, count=result['skipped_unsupported_type'])
        if result['skipped_protected']:
            msg += '\n' + i18n.t('registry_capture_skipped_protected', lang=self.lang, count=len(result['skipped_protected']))
        if result['truncated']:
            msg += '\n' + i18n.t('registry_capture_truncated', lang=self.lang)
        self.simple_note_label.configure(text=msg, text_color=COLOR_TEXT)
        self.on_confirm(result['rules'])
        self.after(1500, self.destroy)

    def _build_advanced_mode(self):
        frame = ctk.CTkFrame(self.body, fg_color='transparent')
        ctk.CTkLabel(frame, text=i18n.t('registry_hive_label', lang=self.lang), text_color=COLOR_TEXT_MUTED).pack(anchor='w')
        self.hive_var = tk.StringVar(value=REGISTRY_HIVE_OPTIONS[0])
        ctk.CTkOptionMenu(frame, values=REGISTRY_HIVE_OPTIONS, variable=self.hive_var).pack(fill='x', pady=(4, 10))
        ctk.CTkLabel(frame, text=i18n.t('registry_key_label', lang=self.lang), text_color=COLOR_TEXT_MUTED).pack(anchor='w')
        self.key_entry = ctk.CTkEntry(frame, placeholder_text='Software\\MyApp\\Settings')
        self.key_entry.pack(fill='x', pady=(4, 10))
        ctk.CTkLabel(frame, text=i18n.t('registry_value_name_label', lang=self.lang), text_color=COLOR_TEXT_MUTED).pack(anchor='w')
        self.value_name_entry = ctk.CTkEntry(frame, placeholder_text='e.g. PaperSize')
        self.value_name_entry.pack(fill='x', pady=(4, 10))
        ctk.CTkLabel(frame, text=i18n.t('registry_value_type_label', lang=self.lang), text_color=COLOR_TEXT_MUTED).pack(anchor='w')
        self.type_var = tk.StringVar(value=REGISTRY_TYPE_OPTIONS[0])
        ctk.CTkOptionMenu(frame, values=REGISTRY_TYPE_OPTIONS, variable=self.type_var).pack(fill='x', pady=(4, 10))
        ctk.CTkLabel(frame, text=i18n.t('registry_expected_label', lang=self.lang), text_color=COLOR_TEXT_MUTED).pack(anchor='w')
        row = ctk.CTkFrame(frame, fg_color='transparent')
        row.pack(fill='x', pady=(4, 4))
        self.expected_entry = ctk.CTkEntry(row, placeholder_text='e.g. A4')
        self.expected_entry.pack(side='left', fill='x', expand=True, padx=(0, 6))
        ctk.CTkButton(row, text=i18n.t('registry_capture_current', lang=self.lang), width=140, command=self._capture_current, fg_color=COLOR_PANEL, hover_color=COLOR_BORDER).pack(side='left')
        self.note_label = ctk.CTkLabel(frame, text='', text_color=STATUS_TEXT_COLORS['corrupted'], wraplength=460, justify='left')
        self.note_label.pack(anchor='w', pady=(6, 10))
        ctk.CTkButton(frame, text=i18n.t('registry_add_value', lang=self.lang), command=self._confirm_advanced, fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, text_color='#06231a').pack(fill='x')
        return frame

    def _capture_current(self):
        if not _WINREG_AVAILABLE:
            return
        hive = self.hive_var.get()
        key_path = self.key_entry.get().strip()
        value_name = self.value_name_entry.get().strip()
        if not key_path or not value_name:
            self.note_label.configure(text=i18n.t('registry_fill_all', lang=self.lang), text_color=STATUS_TEXT_COLORS['corrupted'])
            return
        if is_protected_registry_key(hive, key_path):
            self.note_label.configure(text=i18n.t('registry_protected_error', lang=self.lang), text_color=STATUS_TEXT_COLORS['missing'])
            return
        value, _ = read_registry_value(hive, key_path, value_name)
        if value is None:
            self.note_label.configure(text=i18n.t('registry_value_not_found', lang=self.lang), text_color=STATUS_TEXT_COLORS['corrupted'])
        else:
            self.expected_entry.delete(0, 'end')
            self.expected_entry.insert(0, str(value))
            self.note_label.configure(text=i18n.t('registry_captured_current', lang=self.lang, value=value), text_color=COLOR_TEXT)

    def _confirm_advanced(self):
        hive = self.hive_var.get()
        key_path = self.key_entry.get().strip()
        value_name = self.value_name_entry.get().strip()
        expected_value = self.expected_entry.get().strip()
        if not key_path or not value_name or (not expected_value):
            self.note_label.configure(text=i18n.t('registry_fill_all', lang=self.lang), text_color=STATUS_TEXT_COLORS['corrupted'])
            return
        if is_protected_registry_key(hive, key_path):
            self.note_label.configure(text=i18n.t('registry_protected_error', lang=self.lang), text_color=STATUS_TEXT_COLORS['missing'])
            return
        rule = {'hive': hive, 'key_path': key_path, 'value_name': value_name, 'value_type': self.type_var.get(), 'expected_value': expected_value, 'action_on_mismatch': 'auto_repair'}
        self.on_confirm([rule])
        self.destroy()
