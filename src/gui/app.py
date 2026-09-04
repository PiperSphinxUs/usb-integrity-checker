import html
import json
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk
import i18n
from scanner import run_scan
from repair import run_repair
from profile_builder import ProfileBuilder
from audit_log import append_audit_entry, read_audit_log
from registry_rules import scan_registry_rule, repair_registry_rule, RegistryStatus, _WINREG_AVAILABLE
from .constants import APP_VERSION, BACKUP_DIR, LOGS_DIR, PROFILES_DIR, REFERENCE_ROOT_DIR, COLOR_BG, COLOR_SIDEBAR, COLOR_PANEL, COLOR_BORDER, COLOR_ACCENT, COLOR_ACCENT_HOVER, COLOR_TEXT, COLOR_TEXT_MUTED, STATUS_COLORS, STATUS_TEXT_COLORS, STATUS_KEY_MAP, REGISTRY_STATUS_KEY_MAP, REGISTRY_STATUS_TEXT_COLORS, REGISTRY_STATUS_BG_COLORS
from .config import _load_language, _save_language, _load_gui_config, _save_gui_config
from .helpers import _open_file_location
from .wizard import ProfileWizard
from .add_files_dialog import AddFilesDialog
from .registry_dialog import RegistryEntryDialog

class App(ctk.CTk):

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode('dark')
        self.title(f'USB Integrity Checker v{APP_VERSION}')
        self.geometry('1100x720')
        self.minsize(820, 560)
        self.configure(fg_color=COLOR_BG)
        self.profile_entries = _load_gui_config()
        self.lang = _load_language()
        self.current_index = None
        self.current_report = None
        self.current_unknown_files = []
        self.current_registry_results = []
        self._build_layout()
        self._refresh_sidebar()
        if self.profile_entries:
            try:
                self._open_profile(0)
            except (FileNotFoundError, json.JSONDecodeError):
                self._show_empty_view()
        else:
            self._show_empty_view()

    def _build_layout(self):
        self.sidebar = ctk.CTkFrame(self, width=220, fg_color=COLOR_SIDEBAR, corner_radius=0)
        self.sidebar.pack(side='left', fill='y')
        self.sidebar.pack_propagate(False)
        header = ctk.CTkFrame(self.sidebar, fg_color='transparent')
        header.pack(fill='x', padx=16, pady=(20, 10))
        self.app_name_label = ctk.CTkLabel(header, text=i18n.t('app_name', lang=self.lang).upper(), font=('', 11, 'bold'), text_color=COLOR_TEXT_MUTED)
        self.app_name_label.pack(side='left')
        self.profile_list_frame = ctk.CTkScrollableFrame(self.sidebar, fg_color='transparent')
        self.profile_list_frame.pack(fill='both', expand=True, padx=8, pady=8)
        self.add_profile_btn = ctk.CTkButton(self.sidebar, text=i18n.t('nav_add_profile', lang=self.lang), command=self._open_wizard, fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, text_color='#06231a')
        self.add_profile_btn.pack(fill='x', padx=16, pady=(8, 6))
        self.settings_btn = ctk.CTkButton(self.sidebar, text=i18n.t('nav_settings', lang=self.lang), command=self._show_settings_view, fg_color=COLOR_PANEL, hover_color=COLOR_BORDER)
        self.settings_btn.pack(fill='x', padx=16, pady=(0, 16))
        self.main_area = ctk.CTkFrame(self, fg_color=COLOR_BG, corner_radius=0)
        self.main_area.pack(side='left', fill='both', expand=True)
        self.empty_view = self._build_empty_view()
        self.dashboard_view = self._build_dashboard_view()
        self.settings_view = self._build_settings_view()

    def _clear_main(self):
        for view in (self.empty_view, self.dashboard_view, self.settings_view):
            view.pack_forget()

    def _show_empty_view(self):
        self._clear_main()
        self.empty_view.pack(fill='both', expand=True)

    def _show_dashboard_view(self):
        self._clear_main()
        self.dashboard_view.pack(fill='both', expand=True)

    def _show_settings_view(self):
        self._clear_main()
        self.settings_view.pack(fill='both', expand=True)
        self.path_profiles_val.configure(text=str(PROFILES_DIR))
        self.path_reference_val.configure(text=str(REFERENCE_ROOT_DIR))
        self.path_backup_val.configure(text=str(BACKUP_DIR))
        self.path_logs_val.configure(text=str(LOGS_DIR))

    def _build_empty_view(self):
        frame = ctk.CTkFrame(self.main_area, fg_color=COLOR_BG)
        self.empty_title_label = ctk.CTkLabel(frame, text=i18n.t('empty_title', lang=self.lang), font=('', 20, 'bold'))
        self.empty_title_label.pack(expand=True, pady=(0, 8))
        self.empty_body_label = ctk.CTkLabel(frame, text=i18n.t('empty_body', lang=self.lang), text_color=COLOR_TEXT_MUTED)
        self.empty_body_label.pack()
        return frame

    def _refresh_sidebar(self):
        for widget in self.profile_list_frame.winfo_children():
            widget.destroy()
        for idx, entry in enumerate(self.profile_entries):
            try:
                with open(entry['profile_path'], 'r', encoding='utf-8') as f:
                    data = json.load(f)
                label = data.get('profile_name', '?')
                os_type = data.get('os_type', '?')
            except (FileNotFoundError, json.JSONDecodeError):
                label = i18n.t('profile_not_found', lang=self.lang)
                os_type = ''
            is_active = idx == self.current_index
            row = ctk.CTkFrame(self.profile_list_frame, fg_color=COLOR_ACCENT if is_active else COLOR_PANEL, corner_radius=8)
            row.pack(fill='x', pady=4)
            text_color = '#06231a' if is_active else COLOR_TEXT
            btn = ctk.CTkButton(row, text=f'{label}\n{os_type}', anchor='w', font=('', 12), fg_color='transparent', hover_color=COLOR_BORDER if not is_active else COLOR_ACCENT_HOVER, text_color=text_color, command=lambda i=idx: self._open_profile(i))
            btn.pack(side='left', fill='both', expand=True, padx=(4, 0), pady=4)
            del_btn = ctk.CTkButton(row, text='✕', width=28, fg_color='transparent', hover_color=STATUS_COLORS['missing'], text_color=text_color, command=lambda i=idx: self._remove_profile(i))
            del_btn.pack(side='right', padx=4, pady=4)

    def _attach_tooltip(self, widget, text):
        state = {'win': None}

        def show(_event):
            win = tk.Toplevel(widget)
            win.wm_overrideredirect(True)
            win.configure(bg=COLOR_BORDER)
            x = widget.winfo_rootx() + widget.winfo_width() + 10
            y = widget.winfo_rooty() + widget.winfo_height() // 2 - 12
            win.wm_geometry(f'+{x}+{y}')
            ctk.CTkLabel(win, text=text, fg_color=COLOR_PANEL, text_color=COLOR_TEXT, corner_radius=6, padx=10, pady=6, justify='left').pack()
            state['win'] = win

        def hide(_event):
            if state['win'] is not None:
                state['win'].destroy()
                state['win'] = None
        widget.bind('<Enter>', show)
        widget.bind('<Leave>', hide)

    def _open_wizard(self):
        ProfileWizard(self, on_created=self._on_profile_created, lang=self.lang)

    def _on_profile_created(self):
        self.profile_entries = _load_gui_config()
        self._refresh_sidebar()
        self._open_profile(len(self.profile_entries) - 1)

    def _remove_profile(self, idx):
        entry = self.profile_entries[idx]
        name = Path(entry['profile_path']).stem
        if not messagebox.askyesno(i18n.t('remove_profile_title', lang=self.lang), i18n.t('remove_profile_confirm', lang=self.lang, name=name)):
            return
        del self.profile_entries[idx]
        _save_gui_config(self.profile_entries)
        if self.current_index == idx:
            self.current_index = None
            self._show_empty_view()
        self._refresh_sidebar()

    def _build_dashboard_view(self):
        frame = ctk.CTkFrame(self.main_area, fg_color=COLOR_BG)
        top = ctk.CTkFrame(frame, fg_color='transparent')
        top.pack(fill='x', padx=24, pady=(20, 6))
        self.dash_name_label = ctk.CTkLabel(top, text='—', font=('', 18, 'bold'))
        self.dash_name_label.pack(side='left')
        self.dash_os_badge = ctk.CTkLabel(top, text='—', fg_color=COLOR_PANEL, corner_radius=6, text_color=COLOR_TEXT_MUTED, padx=8, pady=2)
        self.dash_os_badge.pack(side='left', padx=10)
        self.warning_label = ctk.CTkLabel(frame, text='', text_color=STATUS_TEXT_COLORS['corrupted'], wraplength=800, justify='left')
        self.warning_label.pack(fill='x', padx=24)
        tab_bar = ctk.CTkFrame(frame, fg_color='transparent')
        tab_bar.pack(fill='x', padx=24, pady=(10, 0))
        self.tab_file_btn = ctk.CTkButton(tab_bar, text=i18n.t('dashboard_tab_files', lang=self.lang), command=self._show_file_tab, fg_color=COLOR_ACCENT, text_color='#06231a', width=110)
        self.tab_file_btn.pack(side='left', padx=(0, 6))
        self.tab_registry_btn = ctk.CTkButton(tab_bar, text=i18n.t('dashboard_tab_registry', lang=self.lang), command=self._show_registry_tab, fg_color=COLOR_PANEL, hover_color=COLOR_BORDER, width=110)
        self.tab_registry_btn.pack(side='left')
        style = ttk.Style()
        style.theme_use('default')
        style.configure('Dark.Treeview', background=COLOR_PANEL, fieldbackground=COLOR_PANEL, foreground=COLOR_TEXT, rowheight=28, borderwidth=0)
        style.configure('Dark.Treeview.Heading', background=COLOR_SIDEBAR, foreground=COLOR_TEXT_MUTED, borderwidth=0)
        style.map('Dark.Treeview', background=[('selected', COLOR_ACCENT)])
        self.file_panel = self._build_file_panel(frame)
        self.registry_panel = self._build_registry_panel(frame)
        self.registry_panel.pack_forget()
        return frame

    def _show_file_tab(self):
        self.registry_panel.pack_forget()
        self.file_panel.pack(fill='both', expand=True)
        self.tab_file_btn.configure(fg_color=COLOR_ACCENT, text_color='#06231a')
        self.tab_registry_btn.configure(fg_color=COLOR_PANEL, text_color=COLOR_TEXT)

    def _show_registry_tab(self):
        self.file_panel.pack_forget()
        self.registry_panel.pack(fill='both', expand=True)
        self.tab_registry_btn.configure(fg_color=COLOR_ACCENT, text_color='#06231a')
        self.tab_file_btn.configure(fg_color=COLOR_PANEL, text_color=COLOR_TEXT)
        self._on_registry_scan()

    def _build_file_panel(self, parent):
        panel = ctk.CTkFrame(parent, fg_color=COLOR_BG)
        panel.pack(fill='both', expand=True)
        self.unknown_files_btn = ctk.CTkButton(panel, text='', fg_color=STATUS_COLORS['misplaced'], hover_color=COLOR_BORDER, text_color=STATUS_TEXT_COLORS['misplaced'], anchor='w', command=self._show_unknown_files)
        table_frame = ctk.CTkFrame(panel, fg_color='transparent')
        table_frame.pack(fill='both', expand=True, padx=24, pady=12)
        columns = ('rule_id', 'watch_file', 'status', 'detail')
        self.tree = ttk.Treeview(table_frame, columns=columns, show='headings', style='Dark.Treeview')
        self.tree.heading('rule_id', text='Rule ID')
        self.tree.heading('watch_file', text=i18n.t('dashboard_tab_files', lang=self.lang))
        self.tree.heading('status', text='Status')
        self.tree.heading('detail', text='Detail')
        self.tree.column('rule_id', width=90)
        self.tree.column('watch_file', width=160)
        self.tree.column('status', width=110)
        self.tree.column('detail', width=420)
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<Button-3>', self._on_file_tree_right_click)
        for status, bg in STATUS_COLORS.items():
            self.tree.tag_configure(status, background=bg, foreground=STATUS_TEXT_COLORS[status])
        self.summary_label = ctk.CTkLabel(panel, text='', text_color=COLOR_TEXT_MUTED)
        self.summary_label.pack(anchor='w', padx=24)
        actions = ctk.CTkFrame(panel, fg_color='transparent')
        actions.pack(fill='x', padx=24, pady=(8, 20))
        self.scan_btn = ctk.CTkButton(actions, text=i18n.t('dashboard_scan', lang=self.lang), command=self._on_scan, fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, text_color='#06231a')
        self.scan_btn.pack(side='left')
        self.dry_run_btn = ctk.CTkButton(actions, text=i18n.t('dashboard_repair_plan', lang=self.lang), command=self._on_dry_run, fg_color=COLOR_PANEL, hover_color=COLOR_BORDER, state='disabled')
        self.dry_run_btn.pack(side='left', padx=10)
        self.apply_btn = ctk.CTkButton(actions, text=i18n.t('dashboard_apply_fix', lang=self.lang), command=self._on_apply, fg_color=STATUS_TEXT_COLORS['missing'], hover_color='#c94850', state='disabled')
        self.apply_btn.pack(side='left')
        ctk.CTkButton(actions, text=i18n.t('dashboard_add_files', lang=self.lang), command=self._open_add_files_to_profile, fg_color=COLOR_PANEL, hover_color=COLOR_BORDER).pack(side='left', padx=10)
        ctk.CTkButton(actions, text=i18n.t('dashboard_export_report', lang=self.lang), command=self._export_report, fg_color=COLOR_PANEL, hover_color=COLOR_BORDER).pack(side='left')
        ctk.CTkButton(actions, text=i18n.t('dashboard_history', lang=self.lang), command=self._show_audit_log, fg_color=COLOR_PANEL, hover_color=COLOR_BORDER).pack(side='right')
        return panel

    def _build_registry_panel(self, parent):
        panel = ctk.CTkFrame(parent, fg_color=COLOR_BG)
        if not _WINREG_AVAILABLE:
            ctk.CTkLabel(panel, text=i18n.t('registry_tab_no_windows', lang=self.lang), text_color=STATUS_TEXT_COLORS['corrupted']).pack(padx=24, pady=12, anchor='w')
        table_frame = ctk.CTkFrame(panel, fg_color='transparent')
        table_frame.pack(fill='both', expand=True, padx=24, pady=12)
        columns = ('rule_id', 'key', 'value_name', 'status', 'detail')
        self.registry_tree = ttk.Treeview(table_frame, columns=columns, show='headings', style='Dark.Treeview')
        self.registry_tree.heading('rule_id', text='Rule ID')
        self.registry_tree.heading('key', text='Key')
        self.registry_tree.heading('value_name', text='Value')
        self.registry_tree.heading('status', text='Status')
        self.registry_tree.heading('detail', text='Detail')
        self.registry_tree.column('rule_id', width=80)
        self.registry_tree.column('key', width=260)
        self.registry_tree.column('value_name', width=100)
        self.registry_tree.column('status', width=100)
        self.registry_tree.column('detail', width=260)
        self.registry_tree.pack(fill='both', expand=True)
        self.registry_tree.bind('<Button-3>', self._on_registry_tree_right_click)
        for status, bg in REGISTRY_STATUS_BG_COLORS.items():
            self.registry_tree.tag_configure(status, background=bg, foreground=REGISTRY_STATUS_TEXT_COLORS[status])
        self.registry_summary_label = ctk.CTkLabel(panel, text='', text_color=COLOR_TEXT_MUTED)
        self.registry_summary_label.pack(anchor='w', padx=24)
        actions = ctk.CTkFrame(panel, fg_color='transparent')
        actions.pack(fill='x', padx=24, pady=(8, 20))
        self.registry_scan_btn = ctk.CTkButton(actions, text=i18n.t('dashboard_scan', lang=self.lang), command=self._on_registry_scan, fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, text_color='#06231a')
        self.registry_scan_btn.pack(side='left')
        self.registry_dry_run_btn = ctk.CTkButton(actions, text=i18n.t('dashboard_repair_plan', lang=self.lang), command=self._on_registry_dry_run, fg_color=COLOR_PANEL, hover_color=COLOR_BORDER, state='disabled')
        self.registry_dry_run_btn.pack(side='left', padx=10)
        self.registry_apply_btn = ctk.CTkButton(actions, text=i18n.t('dashboard_apply_fix', lang=self.lang), command=self._on_registry_apply, fg_color=STATUS_TEXT_COLORS['missing'], hover_color='#c94850', state='disabled')
        self.registry_apply_btn.pack(side='left')
        ctk.CTkButton(actions, text=i18n.t('wizard_add_registry', lang=self.lang), command=self._open_add_registry_to_profile, fg_color=COLOR_PANEL, hover_color=COLOR_BORDER).pack(side='right')
        return panel

    def _open_add_files_to_profile(self):
        AddFilesDialog(self, on_confirm=self._add_files_to_current_profile, lang=self.lang)

    def _add_files_to_current_profile(self, targets: list, allow_personal: bool):
        entry = self.profile_entries[self.current_index]
        with open(entry['profile_path'], 'r', encoding='utf-8') as f:
            data = json.load(f)
        builder = ProfileBuilder(profile_name=data.get('profile_name', '?'), reference_dir=Path(entry['reference_dir']), profiles_dir=PROFILES_DIR, os_type=data.get('os_type', ''), os_family=data.get('os_family', 'windows'), custom_anchors=data.get('custom_anchors', {}))
        builder.rules = data.get('rules', [])
        builder.watched_folders = data.get('watched_folders', [])
        for target in targets:
            try:
                if target['is_folder']:
                    builder.add_folder(target['path'], allow_personal_path=allow_personal)
                else:
                    builder.add_file(target['path'], allow_personal_path=allow_personal)
            except (FileNotFoundError, NotADirectoryError, PermissionError):
                continue
        builder.save()
        self._on_scan()

    def _open_add_registry_to_profile(self):
        RegistryEntryDialog(self, on_confirm=self._add_registry_rule_to_current_profile, lang=self.lang)

    def _add_registry_rule_to_current_profile(self, rules: list):
        entry = self.profile_entries[self.current_index]
        with open(entry['profile_path'], 'r', encoding='utf-8') as f:
            data = json.load(f)
        existing = data.get('registry_rules', [])
        for rule_partial in rules:
            rule_partial['id'] = f'reg_{len(existing) + 1:03d}'
            existing.append(rule_partial)
        data['registry_rules'] = existing
        with open(entry['profile_path'], 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._on_registry_scan()

    def _current_registry_rules(self) -> list:
        entry = self.profile_entries[self.current_index]
        with open(entry['profile_path'], 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('registry_rules', [])

    def _on_registry_scan(self):
        if self.current_index is None:
            return
        self.registry_scan_btn.configure(state='disabled', text=i18n.t('dashboard_scanning', lang=self.lang))
        registry_rules = self._current_registry_rules()
        scan_target_index = self.current_index

        def worker():
            results = [scan_registry_rule(r) for r in registry_rules]
            self.after(0, lambda: self._on_registry_scan_finished(results, scan_target_index))
        threading.Thread(target=worker, daemon=True).start()

    def _on_registry_scan_finished(self, results, scan_target_index):
        self.registry_scan_btn.configure(state='normal', text=i18n.t('dashboard_scan', lang=self.lang))
        if scan_target_index != self.current_index:
            return
        self.current_registry_results = results
        self.registry_tree.delete(*self.registry_tree.get_children())
        for r in self.current_registry_results:
            status_th = i18n.t(REGISTRY_STATUS_KEY_MAP.get(r.status.value, r.status.value), lang=self.lang)
            self.registry_tree.insert('', tk.END, values=(r.rule_id, f'{r.hive}\\{r.key_path}', r.value_name, status_th, r.detail), tags=(r.status.value,))
        counts = {}
        for r in self.current_registry_results:
            counts[r.status.value] = counts.get(r.status.value, 0) + 1
        self.registry_summary_label.configure(text='  |  '.join((f'{i18n.t(REGISTRY_STATUS_KEY_MAP[k], lang=self.lang)}: {v}' for k, v in counts.items())) if counts else i18n.t('registry_no_values', lang=self.lang))
        append_audit_entry(LOGS_DIR, 'registry_scan', Path(self.profile_entries[self.current_index]['profile_path']).stem, counts)
        needs_repair = any((r.status == RegistryStatus.MISMATCHED or r.status == RegistryStatus.MISSING for r in self.current_registry_results))
        self.registry_dry_run_btn.configure(state='normal' if needs_repair else 'disabled')
        self.registry_apply_btn.configure(state='normal' if needs_repair else 'disabled')

    def _on_registry_dry_run(self):
        self._run_registry_repair(apply=False)

    def _on_registry_apply(self):
        confirmed = messagebox.askyesno(i18n.t('confirm_repair_title', lang=self.lang), i18n.t('confirm_repair_body', lang=self.lang))
        if not confirmed:
            return
        self._run_registry_repair(apply=True)
        self._on_registry_scan()

    def _run_registry_repair(self, apply: bool):
        registry_rules = self._current_registry_rules()
        results_by_id = {r.rule_id: r for r in self.current_registry_results}
        outcomes = []
        for rule in registry_rules:
            scan_result = results_by_id[rule['id']]
            outcomes.append(repair_registry_rule(rule, scan_result, BACKUP_DIR, apply=apply))
        action_counts = {}
        for o in outcomes:
            key = 'success' if o['success'] else 'failed'
            action_counts[key] = action_counts.get(key, 0) + 1
        append_audit_entry(LOGS_DIR, 'registry_repair_apply' if apply else 'registry_repair_dry_run', Path(self.profile_entries[self.current_index]['profile_path']).stem, action_counts, extra={'outcomes': outcomes})
        self._show_registry_result_window(outcomes, i18n.t('result_registry_apply_title', lang=self.lang) if apply else i18n.t('result_registry_dry_run_title', lang=self.lang))

    def _show_registry_result_window(self, outcomes, title):
        win = ctk.CTkToplevel(self)
        win.title(title)
        win.geometry('640x420')
        win.minsize(480, 320)
        win.configure(fg_color=COLOR_BG)
        win.grab_set()
        box = ctk.CTkTextbox(win, fg_color=COLOR_PANEL, text_color=COLOR_TEXT)
        box.pack(fill='both', expand=True, padx=16, pady=16)
        for o in outcomes:
            icon = '[OK]' if o['success'] else '[FAILED]'
            msg = i18n.t(o['message_key'], lang=self.lang, **o.get('message_params', {})) if o.get('message_key') else o['message']
            box.insert('end', f'{icon} [{o['rule_id']}] {msg}\n')
            if o.get('backup_path'):
                box.insert('end', f'    {i18n.t('backup_saved_at', lang=self.lang, path=o['backup_path'])}\n')
            box.insert('end', '\n')
        box.configure(state='disabled')

    def _open_profile(self, idx):
        self.current_index = idx
        entry = self.profile_entries[idx]
        with open(entry['profile_path'], 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.dash_name_label.configure(text=data.get('profile_name', '?'))
        self.dash_os_badge.configure(text=data.get('os_type', '?'))
        created_os_version = data.get('created_os_version')
        if created_os_version:
            self._attach_tooltip(self.dash_os_badge, f'{i18n.t('report_machine', lang=self.lang)}: {created_os_version}')
        self._refresh_sidebar()
        self._show_dashboard_view()
        self._show_file_tab()
        self._on_scan()

    def _on_file_tree_right_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id or not self.current_report:
            return
        self.tree.selection_set(item_id)
        rule_id = self.tree.item(item_id, 'values')[0]
        result = next((r for r in self.current_report.results if r.rule_id == rule_id), None)
        if not result:
            return
        menu = tk.Menu(self.tree, tearoff=0)
        if result.resolved_location:
            menu.add_command(label=i18n.t('context_open_location', lang=self.lang), command=lambda: _open_file_location(result.resolved_location))
            menu.add_command(label=i18n.t('context_copy_path', lang=self.lang), command=lambda: self._copy_to_clipboard(result.resolved_location))
            menu.add_separator()
        menu.add_command(label=i18n.t('context_remove_rule', lang=self.lang), command=lambda: self._remove_rule_from_profile(rule_id, result.watch_file))
        menu.tk_popup(event.x_root, event.y_root)

    def _copy_to_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)

    def _remove_rule_from_profile(self, rule_id, display_name):
        if not messagebox.askyesno(i18n.t('remove_rule_confirm_title', lang=self.lang), i18n.t('remove_rule_confirm_body', lang=self.lang, name=display_name)):
            return
        entry = self.profile_entries[self.current_index]
        with open(entry['profile_path'], 'r', encoding='utf-8') as f:
            data = json.load(f)
        data['rules'] = [r for r in data.get('rules', []) if r['id'] != rule_id]
        with open(entry['profile_path'], 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._on_scan()

    def _on_registry_tree_right_click(self, event):
        item_id = self.registry_tree.identify_row(event.y)
        if not item_id:
            return
        values = self.registry_tree.item(item_id, 'values')
        rule_id, key_path, value_name = (values[0], values[1], values[2])
        self.registry_tree.selection_set(item_id)
        menu = tk.Menu(self.registry_tree, tearoff=0)
        menu.add_command(label=i18n.t('context_copy_path', lang=self.lang), command=lambda: self._copy_to_clipboard(f'{key_path}\\{value_name}'))
        menu.add_separator()
        menu.add_command(label=i18n.t('context_remove_rule', lang=self.lang), command=lambda: self._remove_registry_rule_from_profile(rule_id, value_name))
        menu.tk_popup(event.x_root, event.y_root)

    def _remove_registry_rule_from_profile(self, rule_id, display_name):
        if not messagebox.askyesno(i18n.t('remove_rule_confirm_title', lang=self.lang), i18n.t('remove_rule_confirm_body', lang=self.lang, name=display_name)):
            return
        entry = self.profile_entries[self.current_index]
        with open(entry['profile_path'], 'r', encoding='utf-8') as f:
            data = json.load(f)
        data['registry_rules'] = [r for r in data.get('registry_rules', []) if r['id'] != rule_id]
        with open(entry['profile_path'], 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._on_registry_scan()

    def _export_report(self):
        if not self.current_report:
            return
        report = self.current_report
        lang = self.lang
        esc = html.escape
        status_rows = ''
        for r in report.results:
            status_label = i18n.t(STATUS_KEY_MAP.get(r.status.value, r.status.value), lang=lang)
            detail_text = i18n.t(r.detail_key, lang=lang, **r.detail_params) if r.detail_key else r.detail
            bg = STATUS_COLORS.get(r.status.value, COLOR_PANEL)
            fg = STATUS_TEXT_COLORS.get(r.status.value, COLOR_TEXT)
            status_rows += f'<tr><td>{esc(r.rule_id)}</td><td>{esc(r.watch_file)}</td><td style="background:{bg};color:{fg};font-weight:600">{esc(status_label)}</td><td>{esc(detail_text)}</td></tr>\n'
        s = report.summary()
        summary_html = ''.join((f'<span class="chip" style="background:{STATUS_COLORS[k]};color:{STATUS_TEXT_COLORS[k]}">{esc(i18n.t(STATUS_KEY_MAP[k], lang=lang))}: {s[k]}</span>' for k in ('ok', 'missing', 'corrupted', 'misplaced', 'ref_broken')))
        profile_name_safe = esc(report.profile_name)
        html_doc = f'<!DOCTYPE html>\n<html><head><meta charset="utf-8">\n<title>{esc(i18n.t('report_title', lang=lang))} - {profile_name_safe}</title>\n<style>\nbody {{ font-family: Segoe UI, Arial, sans-serif; background:{COLOR_BG}; color:{COLOR_TEXT}; padding:32px; }}\nh1 {{ margin-bottom:4px; }}\n.meta {{ color:{COLOR_TEXT_MUTED}; margin-bottom:20px; }}\n.chip {{ display:inline-block; padding:4px 10px; border-radius:6px; margin-right:8px; font-size:13px; }}\ntable {{ width:100%; border-collapse:collapse; margin-top:16px; }}\nth, td {{ text-align:left; padding:8px 10px; border-bottom:1px solid {COLOR_BORDER}; font-size:13px; }}\nth {{ color:{COLOR_TEXT_MUTED}; font-weight:600; }}\n</style></head><body>\n<h1>{esc(i18n.t('report_title', lang=lang))}: {profile_name_safe}</h1>\n<div class="meta">{esc(i18n.t('report_generated_at', lang=lang))}: {esc(report.scanned_at)}<br>\n{esc(i18n.t('report_machine', lang=lang))}: {esc(report.detected_os_version)}</div>\n<div>{summary_html}</div>\n<table>\n<tr><th>Rule ID</th><th>{esc(i18n.t('dashboard_tab_files', lang=lang))}</th><th>Status</th><th>Detail</th></tr>\n{status_rows}\n</table>\n</body></html>'
        safe_profile_name = ''.join((c if c.isalnum() or c in '-_' else '_' for c in report.profile_name))
        default_name = f'{safe_profile_name}_report_{report.scanned_at.replace(':', '-')}.html'
        path = filedialog.asksaveasfilename(defaultextension='.html', initialfile=default_name, filetypes=[('HTML file', '*.html')])
        if not path:
            return
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html_doc)
        messagebox.showinfo('', i18n.t('report_saved', lang=lang, path=path))
        _open_file_location(path)

    def _on_scan(self):
        if self.current_index is None:
            return
        self.scan_btn.configure(state='disabled', text=i18n.t('dashboard_scanning', lang=self.lang))
        entry = self.profile_entries[self.current_index]
        profile_path = Path(entry['profile_path'])
        reference_dir = Path(entry['reference_dir'])
        scan_target_index = self.current_index

        def worker():
            report = run_scan(profile_path, reference_dir)
            self.after(0, lambda: self._on_scan_finished(report, scan_target_index))
        threading.Thread(target=worker, daemon=True).start()

    def _on_scan_finished(self, report, scan_target_index):
        self.scan_btn.configure(state='normal', text=i18n.t('dashboard_scan', lang=self.lang))
        if scan_target_index != self.current_index:
            return
        self.current_report = report
        append_audit_entry(LOGS_DIR, 'scan', report.profile_name, report.summary())
        if report.os_mismatch:
            self.warning_label.configure(text=i18n.t('os_mismatch_warning', lang=self.lang), text_color=STATUS_TEXT_COLORS['missing'])
        elif report.os_version_mismatch:
            self.warning_label.configure(text=i18n.t('os_version_mismatch_warning', lang=self.lang, detected=report.detected_os_version, expected=report.profile_os_type), text_color=STATUS_TEXT_COLORS['corrupted'])
        else:
            self.warning_label.configure(text='')
        self.tree.delete(*self.tree.get_children())
        for r in report.results:
            status_th = i18n.t(STATUS_KEY_MAP.get(r.status.value, r.status.value), lang=self.lang)
            detail_text = i18n.t(r.detail_key, lang=self.lang, **r.detail_params) if r.detail_key else r.detail
            self.tree.insert('', tk.END, values=(r.rule_id, r.watch_file, status_th, detail_text), tags=(r.status.value,))
        self.current_unknown_files = report.unknown_files
        if report.unknown_files:
            self.unknown_files_btn.configure(text=i18n.t('dashboard_unknown_files', lang=self.lang, count=len(report.unknown_files)))
            self.unknown_files_btn.pack(fill='x', padx=24, pady=(0, 8), before=self.tree.master)
        else:
            self.unknown_files_btn.pack_forget()
        s = report.summary()
        summary_parts = [f'{i18n.t(STATUS_KEY_MAP[k], lang=self.lang)}: {s[k]}' for k in ('ok', 'missing', 'corrupted', 'misplaced', 'ref_broken')]
        self.summary_label.configure(text='  |  '.join(summary_parts))
        needs_repair = s['missing'] + s['corrupted'] + s['misplaced'] > 0
        self.dry_run_btn.configure(state='normal' if needs_repair else 'disabled')
        self.apply_btn.configure(state='normal' if needs_repair else 'disabled')

    def _rules_by_id_and_family(self):
        entry = self.profile_entries[self.current_index]
        with open(entry['profile_path'], 'r', encoding='utf-8') as f:
            data = json.load(f)
        rules_by_id = {r['id']: r for r in data['rules']}
        return (rules_by_id, data.get('os_family', 'windows'), data.get('custom_anchors', {}), data.get('profile_name', '?'))

    def _on_dry_run(self):
        self._run_repair(apply=False)

    def _on_apply(self):
        confirmed = messagebox.askyesno(i18n.t('confirm_repair_title', lang=self.lang), i18n.t('confirm_repair_body', lang=self.lang))
        if not confirmed:
            return
        self._run_repair(apply=True)
        self._on_scan()

    def _run_repair(self, apply: bool):
        entry = self.profile_entries[self.current_index]
        rules_by_id, os_family, custom_anchors, profile_name = self._rules_by_id_and_family()
        result = run_repair(self.current_report.results, rules_by_id, Path(entry['reference_dir']), BACKUP_DIR, apply=apply, os_family=os_family, custom_anchors=custom_anchors)
        action_counts = {}
        for outcome in result['outcomes']:
            action_counts[outcome['action']] = action_counts.get(outcome['action'], 0) + 1
        append_audit_entry(LOGS_DIR, 'repair_apply' if apply else 'repair_dry_run', profile_name, action_counts, extra={'outcomes': result['outcomes']})
        self._show_result_window(result, i18n.t('result_apply_title', lang=self.lang) if apply else i18n.t('result_dry_run_title', lang=self.lang))

    def _show_result_window(self, result, title):
        win = ctk.CTkToplevel(self)
        win.title(title)
        win.geometry('640x420')
        win.minsize(480, 320)
        win.configure(fg_color=COLOR_BG)
        win.grab_set()
        box = ctk.CTkTextbox(win, fg_color=COLOR_PANEL, text_color=COLOR_TEXT)
        box.pack(fill='both', expand=True, padx=16, pady=16)
        action_label_keys = {'restore_missing': 'verb_restore_missing', 'overwrite_corrupted': 'verb_overwrite_corrupted', 'move_misplaced': 'verb_move_misplaced'}
        for o in result['outcomes']:
            icon = '[BLOCKED]' if o['action'] == 'blocked_personal_zone' else '[OK]' if o['success'] else '[FAILED]'
            action_label = i18n.t(action_label_keys[o['action']], lang=self.lang) if o['action'] in action_label_keys else o['action']
            params = dict(o.get('message_params', {}))
            if 'action' in params and params['action'] in action_label_keys:
                params['verb'] = i18n.t(action_label_keys[params['action']], lang=self.lang)
                del params['action']
            msg = i18n.t(o['message_key'], lang=self.lang, **params) if o.get('message_key') else o['message']
            box.insert('end', f'{icon} [{o['rule_id']}] {action_label}\n    {msg}\n')
            if o.get('backup_path'):
                box.insert('end', f'    {i18n.t('backup_saved_at', lang=self.lang, path=o['backup_path'])}\n')
            box.insert('end', '\n')
        box.configure(state='disabled')

    def _show_unknown_files(self):
        win = ctk.CTkToplevel(self)
        win.title(i18n.t('dashboard_unknown_files_title', lang=self.lang))
        win.geometry('640x420')
        win.minsize(480, 320)
        win.configure(fg_color=COLOR_BG)
        win.grab_set()
        ctk.CTkLabel(win, justify='left', wraplength=600, text_color=COLOR_TEXT_MUTED, text=i18n.t('dashboard_unknown_files_body', lang=self.lang)).pack(padx=16, pady=(16, 8), anchor='w')
        box = ctk.CTkTextbox(win, fg_color=COLOR_PANEL, text_color=COLOR_TEXT)
        box.pack(fill='both', expand=True, padx=16, pady=(0, 16))
        for f in self.current_unknown_files:
            box.insert('end', f'- {f}\n')
        box.configure(state='disabled')

    def _show_audit_log(self):
        entries = read_audit_log(LOGS_DIR, limit=50)
        win = ctk.CTkToplevel(self)
        win.title(i18n.t('audit_log_title', lang=self.lang))
        win.geometry('640x420')
        win.minsize(480, 320)
        win.configure(fg_color=COLOR_BG)
        win.grab_set()
        box = ctk.CTkTextbox(win, fg_color=COLOR_PANEL, text_color=COLOR_TEXT)
        box.pack(fill='both', expand=True, padx=16, pady=16)
        by_label = i18n.t('audit_log_by', lang=self.lang)
        summary_label = i18n.t('audit_log_summary', lang=self.lang)
        if not entries:
            box.insert('end', i18n.t('audit_log_empty', lang=self.lang))
        for e in entries:
            box.insert('end', f'[{e['timestamp']}] {e['event_type']}\n    {by_label}: {e['actor']} | {summary_label}: {e['summary']}\n\n')
        box.configure(state='disabled')

    def _build_settings_view(self):
        frame = ctk.CTkFrame(self.main_area, fg_color=COLOR_BG)
        self.settings_title_label = ctk.CTkLabel(frame, text=i18n.t('settings_title', lang=self.lang), font=('', 20, 'bold'))
        self.settings_title_label.pack(anchor='w', padx=24, pady=(24, 16))
        lang_block = ctk.CTkFrame(frame, fg_color=COLOR_PANEL, corner_radius=8)
        lang_block.pack(fill='x', padx=24, pady=8)
        self.settings_lang_title_label = ctk.CTkLabel(lang_block, text=i18n.t('settings_language_title', lang=self.lang), text_color=COLOR_TEXT_MUTED, font=('', 12, 'bold'))
        self.settings_lang_title_label.pack(anchor='w', padx=16, pady=(12, 8))
        lang_names = list(i18n.LANGUAGES.values())
        current_name = i18n.LANGUAGES.get(self.lang, i18n.LANGUAGES[i18n.DEFAULT_LANG])
        self.lang_var = tk.StringVar(value=current_name)
        lang_menu = ctk.CTkOptionMenu(lang_block, values=lang_names, variable=self.lang_var, command=self._on_language_changed)
        lang_menu.pack(anchor='w', padx=16, pady=(0, 16))
        block = ctk.CTkFrame(frame, fg_color=COLOR_PANEL, corner_radius=8)
        block.pack(fill='x', padx=24, pady=8)
        self.settings_paths_title_label = ctk.CTkLabel(block, text=i18n.t('settings_paths_title', lang=self.lang), text_color=COLOR_TEXT_MUTED, font=('', 12, 'bold'))
        self.settings_paths_title_label.pack(anchor='w', padx=16, pady=(12, 8))

        def path_row(label):
            row = ctk.CTkFrame(block, fg_color='transparent')
            row.pack(fill='x', padx=16, pady=4)
            ctk.CTkLabel(row, text=label, width=140, anchor='w').pack(side='left')
            val = ctk.CTkLabel(row, text='-', text_color=COLOR_TEXT_MUTED, anchor='w')
            val.pack(side='left', fill='x', expand=True)
            return val
        self.path_profiles_val = path_row('Profiles')
        self.path_reference_val = path_row('Reference Files')
        self.path_backup_val = path_row('Backup')
        self.path_logs_val = path_row('Logs / Audit')
        ctk.CTkLabel(block, text='').pack(pady=4)
        repair_block = ctk.CTkFrame(frame, fg_color=COLOR_PANEL, corner_radius=8)
        repair_block.pack(fill='x', padx=24, pady=8)
        self.settings_repair_title_label = ctk.CTkLabel(repair_block, text=i18n.t('settings_system_repair_title', lang=self.lang), text_color=COLOR_TEXT_MUTED, font=('', 12, 'bold'))
        self.settings_repair_title_label.pack(anchor='w', padx=16, pady=(12, 8))
        self.settings_sfc_btn = ctk.CTkButton(repair_block, text=i18n.t('settings_run_sfc', lang=self.lang), command=self._run_sfc_scan, fg_color=COLOR_PANEL, hover_color=COLOR_BORDER, border_width=1, border_color=COLOR_BORDER)
        self.settings_sfc_btn.pack(anchor='w', padx=16, pady=(0, 16))
        about_block = ctk.CTkFrame(frame, fg_color=COLOR_PANEL, corner_radius=8)
        about_block.pack(fill='x', padx=24, pady=8)
        self.settings_about_title_label = ctk.CTkLabel(about_block, text=i18n.t('settings_about_title', lang=self.lang), text_color=COLOR_TEXT_MUTED, font=('', 12, 'bold'))
        self.settings_about_title_label.pack(anchor='w', padx=16, pady=(12, 4))
        self.settings_about_body_label = ctk.CTkLabel(about_block, text=f'{i18n.t('app_name', lang=self.lang)} — {i18n.t('app_tagline', lang=self.lang)}', text_color=COLOR_TEXT_MUTED, justify='left', wraplength=600)
        self.settings_about_body_label.pack(anchor='w', padx=16, pady=(0, 4))
        self.settings_version_label = ctk.CTkLabel(about_block, text=f'{i18n.t('settings_version_label', lang=self.lang)}: {APP_VERSION}', text_color=COLOR_TEXT_MUTED, justify='left')
        self.settings_version_label.pack(anchor='w', padx=16, pady=(0, 16))
        return frame

    def _on_language_changed(self, selected_name: str):
        code_by_name = {v: k for k, v in i18n.LANGUAGES.items()}
        new_lang = code_by_name.get(selected_name, i18n.DEFAULT_LANG)
        if new_lang == self.lang:
            return
        self.lang = new_lang
        _save_language(new_lang)
        for widget in self.winfo_children():
            widget.destroy()
        self._build_layout()
        self._refresh_sidebar()
        self._show_settings_view()

    def _run_sfc_scan(self):
        import platform
        if platform.system() != 'Windows':
            messagebox.showinfo('', 'sfc /scannow is only available on Windows.')
            return
        try:
            import ctypes
            ctypes.windll.shell32.ShellExecuteW(None, 'runas', 'cmd.exe', '/k "sfc /scannow"', None, 1)
        except OSError as e:
            messagebox.showerror('Error', str(e))

def main():
    app = App()
    app.mainloop()
if __name__ == '__main__':
    main()
