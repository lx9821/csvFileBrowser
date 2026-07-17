import csv
import os
import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk

try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
except Exception:
    Image = ImageDraw = ImageFont = ImageTk = None

from .dialogs import ColumnFilterDialog, CompareDetailWindow, CompareRootDialog, ImportDialog, SizeUnitDialog, TreeExportDialog
from .icons import load_icons, set_window_icon
from .models import *
from .parsing import detect_import_profile, file_md5, is_ftk_listing, read_csv_rows, read_tree_listing
from .profile_store import load_import_profile, save_import_profile
from .tree_export import compute_tree_stats, generate_tree_html, generate_tree_text
from .utils import *

class FileBrowser(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        set_window_icon(self)
        self.geometry("1320x780")
        self.minsize(980, 560)

        self.rows = []
        self.entries = []
        self.headers = []
        self.profile = None
        self.current_folder = "/"
        self.current_file = ""
        self.metadata_columns = []
        self.tree_data = {}
        self.folder_entries = {}
        self.folder_counts = {}
        self.folder_sizes = {}
        self.base_entries = []
        self.compare_entries = []
        self.compare_active = False
        self.compare_file = ""
        self.compare_roots = ("/", "/")
        self.import_kind = ""
        self.compare_status_by_path = {}
        self.compare_detail_by_path = {}
        self.compare_summary = {}
        self.plated_folders = set()
        self.checked_folders = set()
        self.checked_file_entries = {}
        self.sort_column = "name"
        self.sort_descending = False
        self.detail_render_token = 0
        self.detail_items = []
        self.detail_page_index = 0
        self.detail_render_index = 0
        self.detail_loading_iid = ""
        self.detail_total_files = 0
        self.detail_visible_files = 0
        self.detail_visible_folders = 0
        self.detail_rendered_files = 0
        self.detail_folder_count = 0
        self.detail_plate_mode = False
        self.tree_populated = set()
        self.context_folder_path = ""
        self.context_entry = None
        self.search_after_id = None
        self.column_filters = []
        self.breadcrumb_after_id = None
        self.breadcrumb_pending_path = "/"
        self.detail_entry_by_iid = {}
        self.detail_folder_by_iid = {}
        self.diff_icon_cache = {}
        self.detail_number_icon_cache = {}
        self.detail_number_width = DETAIL_NUMBER_MIN_WIDTH
        self.detail_number_icon_offset = 0
        self.compare_detail_window = None
        self.import_warnings = []
        self.saved_profile_name = ""

        self.icons = load_icons()
        self.status_var = tk.StringVar(value="Select a CSV or tree text file to start.")
        self.busy_message_var = tk.StringVar(value="")
        self.busy_overlay = None
        self.file_title_var = tk.StringVar(value="No file loaded")
        self.file_md5_var = tk.StringVar(value="")
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=COLORS["app_bg"])
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        self._configure_styles(style)

        self._build_import_screen()
        shell = ttk.Frame(self, style="App.TFrame", padding=14)
        self.main_shell = shell

        header_shell = tk.Frame(shell, bg="#99f6e4", bd=0)
        header_shell.pack(fill="x", pady=(0, 12))
        header = ttk.Frame(header_shell, style="Header.TFrame", padding=(14, 10))
        header.pack(fill="x", padx=1, pady=1)
        title_area = ttk.Frame(header, style="Header.TFrame")
        title_area.pack(side="left", fill="x", expand=True)
        ttk.Label(title_area, textvariable=self.file_title_var, style="FileTitle.TLabel").pack(anchor="w")
        ttk.Label(title_area, textvariable=self.file_md5_var, style="FileHash.TLabel").pack(anchor="w", pady=(2, 0))

        action_area = ttk.Frame(header, style="Header.TFrame")
        action_area.pack(side="right")
        load_options = {"image": self.icons.get("load"), "compound": "left"} if self.icons.get("load") else {}
        column_options = {"image": self.icons.get("columns"), "compound": "left"} if self.icons.get("columns") else {}
        ttk.Button(action_area, text="Import file", command=self.load_csv, style="Accent.TButton", **load_options).pack(side="left")
        ttk.Button(action_area, text="Compare", command=self.load_compare_file, style="Tool.TButton").pack(side="left", padx=(8, 0))
        self.clear_compare_button = ttk.Button(action_area, text="Clear compare", command=self.clear_compare, style="DangerGhost.TButton")
        self.map_columns_button = ttk.Button(action_area, text="Manage columns", command=self.remap_columns, style="Tool.TButton", **column_options)
        self.map_columns_button.pack(side="left", padx=(8, 0))

        content = tk.PanedWindow(
            shell,
            orient="horizontal",
            sashwidth=8,
            sashrelief="flat",
            bd=0,
            bg=COLORS["app_bg"],
            opaqueresize=True,
        )
        content.pack(fill="both", expand=True)

        left = tk.Frame(content, bg=COLORS["sidebar"], bd=0, highlightthickness=1, highlightbackground="#dbeafe")
        left.configure(width=320)
        left.pack_propagate(False)

        tree_wrap = tk.Frame(left, bg=COLORS["sidebar"])
        tree_wrap.pack(fill="both", expand=True, padx=(10, 6), pady=(12, 12))
        self.tree = ttk.Treeview(tree_wrap, show="tree", style="Sidebar.Treeview")
        self.tree.heading("#0", text="Folders")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<<TreeviewOpen>>", self.on_tree_open)
        self.tree.bind("<Button-1>", self.on_tree_click, add="+")
        self.tree.bind("<Button-2>", self.show_tree_context_menu)
        self.tree.bind("<Button-3>", self.show_tree_context_menu)
        self.tree.tag_configure("plated", foreground=COLORS["accent"])
        self.tree.tag_configure("compare_only_first", foreground="#b45309")
        self.tree.tag_configure("compare_only_second", foreground="#047857")
        self.tree.tag_configure("compare_changed", foreground="#1d4ed8")
        tree_scroll = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        right = ttk.Frame(content, style="Panel.TFrame", padding=16)
        content.add(left, minsize=220, width=320, stretch="never")
        content.add(right, minsize=520, stretch="always")

        topbar = ttk.Frame(right, style="Toolbar.TFrame", padding=(10, 8))
        topbar.pack(fill="x", pady=(0, 12))

        tools = ttk.Frame(topbar, style="Toolbar.TFrame")
        tools.pack(side="right", anchor="ne")

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.on_filter_text_changed())

        filter_options = {"image": self.icons.get("filter"), "compound": "left"} if self.icons.get("filter") else {}
        self.filter_button = ttk.Button(tools, text="Filters", command=self.open_filter_dialog, style="Tool.TButton", **filter_options)
        self.filter_button.pack(side="right", padx=(8, 0))
        self.clear_filter_button = ttk.Button(tools, text="Clear", command=self.clear_column_filters, state="disabled", style="Tool.TButton")
        self.clear_filter_button.pack(side="right", padx=(8, 0))

        search_box = ttk.Frame(tools, style="Search.TFrame", padding=(10, 6))
        search_box.pack(side="right")
        ttk.Label(search_box, text="Search", style="SearchLabel.TLabel").pack(side="left", padx=(0, 8))
        ttk.Entry(search_box, textvariable=self.search_var, width=24, style="Search.TEntry").pack(side="left")

        self.breadcrumb = tk.Frame(topbar, bg=COLORS["panel_alt"])
        self.breadcrumb.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self.breadcrumb_font = tkfont.nametofont("TkDefaultFont").copy()
        self.breadcrumb_font.configure(size=8)
        self.breadcrumb.bind("<Configure>", lambda event: self.schedule_breadcrumb_update())

        self.summary_bar = ttk.Frame(right, style="HitSummary.TFrame", padding=(10, 7))
        self.summary_bar.pack(fill="x", pady=(0, 10))
        self.summary_bar.columnconfigure(0, weight=1)
        self.detail_summary_var = tk.StringVar(value="")
        self.detail_page_var = tk.StringVar(value="")
        ttk.Label(self.summary_bar, textvariable=self.detail_summary_var, style="HitSummary.TLabel").grid(row=0, column=0, sticky="w")
        self.prev_page_button = ttk.Button(self.summary_bar, text="<", width=3, command=self.previous_detail_page, style="FilterGhost.TButton")
        self.prev_page_button.grid(row=0, column=1, sticky="e", padx=(8, 4))
        ttk.Label(self.summary_bar, textvariable=self.detail_page_var, style="HitSummaryMuted.TLabel").grid(row=0, column=2, sticky="e", padx=(0, 4))
        self.next_page_button = ttk.Button(self.summary_bar, text=">", width=3, command=self.next_detail_page, style="FilterGhost.TButton")
        self.next_page_button.grid(row=0, column=3, sticky="e")

        self.details_frame = ttk.Frame(right, style="Panel.TFrame")
        self.details_frame.pack(fill="both", expand=True)
        self.details = ttk.Treeview(self.details_frame, show="tree headings", style="Details.Treeview")
        self.details.heading("#0", text="Name", command=lambda: self.set_sort("name"))
        self.details.column("#0", width=360, minwidth=180, stretch=True)
        self.details.bind("<Button-1>", self.on_details_click, add="+")
        self.details.bind("<Double-1>", self.open_details_item)
        self.details.bind("<Button-2>", self.show_details_context_menu)
        self.details.bind("<Button-3>", self.show_details_context_menu)

        detail_y = ttk.Scrollbar(self.details_frame, orient="vertical", command=self.on_detail_scroll)
        detail_x = ttk.Scrollbar(self.details_frame, orient="horizontal", command=self.details.xview)
        self.details.configure(yscrollcommand=lambda first, last: self.on_detail_yview(detail_y, first, last), xscrollcommand=detail_x.set)
        self.details.grid(row=0, column=0, sticky="nsew")
        detail_y.grid(row=0, column=1, sticky="ns")
        detail_x.grid(row=1, column=0, sticky="ew")
        self.details_frame.columnconfigure(0, weight=1)
        self.details_frame.rowconfigure(0, weight=1)

        self.empty_state = tk.Frame(self.details_frame, bg=COLORS["panel"])
        tk.Label(
            self.empty_state,
            text="No CSV loaded",
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=("TkDefaultFont", 18, "bold"),
        ).pack(pady=(120, 6))
        tk.Label(
            self.empty_state,
            text="Import an FTK CSV, a tree text file, or manage custom CSV columns for path and filename.",
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("TkDefaultFont", 11),
        ).pack()
        ttk.Button(self.empty_state, text="Import file", command=self.load_csv, style="Accent.TButton").pack(pady=(18, 0))
        self.empty_state.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.no_results_state = tk.Frame(self.details_frame, bg=COLORS["panel"])
        tk.Label(
            self.no_results_state,
            text="No hit",
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("TkDefaultFont", 16, "bold"),
        ).place(relx=0.5, rely=0.45, anchor="center")

        ttk.Label(shell, textvariable=self.status_var, anchor="w", padding=(2, 10), style="Status.TLabel").pack(fill="x")

        self.folder_context_menu = tk.Menu(self, tearoff=0)
        self.folder_context_menu.add_command(label="Copy tree...", command=self.open_context_folder_tree_dialog)
        self.folder_context_menu.add_separator()
        self.folder_context_menu.add_command(label="Copy direct child items", command=lambda: self.copy_context_folder_children(False))
        self.folder_context_menu.add_command(label="Copy all child items", command=lambda: self.copy_context_folder_children(True))

        self.item_context_menu = tk.Menu(self, tearoff=0)
        self.item_context_menu.add_command(label="Copy item information", command=self.copy_context_item_information)
        self.item_context_menu.add_command(label="Copy filename", command=self.copy_context_item_filename)
        self.item_context_menu.add_command(label="Copy full path", command=self.copy_context_item_full_path)
        self.item_context_menu.add_separator()
        self.item_context_menu.add_command(label="Properties", command=self.show_context_item_properties)
        self.item_context_menu.add_separator()
        self.item_context_menu.add_command(label="Export current view to CSV", command=self.export_current_view_csv)
        self.item_context_menu.add_command(label="Export checked items to CSV", command=self.export_checked_csv)

        self.detail_folder_context_menu = tk.Menu(self, tearoff=0)
        self.detail_folder_context_menu.add_command(label="Copy tree...", command=self.open_context_folder_tree_dialog)
        self.detail_folder_context_menu.add_separator()
        self.detail_folder_context_menu.add_command(label="Copy direct child items", command=lambda: self.copy_context_folder_children(False))
        self.detail_folder_context_menu.add_command(label="Copy all child items", command=lambda: self.copy_context_folder_children(True))
        self.detail_folder_context_menu.add_separator()
        self.detail_folder_context_menu.add_command(label="Export current view to CSV", command=self.export_current_view_csv)
        self.detail_folder_context_menu.add_command(label="Export checked items to CSV", command=self.export_checked_csv)

        self.selection_context_menu = tk.Menu(self, tearoff=0)
        self.selection_context_menu.add_command(label="Copy tree of selection...", command=self.open_selection_tree_dialog)
        self.selection_context_menu.add_command(label="Copy full paths", command=self.copy_selected_full_paths)
        self.selection_context_menu.add_separator()
        self.selection_context_menu.add_command(label="Check selected items", command=lambda: self.set_selection_checked(True))
        self.selection_context_menu.add_command(label="Uncheck selected items", command=lambda: self.set_selection_checked(False))
        self.selection_context_menu.add_separator()
        self.selection_context_menu.add_command(label="Export selection to CSV", command=self.export_selected_csv)
        self.selection_context_menu.add_command(label="Export checked items to CSV", command=self.export_checked_csv)
        self.selection_context_menu.add_command(label="Export current view to CSV", command=self.export_current_view_csv)

        self.details_context_menu = tk.Menu(self, tearoff=0)
        self.details_context_menu.add_command(label="Export current view to CSV", command=self.export_current_view_csv)
        self.details_context_menu.add_command(label="Export checked items to CSV", command=self.export_checked_csv)
        self.details_context_menu.add_separator()
        self.details_context_menu.add_command(label="Clear checkboxes", command=self.clear_all_checks)


    def _build_import_screen(self):
        self.import_screen = tk.Frame(self, bg=COLORS["app_bg"])
        self.import_screen.pack(fill="both", expand=True)

        panel = tk.Frame(
            self.import_screen,
            bg=COLORS["panel"],
            bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        panel.place(relx=0.5, rely=0.44, anchor="center", width=480)

        ttk.Label(panel, text="Import file", style="ImportTitle.TLabel").pack(anchor="w", padx=24, pady=(24, 6))
        ttk.Label(
            panel,
            text="FTK CSV listings and tree text files load automatically. Other CSV files open column management before import.",
            wraplength=420,
            style="PanelMuted.TLabel",
        ).pack(anchor="w", padx=24, pady=(0, 18))

        button_options = {"image": self.icons.get("load"), "compound": "left"} if self.icons.get("load") else {}
        ttk.Button(
            panel,
            text="Select file",
            command=self.load_csv,
            style="Accent.TButton",
            **button_options,
        ).pack(anchor="w", padx=24, pady=(0, 16))

        ttk.Label(panel, textvariable=self.status_var, style="PanelMuted.TLabel").pack(anchor="w", padx=24, pady=(0, 24))


    def show_browser(self):
        if self.import_screen.winfo_ismapped():
            self.import_screen.pack_forget()
        if not self.main_shell.winfo_ismapped():
            self.main_shell.pack(fill="both", expand=True)

    def busy_overlay_parent(self):
        if hasattr(self, "main_shell") and self.main_shell.winfo_ismapped():
            return self.main_shell
        if hasattr(self, "import_screen") and self.import_screen.winfo_ismapped():
            return self.import_screen
        return self

    def show_busy_overlay(self, message):
        self.busy_message_var.set(message)
        parent = self.busy_overlay_parent()
        if self.busy_overlay and self.busy_overlay.winfo_exists():
            if self.busy_overlay.master is not parent:
                self.busy_overlay.destroy()
                self.busy_overlay = None
            else:
                self.busy_overlay.lift()
                return

        overlay = tk.Frame(parent, bg=COLORS["app_bg"], bd=0)
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

        panel = tk.Frame(
            overlay,
            bg=COLORS["panel"],
            bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        panel.place(relx=0.5, rely=0.44, anchor="center", width=420)

        tk.Label(
            panel,
            textvariable=self.busy_message_var,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=("TkDefaultFont", 13, "bold"),
        ).pack(anchor="w", padx=24, pady=(22, 6))
        tk.Label(
            panel,
            text="Reading data and preparing the view.",
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("TkDefaultFont", 10),
        ).pack(anchor="w", padx=24, pady=(0, 16))
        progress = ttk.Progressbar(panel, mode="indeterminate", length=320)
        progress.pack(fill="x", padx=24, pady=(0, 22))
        progress.start(12)
        overlay.progress = progress

        self.busy_overlay = overlay
        self.busy_overlay.lift()

    def set_busy(self, message, overlay=False):
        self.status_var.set(message)
        self.configure(cursor="watch")
        if overlay:
            self.show_busy_overlay(message)
        elif self.busy_overlay and self.busy_overlay.winfo_exists():
            self.busy_message_var.set(message)
            self.busy_overlay.lift()
        self.update_idletasks()

    def clear_busy(self):
        self.configure(cursor="")
        if self.busy_overlay and self.busy_overlay.winfo_exists():
            progress = getattr(self.busy_overlay, "progress", None)
            if progress:
                progress.stop()
            self.busy_overlay.destroy()
        self.busy_overlay = None
        self.update_idletasks()

    def _configure_styles(self, style):
        style.configure(".", font=("TkDefaultFont", 10))
        style.configure("App.TFrame", background=COLORS["app_bg"])
        style.configure("Panel.TFrame", background=COLORS["panel"])
        style.configure("Header.TFrame", background="#ecfdf5")
        style.configure("Toolbar.TFrame", background=COLORS["panel_alt"])
        style.configure("Search.TFrame", background="#eef2ff", relief="flat")
        style.configure("ImportTitle.TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=("TkDefaultFont", 20, "bold"))
        style.configure("PanelTitle.TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=("TkDefaultFont", 12, "bold"))
        style.configure("FileTitle.TLabel", background="#ecfdf5", foreground=COLORS["text"], font=("TkDefaultFont", 12, "bold"))
        style.configure("FileHash.TLabel", background="#ecfdf5", foreground=COLORS["muted"], font=("TkDefaultFont", 9))
        style.configure("PanelMuted.TLabel", background=COLORS["panel"], foreground=COLORS["muted"], font=("TkDefaultFont", 10))
        style.configure("SearchLabel.TLabel", background="#eef2ff", foreground="#475569", font=("TkDefaultFont", 10))
        style.configure("HitSummary.TFrame", background="#ecfeff")
        style.configure("HitSummary.TLabel", background="#ecfeff", foreground="#0f766e", font=("TkDefaultFont", 10, "bold"))
        style.configure("HitSummaryMuted.TLabel", background="#ecfeff", foreground="#64748b", font=("TkDefaultFont", 10))
        style.configure("FilterPreset.TFrame", background="#ecfdf5")
        style.configure("FilterPreset.TLabel", background="#ecfdf5", foreground="#0f766e", font=("TkDefaultFont", 10, "bold"))
        style.configure("FilterRule.TFrame", background="#f8fafc")
        style.configure("FilterHeader.TLabel", background=COLORS["panel"], foreground="#1d4ed8", font=("TkDefaultFont", 10, "bold"))
        style.configure("FilterRuleMuted.TLabel", background="#f8fafc", foreground="#0f766e", font=("TkDefaultFont", 10, "bold"))
        style.configure("FilterHint.TLabel", background="#f8fafc", foreground="#64748b", padding=(10, 6), font=("TkDefaultFont", 10, "italic"))
        style.configure("FilterChipMore.TLabel", background="#f8fafc", foreground="#64748b", font=("TkDefaultFont", 9, "bold"))
        style.configure("Status.TLabel", background=COLORS["app_bg"], foreground=COLORS["muted"], font=("TkDefaultFont", 10))
        style.configure("TLabel", background=COLORS["panel"], foreground=COLORS["text"])
        style.configure("TCheckbutton", background=COLORS["panel"], foreground=COLORS["text"], focuscolor=COLORS["panel"])
        style.map("TCheckbutton", background=[("active", COLORS["panel"])])
        style.configure("TRadiobutton", background=COLORS["panel"], foreground=COLORS["text"], focuscolor=COLORS["panel"])
        style.map("TRadiobutton", background=[("active", COLORS["panel"])])
        style.configure("TButton", padding=(12, 7), borderwidth=0)
        style.configure("Mini.TButton", padding=(7, 4), borderwidth=0)
        style.configure("MiniDanger.TButton", padding=(7, 4), borderwidth=0, foreground=COLORS["danger"])
        style.configure("Tool.TButton", background="#e0f2fe", foreground="#075985", padding=(12, 7), borderwidth=0)
        style.map("Tool.TButton", background=[("active", "#bae6fd"), ("pressed", "#7dd3fc"), ("disabled", "#f1f5f9")], foreground=[("disabled", "#94a3b8")])
        style.configure("DangerGhost.TButton", background="#fee2e2", foreground=COLORS["danger"], padding=(12, 7), borderwidth=0)
        style.map("DangerGhost.TButton", background=[("active", "#fecaca"), ("pressed", "#fca5a5"), ("disabled", "#f1f5f9")], foreground=[("disabled", "#94a3b8")])
        style.configure("FilterAdd.TButton", background="#dbeafe", foreground="#1d4ed8", padding=(8, 4), borderwidth=0, font=("TkDefaultFont", 10, "bold"))
        style.map("FilterAdd.TButton", background=[("active", "#bfdbfe"), ("pressed", "#93c5fd")], foreground=[("disabled", "#94a3b8")])
        style.configure("FilterDelete.TButton", background="#fee2e2", foreground=COLORS["danger"], padding=(8, 4), borderwidth=0, font=("TkDefaultFont", 10, "bold"))
        style.map("FilterDelete.TButton", background=[("active", "#fecaca"), ("pressed", "#fca5a5")], foreground=[("disabled", "#94a3b8")])
        style.configure("FilterEdit.TButton", background="#ccfbf1", foreground=COLORS["accent"], padding=(5, 4), borderwidth=0)
        style.map("FilterEdit.TButton", background=[("active", "#99f6e4"), ("pressed", "#5eead4")], foreground=[("disabled", "#94a3b8")])
        style.configure("FilterGhost.TButton", background="#f1f5f9", foreground="#334155", padding=(12, 7), borderwidth=0)
        style.map("FilterGhost.TButton", background=[("active", "#e2e8f0"), ("pressed", "#cbd5e1")])
        style.configure("FilterPreset.TButton", background="#ccfbf1", foreground="#0f766e", padding=(12, 7), borderwidth=0)
        style.map("FilterPreset.TButton", background=[("active", "#99f6e4"), ("pressed", "#5eead4")])
        style.configure("FilterActive.TButton", background="#f59e0b", foreground="#111827", padding=(12, 7), borderwidth=0)
        style.map("FilterActive.TButton", background=[("active", "#fbbf24"), ("pressed", "#f59e0b")], foreground=[("disabled", "#6b7280")])
        style.configure("Accent.TButton", background=COLORS["accent"], foreground="#ffffff", padding=(14, 8), borderwidth=0)
        style.map("Accent.TButton", background=[("active", COLORS["accent_hover"]), ("pressed", COLORS["accent_hover"])], foreground=[("disabled", "#d1d5db")])
        style.configure("Search.TEntry", fieldbackground=COLORS["panel_alt"], bordercolor=COLORS["panel_alt"], lightcolor=COLORS["panel_alt"], darkcolor=COLORS["panel_alt"])
        style.configure("Filter.TEntry", padding=(10, 6), fieldbackground="#ffffff", bordercolor="#cbd5e1", lightcolor="#cbd5e1", darkcolor="#cbd5e1")
        style.configure(
            "Filter.TCombobox",
            padding=(8, 5),
            fieldbackground="#ffffff",
            background="#f1f5f9",
            foreground=COLORS["text"],
            bordercolor="#cbd5e1",
            lightcolor="#cbd5e1",
            darkcolor="#cbd5e1",
            arrowcolor=COLORS["accent"],
        )
        style.map(
            "Filter.TCombobox",
            fieldbackground=[("readonly", "#ffffff")],
            selectbackground=[("readonly", "#ccfbf1")],
            selectforeground=[("readonly", COLORS["text"])],
        )
        style.configure(
            "Sidebar.Treeview",
            background=COLORS["sidebar"],
            fieldbackground=COLORS["sidebar"],
            foreground=COLORS["sidebar_text"],
            borderwidth=0,
            rowheight=28,
        )
        style.configure(
            "Sidebar.Treeview.Heading",
            background="#e0f2fe",
            foreground="#075985",
            relief="flat",
            padding=(8, 8),
            font=("TkDefaultFont", 10, "bold"),
        )
        style.map(
            "Sidebar.Treeview",
            background=[("selected", "#dbeafe")],
            foreground=[("selected", COLORS["text"])],
        )
        style.configure(
            "Details.Treeview",
            background=COLORS["panel"],
            fieldbackground=COLORS["panel"],
            foreground=COLORS["text"],
            rowheight=30,
            borderwidth=0,
        )
        style.map("Details.Treeview", background=[("selected", "#dbeafe")], foreground=[("selected", COLORS["text"])])
        style.configure(
            "Details.Treeview.Heading",
            background="#eff6ff",
            foreground="#334155",
            relief="flat",
            padding=(8, 8),
            font=("TkDefaultFont", 10, "bold"),
        )

    def load_csv(self):
        file_path = filedialog.askopenfilename(filetypes=[("Supported files", "*.csv *.txt"), ("CSV", "*.csv"), ("Tree text", "*.txt"), ("All files", "*.*")])
        if not file_path:
            return

        file_name = os.path.basename(file_path)
        self.set_busy(f"Loading {file_name}...", overlay=True)
        tree_error = None
        if os.path.splitext(file_path)[1].lower() in {".txt", ".tree"}:
            try:
                self.import_tree_listing(file_path)
                return
            except Exception as exc:
                tree_error = exc

        try:
            self.set_busy(f"Reading {file_name}...", overlay=True)
            headers, rows, encoding, delimiter = read_csv_rows(file_path)
            csv_md5 = file_md5(file_path)
        except Exception as exc:
            self.clear_busy()
            if tree_error:
                messagebox.showerror("File could not be loaded", f"Tree text: {tree_error}\nCSV: {exc}")
            else:
                messagebox.showerror("CSV could not be loaded", str(exc))
            self.status_var.set("Import failed.")
            return
        self.clear_busy()

        profile, saved_profile = load_import_profile(headers)
        self.saved_profile_name = ""
        if profile:
            self.saved_profile_name = (saved_profile or {}).get("name") or "Saved import profile"
        else:
            profile = detect_import_profile(headers)

        if not self.saved_profile_name and (profile is None or not is_ftk_listing(headers)):
            dialog = ImportDialog(self, headers, profile=profile, action_label="Import")
            self.wait_window(dialog)
            if not dialog.result:
                self.status_var.set("Import canceled.")
                return
            profile = dialog.result

        self.current_file = file_path
        self.headers = headers
        self.rows = rows
        self.profile = profile
        self.import_kind = "csv"
        self.reset_compare_state()
        self.column_filters.clear()
        if self.search_var.get():
            self.search_var.set("")
        self.apply_path_style_detection(profile, rows)
        if not self.resolve_size_units():
            return
        self.save_current_import_profile(file_name)
        self.set_busy(f"Building view for {file_name}...", overlay=True)
        self.metadata_columns = list(profile.metadata_columns)
        self.rebuild()
        self.show_browser()
        self.file_title_var.set(file_name)
        self.file_md5_var.set(f"MD5: {csv_md5}")
        self.show_import_warnings()

        delimiter_name = {"\t": "tab", ",": "comma", ";": "semicolon", "|": "pipe"}.get(delimiter, delimiter)
        profile_note = " Saved profile applied." if self.saved_profile_name else ""
        warning_note = f" Import warnings: {self.warning_count()}." if self.warning_count() else ""
        self.status_var.set(
            f"Loaded {file_name}: {len(rows):,} rows, {encoding}, {delimiter_name} delimiter. "
            f"Path style: {path_style_label(profile.path_style)}.{profile_note}{warning_note}"
        )
        self.clear_busy()

    def csv_path_values(self, rows, profile):
        values = []
        for row in rows:
            if profile.full_path_column:
                value = clean_cell(row.get(profile.full_path_column))
            else:
                folder = clean_cell(row.get(profile.folder_column)) if profile.folder_column else ""
                name = clean_cell(row.get(profile.filename_column)) if profile.filename_column else ""
                trimmed_folder = folder.rstrip("/\\")
                value = f"{trimmed_folder}/{name}" if trimmed_folder and name else name or folder
            if value:
                values.append(value)
        return values

    def apply_path_style_detection(self, profile, rows):
        resolved_style, warnings, _stats = path_style_warnings(self.csv_path_values(rows, profile), profile.path_style)
        profile.path_style = resolved_style
        self.import_warnings = warnings

    def warning_count(self):
        return sum(1 for warning in self.import_warnings if not warning.startswith("Path style auto-detected"))

    def show_import_warnings(self):
        important = [warning for warning in self.import_warnings if not warning.startswith("Path style auto-detected")]
        if important:
            messagebox.showwarning("Import warnings", "\n\n".join(self.import_warnings))

    def save_current_import_profile(self, file_name):
        if not self.headers or not self.profile:
            return
        profile_name = self.saved_profile_name or f"{os.path.splitext(file_name)[0]} import profile"
        try:
            save_import_profile(self.headers, self.profile, name=profile_name)
        except OSError:
            return

    def import_tree_listing(self, file_path):
        file_name = os.path.basename(file_path)
        self.set_busy(f"Reading {file_name}...", overlay=True)
        entries, encoding = read_tree_listing(file_path)
        csv_md5 = file_md5(file_path)

        self.current_file = file_path
        self.headers = []
        self.rows = []
        self.profile = ImportProfile(size_units={})
        self.metadata_columns = []
        self.import_kind = "tree"
        self.import_warnings = []
        self.saved_profile_name = ""
        self.reset_compare_state()
        self.column_filters.clear()
        if self.search_var.get():
            self.search_var.set("")
        self.set_busy(f"Building view for {file_name}...", overlay=True)
        self.rebuild(entries=entries)
        self.show_browser()
        self.file_title_var.set(file_name)
        self.file_md5_var.set(f"MD5: {csv_md5}")

        file_count = sum(not entry.is_folder for entry in entries)
        folder_count = sum(entry.is_folder for entry in entries)
        self.status_var.set(f"Loaded {file_name}: {file_count:,} files, {folder_count:,} folders, {encoding}.")
        self.clear_busy()

    def load_compare_file(self):
        if not self.entries or not self.import_kind:
            messagebox.showinfo("No file loaded", "Import a CSV or tree text file first.")
            return

        if self.import_kind == "tree":
            filetypes = [("Tree text", "*.txt *.tree"), ("All files", "*.*")]
        else:
            filetypes = [("CSV", "*.csv"), ("All files", "*.*")]

        file_path = filedialog.askopenfilename(filetypes=filetypes)
        if not file_path:
            return

        file_name = os.path.basename(file_path)
        self.set_busy(f"Reading compare file {file_name}...", overlay=True)
        try:
            if self.import_kind == "tree":
                compare_entries, _encoding = read_tree_listing(file_path)
            else:
                headers, rows, _encoding, _delimiter = read_csv_rows(file_path)
                if headers != self.headers:
                    self.clear_busy()
                    messagebox.showerror("Compare not possible", "CSV columns must match exactly.")
                    return
                compare_entries = [
                    entry
                    for row in rows
                    if (entry := self.entry_from_row(row, self.profile, self.metadata_columns))
                ]
        except Exception as exc:
            self.clear_busy()
            messagebox.showerror("Compare failed", str(exc))
            return
        self.clear_busy()

        first_roots = self.folder_choices_for_entries(self.base_entries or self.entries)
        second_roots = self.folder_choices_for_entries(compare_entries)
        dialog = CompareRootDialog(self, first_roots, second_roots, bool(self.metadata_columns))
        self.wait_window(dialog)
        if not dialog.result:
            return

        first_root, second_root, compare_metadata = dialog.result
        first_entries = self.entries_for_compare_root(self.base_entries or self.entries, first_root)
        second_entries = self.entries_for_compare_root(compare_entries, second_root)
        if not first_entries and not second_entries:
            messagebox.showerror("Compare not possible", "Both selected roots are empty.")
            return

        self.set_busy(f"Building compare view for {file_name}...", overlay=True)
        self.compare_file = file_path
        self.compare_roots = (first_root, second_root)
        self.compare_entries = compare_entries
        merged_entries, summary = self.build_compare_entries(first_entries, second_entries, compare_metadata=compare_metadata)
        self.compare_active = True
        self.compare_summary = summary
        self.rebuild(entries=merged_entries, preserve_base=True)
        self.set_clear_compare_visible(True)
        self.status_var.set(
            f"Compare: possible renamed/moved {summary['path_changed']:,}, missing in compare {summary['only_first']:,}, new in compare {summary['only_second']:,}, metadata changed {summary['changed']:,}."
        )
        self.clear_busy()

    def clear_compare(self):
        if not self.compare_active:
            return
        self.compare_active = False
        self.compare_file = ""
        self.compare_roots = ("/", "/")
        self.compare_entries = []
        self.compare_status_by_path = {}
        self.compare_detail_by_path = {}
        self.compare_summary = {}
        self.close_compare_detail_window()
        self.set_clear_compare_visible(False)
        self.rebuild(entries=self.base_entries, preserve_base=True)
        self.status_var.set("Compare cleared.")

    def reset_compare_state(self):
        self.compare_active = False
        self.compare_file = ""
        self.compare_roots = ("/", "/")
        self.compare_entries = []
        self.compare_status_by_path = {}
        self.compare_detail_by_path = {}
        self.compare_summary = {}
        self.close_compare_detail_window()
        self.set_clear_compare_visible(False)

    def set_clear_compare_visible(self, visible):
        if not hasattr(self, "clear_compare_button"):
            return
        if visible:
            if not self.clear_compare_button.winfo_ismapped():
                self.clear_compare_button.pack(side="left", padx=(8, 0), before=self.map_columns_button)
        elif self.clear_compare_button.winfo_ismapped():
            self.clear_compare_button.pack_forget()

    def close_compare_detail_window(self):
        if self.compare_detail_window and self.compare_detail_window.winfo_exists():
            self.compare_detail_window.destroy()
        self.compare_detail_window = None

    def folder_choices_for_entries(self, entries):
        folders = {"/"}
        for entry in entries:
            self.add_folder_ancestors(folders, entry.folder)
            if entry.is_folder:
                folders.add(entry.folder)
        return sorted(folders, key=lambda value: (value.count("/"), value.lower()))

    def entries_for_compare_root(self, entries, root):
        root = normalize_path(root) or "/"
        aligned = []
        for entry in entries:
            target = entry.folder if entry.is_folder else entry.full_path
            if not self.path_is_under_root(target, root):
                continue

            if entry.is_folder:
                relative_folder = self.path_relative_to_root(entry.folder, root)
                if relative_folder == "/":
                    continue
                aligned.append(
                    FileEntry(
                        name=display_name(relative_folder),
                        folder=relative_folder,
                        full_path=relative_folder,
                        metadata=dict(entry.metadata),
                        is_folder=True,
                        properties=dict(entry.properties or {}),
                    )
                )
                continue

            relative_path = self.path_relative_to_root(entry.full_path, root)
            aligned.append(
                FileEntry(
                    name=entry.name,
                    folder=parent_path(relative_path),
                    full_path=relative_path,
                    metadata=dict(entry.metadata),
                    is_folder=False,
                    properties=dict(entry.properties or {}),
                )
            )
        return aligned

    def path_is_under_root(self, path, root):
        path = normalize_path(path) or "/"
        root = normalize_path(root) or "/"
        if root == "/":
            return True
        return path == root or path.startswith(root + "/")

    def path_relative_to_root(self, path, root):
        path = normalize_path(path) or "/"
        root = normalize_path(root) or "/"
        if root == "/":
            return path
        if path == root:
            return "/"
        return normalize_path(path[len(root):])

    def build_compare_entries(self, first_entries, second_entries, compare_metadata=True):
        first_files = {entry.full_path: entry for entry in first_entries if not entry.is_folder}
        second_files = {entry.full_path: entry for entry in second_entries if not entry.is_folder}
        first_folders = self.collect_folder_paths(first_entries)
        second_folders = self.collect_folder_paths(second_entries)

        statuses = {}
        details = {}
        summary = {"only_first": 0, "only_second": 0, "changed": 0, "path_changed": 0}
        path_change_pairs = self.find_path_change_pairs(first_files, second_files)
        path_changed_first = {first_path for first_path, _second_path in path_change_pairs}
        path_changed_second = {second_path for _first_path, second_path in path_change_pairs}

        for first_path, second_path in path_change_pairs:
            statuses[first_path] = "path_changed"
            statuses[second_path] = "path_changed"
            detail = {
                "status": "path_changed",
                "loaded_path": first_path,
                "compare_path": second_path,
                "pair_key": first_path,
                "message": "This looks like the same item, but its name or path changed in the compare file.",
            }
            details[first_path] = detail
            details[second_path] = dict(detail, alias=True)
            summary["path_changed"] += 1

        for path in sorted(first_files.keys() | second_files.keys()):
            if path in path_changed_first or path in path_changed_second:
                continue
            if path not in second_files:
                statuses[path] = "only_first"
                details[path] = {
                    "status": "only_first",
                    "message": "This item exists in the loaded file but is missing from the compare file.",
                }
                summary["only_first"] += 1
            elif path not in first_files:
                statuses[path] = "only_second"
                details[path] = {
                    "status": "only_second",
                    "message": "This item is new in the compare file and was not present in the loaded file.",
                }
                summary["only_second"] += 1
            elif compare_metadata and self.entry_compare_signature(first_files[path]) != self.entry_compare_signature(second_files[path]):
                statuses[path] = "changed"
                details[path] = {
                    "status": "changed",
                    "changes": self.metadata_changes(first_files[path], second_files[path]),
                }
                summary["changed"] += 1

        for path in sorted(first_folders | second_folders):
            if path == "/":
                continue
            if path not in second_folders:
                statuses[path] = "only_first"
                details.setdefault(path, {
                    "status": "only_first",
                    "message": "This folder exists in the loaded file but is missing from the compare file.",
                })
            elif path not in first_folders:
                statuses[path] = "only_second"
                details.setdefault(path, {
                    "status": "only_second",
                    "message": "This folder is new in the compare file and was not present in the loaded file.",
                })

        for diff_path, status in list(statuses.items()):
            parent = diff_path if status in {"only_first", "only_second"} and diff_path in first_folders | second_folders else parent_path(diff_path)
            while parent and parent != "/":
                statuses.setdefault(parent, "changed")
                details.setdefault(parent, {
                    "status": "changed",
                    "message": "Folder contains one or more differences below it.",
                })
                parent = parent_path(parent)
            statuses.setdefault("/", "changed")
            details.setdefault("/", {
                "status": "changed",
                "message": "This compare contains one or more differences.",
            })

        merged_entries = []
        for folder in sorted((first_folders | second_folders) - {"/"}, key=str.lower):
            merged_entries.append(FileEntry(display_name(folder), folder, folder, {}, is_folder=True, properties={}))

        for path in sorted(first_files.keys() | second_files.keys(), key=str.lower):
            merged_entries.append(first_files.get(path) or second_files[path])

        self.compare_status_by_path = statuses
        self.compare_detail_by_path = details
        return merged_entries, summary

    def collect_folder_paths(self, entries):
        folders = {"/"}
        for entry in entries:
            self.add_folder_ancestors(folders, entry.folder)
            if entry.is_folder:
                folders.add(entry.folder)
        return folders

    def add_folder_ancestors(self, folders, folder):
        folder = normalize_path(folder) or "/"
        while True:
            folders.add(folder)
            if folder == "/":
                break
            folder = parent_path(folder)

    def entry_compare_signature(self, entry):
        return tuple((column, entry.metadata.get(column, "")) for column in self.metadata_columns)

    def find_path_change_pairs(self, first_files, second_files):
        first_only = {path: first_files[path] for path in first_files.keys() - second_files.keys()}
        second_only = {path: second_files[path] for path in second_files.keys() - first_files.keys()}
        pairs = []
        used_first = set()
        used_second = set()

        for key_mode in ("folder", "global"):
            first_groups = {}
            second_groups = {}
            for path, entry in first_only.items():
                if path in used_first:
                    continue
                key = self.path_change_match_key(entry, key_mode)
                if key is not None:
                    first_groups.setdefault(key, []).append(path)
            for path, entry in second_only.items():
                if path in used_second:
                    continue
                key = self.path_change_match_key(entry, key_mode)
                if key is not None:
                    second_groups.setdefault(key, []).append(path)

            for key in sorted(first_groups.keys() & second_groups.keys(), key=str):
                first_paths = first_groups[key]
                second_paths = second_groups[key]
                if len(first_paths) != 1 or len(second_paths) != 1:
                    continue
                first_path = first_paths[0]
                second_path = second_paths[0]
                used_first.add(first_path)
                used_second.add(second_path)
                pairs.append((first_path, second_path))

        return pairs

    def path_change_match_key(self, entry, mode):
        signature = self.identifying_compare_signature(entry)
        if not signature:
            return None
        if mode == "folder":
            return (entry.folder, signature)
        return signature

    def identifying_compare_signature(self, entry):
        signature = []
        for column in self.metadata_columns:
            lowered = column.lower()
            if any(token in lowered for token in ("file name", "filename", "name", "path", "pfad", "directory", "folder", "ordner")):
                continue
            value = entry.metadata.get(column, "")
            if value:
                signature.append((column, value))
        return tuple(signature)

    def metadata_changes(self, first_entry, second_entry):
        changes = []
        for column in self.metadata_columns:
            first_value = first_entry.metadata.get(column, "")
            second_value = second_entry.metadata.get(column, "")
            if first_value != second_value:
                changes.append((column, first_value, second_value))
        return changes

    def remap_columns(self):
        if not self.headers:
            messagebox.showinfo("No CSV loaded", "Import a CSV file first.")
            return
        dialog = ImportDialog(self, self.headers, profile=self.profile, selected_metadata=self.metadata_columns, action_label="Apply")
        self.wait_window(dialog)
        if dialog.result:
            self.profile = dialog.result
            self.apply_path_style_detection(self.profile, self.rows)
            if not self.resolve_size_units():
                return
            self.metadata_columns = list(dialog.result.metadata_columns)
            self.save_current_import_profile(os.path.basename(self.current_file or "current_file"))
            self.show_import_warnings()
            self.reset_compare_state()
            self.prune_column_filters()
            self.rebuild()

    def resolve_size_units(self):
        if self.profile.size_units is None:
            self.profile.size_units = {}

        ambiguous = [
            column
            for column in self.profile.metadata_columns
            if detect_size_unit(column) == "ask" and column not in self.profile.size_units
        ]
        if not ambiguous:
            return True

        dialog = SizeUnitDialog(self, ambiguous)
        self.wait_window(dialog)
        if dialog.result is None:
            return False

        self.profile.size_units.update(dialog.result)
        return True

    def rebuild(self, entries=None, plate_root=False, preserve_base=False):
        self.entries = list(entries) if entries is not None else [entry for row in self.rows if (entry := self.entry_from_row(row))]
        if not preserve_base:
            self.base_entries = list(self.entries)
        self.plated_folders.clear()
        self.checked_folders.clear()
        self.checked_file_entries.clear()
        if plate_root and self.entries:
            self.plated_folders.add("/")
        self.build_structure()
        self.configure_detail_columns()
        self.build_tree()
        if self.entries:
            self.empty_state.place_forget()
        else:
            self.empty_state.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.update_no_results_state(False)
        first = self.tree.get_children()
        if first:
            self.tree.selection_set(first[0])
            self.tree.focus(first[0])
            self.on_select(None)
        else:
            self.refresh_details()

    def entry_from_row(self, row, profile=None, metadata_columns=None):
        profile = profile or self.profile
        metadata_columns = self.metadata_columns if metadata_columns is None else metadata_columns
        full_path = ""
        if profile.full_path_column:
            full_path = clean_cell(row.get(profile.full_path_column))
        elif profile.filename_column:
            folder = clean_cell(row.get(profile.folder_column)) if profile.folder_column else ""
            name = clean_cell(row.get(profile.filename_column))
            folder = folder.rstrip("/\\")
            full_path = f"{folder}/{name}" if folder else name
            full_path = full_path.replace(" / ", "/")

        normalized = normalize_path(full_path, profile.path_style)
        if not normalized:
            return None

        raw_full = clean_cell(row.get(profile.full_path_column)) if profile.full_path_column else full_path
        raw_name = clean_cell(row.get(profile.filename_column)) if profile.filename_column else ""
        is_folder = raw_full.endswith(("\\", "/")) or raw_name.lower() in {"[root]", ".", ".."}
        name = raw_name or display_name(normalized)

        folder = normalized if is_folder else parent_path(normalized)
        if is_folder and name in {"", "[root]"}:
            name = display_name(folder)

        properties = {column: self.formatted_row_value(row, column, profile) for column in self.headers}
        metadata = {}
        for column in metadata_columns:
            metadata[column] = properties.get(column, self.formatted_row_value(row, column, profile))
        return FileEntry(name=name, folder=folder, full_path=normalized, metadata=metadata, is_folder=is_folder, properties=properties)

    def formatted_row_value(self, row, column, profile=None):
        value = clean_cell(row.get(column))
        profile = profile or self.profile
        size_units = profile.size_units or {} if profile else {}
        unit = size_units.get(column)
        if unit is None:
            unit = detect_size_unit(column)
            if unit == "ask":
                unit = None
        if unit:
            return format_size(value, unit)
        return value

    def build_structure(self):
        self.tree_data = {"/": set()}
        self.folder_entries = {}
        self.folder_counts = {}
        self.folder_sizes = {}

        for entry in self.entries:
            if entry.is_folder:
                self.ensure_folder(entry.folder)
                continue

            self.ensure_folder(entry.folder)
            self.folder_entries.setdefault(entry.folder, []).append(entry)
            size = self.entry_size_bytes(entry)
            folder = entry.folder
            while True:
                self.folder_counts[folder] = self.folder_counts.get(folder, 0) + 1
                self.folder_sizes[folder] = self.folder_sizes.get(folder, 0) + size
                if folder == "/":
                    break
                folder = parent_path(folder)

        for folder in self.tree_data:
            self.folder_counts.setdefault(folder, 0)
            self.folder_sizes.setdefault(folder, 0)

    def ensure_folder(self, folder):
        folder = normalize_path(folder) or "/"
        if folder == "/":
            self.tree_data.setdefault("/", set())
            return

        parts = folder.strip("/").split("/")
        current = ""
        for part in parts:
            current += "/" + part
            parent = parent_path(current)
            self.tree_data.setdefault(parent, set()).add(current)
            self.tree_data.setdefault(current, set())

    def entry_size_bytes(self, entry):
        if not self.profile or not self.profile.size_units:
            return 0

        for column, unit in self.profile.size_units.items():
            if unit == "keep":
                continue
            value = entry.metadata.get(column, "")
            size = parse_size_label(value)
            if size is not None:
                return size
        return 0

    def configure_detail_columns(self):
        self.details["columns"] = self.metadata_columns
        if self.sort_column != "name" and self.sort_column not in self.metadata_columns:
            self.sort_column = "name"
            self.sort_descending = False
        self.prune_column_filters()
        self.update_sort_headings()
        for column in self.metadata_columns:
            self.details.heading(column, text=column, command=lambda c=column: self.set_sort(c))
            width = 150
            if "path" in column.lower() or "pfad" in column.lower():
                width = 280
            elif detect_size_unit(column):
                width = 110
            self.details.column(column, width=width, minwidth=80, stretch=True)
        self.update_sort_headings()
        self.update_filter_button()

    def available_filter_columns(self):
        return [FILTER_NAME_COLUMN, FILTER_PATH_COLUMN, *self.metadata_columns]

    def prune_column_filters(self):
        allowed = set(self.available_filter_columns())
        self.column_filters = [clause for clause in self.normalized_filter_clauses() if clause.column in allowed]
        self.update_filter_button()

    def open_filter_dialog(self):
        if not self.entries:
            messagebox.showinfo("No file loaded", "Import a CSV or tree text file first.")
            return
        dialog = ColumnFilterDialog(self, self.available_filter_columns(), self.column_filters)
        self.wait_window(dialog)
        if dialog.result is None:
            return
        self.column_filters = dialog.result
        self.update_filter_button()
        self.update_sort_headings()
        self.refresh_details()

    def clear_column_filters(self):
        if not self.column_filters and not self.search_var.get().strip():
            return
        self.column_filters.clear()
        if self.search_var.get():
            self.search_var.set("")
        self.update_filter_button()
        self.update_sort_headings()
        self.refresh_details()

    def on_filter_text_changed(self):
        self.update_filter_button()
        self.schedule_refresh_details()

    def update_filter_button(self):
        if not hasattr(self, "filter_button"):
            return
        count = len(self.normalized_filter_clauses()) + (1 if self.search_var.get().strip() else 0)
        self.filter_button.configure(text=f"Filters ({count})" if count else "Filters")
        self.filter_button.configure(style="FilterActive.TButton" if count else "Tool.TButton")
        if hasattr(self, "clear_filter_button"):
            self.clear_filter_button.configure(state="normal" if count else "disabled")

    def folder_matches_filters(self, path):
        return self.filter_clauses_match(lambda column: self.folder_filter_value(path, column))

    def entry_matches_filters(self, entry, display):
        return self.filter_clauses_match(lambda column: self.entry_filter_value(entry, display, column))

    def filter_clauses_match(self, value_provider):
        result = None
        for clause in self.normalized_filter_clauses():
            match = self.value_matches_filter(value_provider(clause.column), clause)
            if result is None:
                result = match
            elif clause.logical == "OR":
                result = result or match
            else:
                result = result and match
        return True if result is None else result

    def folder_filter_value(self, path, column):
        if column == FILTER_NAME_COLUMN:
            return display_name(path)
        if column == FILTER_PATH_COLUMN:
            return path
        return ""

    def entry_filter_value(self, entry, display, column):
        if column == FILTER_NAME_COLUMN:
            return display
        if column == FILTER_PATH_COLUMN:
            return entry.full_path
        return entry.metadata.get(column, "")

    def normalized_filter_clauses(self):
        if isinstance(self.column_filters, dict):
            return [
                FilterClause(column=column, operator=column_filter.operator, value=column_filter.value)
                for column, column_filter in self.column_filters.items()
            ]

        clauses = []
        allowed = set(self.available_filter_columns()) if hasattr(self, "metadata_columns") else set()
        for clause in self.column_filters or []:
            column = getattr(clause, "column", "")
            if allowed and column not in allowed:
                continue
            operator = getattr(clause, "operator", FILTER_ANY)
            if operator == FILTER_ANY:
                continue
            logical = getattr(clause, "logical", "AND") or "AND"
            clauses.append(FilterClause(column=column, operator=operator, value=getattr(clause, "value", ""), logical=logical))
        return clauses

    def filtered_columns(self):
        return {clause.column for clause in self.normalized_filter_clauses()}

    def value_matches_filter(self, value, column_filter):
        text = clean_cell(value)
        targets = split_filter_values(column_filter.value)
        operator = column_filter.operator

        if operator == FILTER_ANY:
            return True
        if operator in {"Is empty", "Is not set"}:
            return not text
        if operator in {"Is not empty", "Is set"}:
            return bool(text)

        text_lower = text.lower()
        target_lowers = [target.lower() for target in targets]

        if operator == "Contains":
            return any(target in text_lower for target in target_lowers)
        if operator == "Does not contain":
            return all(target not in text_lower for target in target_lowers)
        if operator == "Equals":
            return any(text_lower == target for target in target_lowers)
        if operator == "Does not equal":
            return all(text_lower != target for target in target_lowers)
        if operator == "Starts with":
            return any(text_lower.startswith(target) for target in target_lowers)
        if operator == "Does not start with":
            return all(not text_lower.startswith(target) for target in target_lowers)
        if operator == "Ends with":
            return any(text_lower.endswith(target) for target in target_lowers)
        if operator == "Does not end with":
            return all(not text_lower.endswith(target) for target in target_lowers)

        if operator in NUMERIC_FILTERS:
            target = clean_cell(column_filter.value)
            text_number = parse_size_label(text)
            if text_number is None:
                text_number = parse_number(text)
            target_number = parse_size_label(target)
            if target_number is None:
                target_number = parse_number(target)
            if text_number is None or target_number is None:
                return False
            if operator == "Greater than":
                return text_number > target_number
            if operator == "Less than":
                return text_number < target_number

        return True

    def tree_insert(self, tree, parent, index, image=None, **options):
        if image:
            options["image"] = image
        return tree.insert(parent, index, **options)

    def build_tree(self):
        self.tree_populated = set()
        self.tree.delete(*self.tree.get_children())
        self.tree_insert(self.tree, "", "end", iid="/", text=self.folder_label("/", "Root"), image=self.folder_icon("/"), open=True, tags=self.folder_tags("/"))
        self.populate_tree_node("/")

    def insert_node(self, parent_ui, path):
        name = display_name(path)
        iid = self.tree_insert(self.tree, parent_ui, "end", text=self.folder_label(path, name), iid=path, image=self.folder_icon(path), tags=self.folder_tags(path))
        if self.tree_data.get(path):
            self.tree.insert(iid, "end", iid=self.dummy_iid(path), text="")
        return iid

    def dummy_iid(self, path):
        return f"{path}{TREE_DUMMY_SUFFIX}"

    def is_dummy_iid(self, iid):
        return iid.endswith(TREE_DUMMY_SUFFIX)

    def populate_tree_node(self, path):
        if path in self.tree_populated or not self.tree.exists(path):
            return

        for child in self.tree.get_children(path):
            if self.is_dummy_iid(child):
                self.tree.delete(child)

        for child in sorted(self.tree_data.get(path, set()), key=str.lower):
            if not self.tree.exists(child):
                self.insert_node(path, child)
        self.tree_populated.add(path)

    def on_tree_open(self, event):
        path = self.tree.focus()
        if path:
            self.populate_tree_node(path)

    def folder_label(self, path, name):
        count = self.folder_counts.get(path, 0)
        if self.has_folder_sizes():
            size = format_size_bytes(self.folder_sizes.get(path, 0))
            return f"{name} ({count}, {size})"
        return f"{name} ({count})"

    def has_folder_sizes(self):
        if not self.profile or not self.profile.size_units:
            return False
        return any(unit != "keep" for unit in self.profile.size_units.values())

    def folder_icon(self, path):
        check_icon = self.icons.get("check_on" if path in self.checked_folders else "check_off")
        parts = [check_icon, self.folder_base_icon(path)]
        if path in self.compare_detail_by_path:
            parts.append(self.icons.get("info"))
        return self.compose_row_icon(parts)

    def compose_row_icon(self, parts):
        parts = [part for part in parts if part]
        if not parts:
            return None
        if len(parts) == 1:
            return parts[0]

        cache_key = tuple(str(part) for part in parts)
        if cache_key in self.diff_icon_cache:
            return self.diff_icon_cache[cache_key]

        width = sum(part.width() for part in parts) + TREE_ICON_GAP * (len(parts) - 1)
        height = max(ICON_SIZE[1], max(part.height() for part in parts))
        image = tk.PhotoImage(width=width, height=height)
        x = 0
        for part in parts:
            self.copy_photo_part(image, part, x, max(0, (height - part.height()) // 2))
            x += part.width() + TREE_ICON_GAP
        self.diff_icon_cache[cache_key] = image
        return image

    def folder_base_icon(self, path):
        if path == "/":
            if self.is_effectively_plated_folder(path):
                return self.icons.get("plate_filled")
            return self.icons.get("plate_empty")
        if self.is_effectively_plated_folder(path):
            return self.icons.get("folder_plate_filled") or self.icons.get("plate_filled") or self.icons.get("folder")
        return self.icons.get("folder_plate_empty") or self.icons.get("plate_empty") or self.icons.get("folder")

    def folder_tags(self, path):
        tags = []
        if self.is_effectively_plated_folder(path):
            tags.append("plated")
        compare_tag = self.compare_tag_for_path(path)
        if compare_tag:
            tags.append(compare_tag)
        return tuple(tags)

    def compare_tag_for_path(self, path):
        status = self.compare_status_by_path.get(path)
        if status == "only_first":
            return "compare_only_first"
        if status == "only_second":
            return "compare_only_second"
        if status in {"changed", "path_changed"}:
            return "compare_changed"
        return ""

    def is_effectively_plated_folder(self, path):
        return bool(self.best_plate_root_for_path(path))

    def best_plate_root_for_path(self, path):
        matches = []
        for plated in self.plated_folders:
            prefix = "/" if plated == "/" else plated + "/"
            if path == plated or path.startswith(prefix):
                matches.append(plated)
        return max(matches, key=len) if matches else ""

    def refresh_tree_labels(self):
        for path in self.iter_tree_items():
            if self.is_dummy_iid(path):
                continue
            options = {"text": self.folder_label(path, display_name(path)), "tags": self.folder_tags(path)}
            icon = self.folder_icon(path)
            if icon:
                options["image"] = icon
            self.tree.item(path, **options)

    def iter_tree_items(self, parent=""):
        for item in self.tree.get_children(parent):
            yield item
            yield from self.iter_tree_items(item)

    def on_tree_click(self, event):
        item = self.tree.identify_row(event.y)
        if not item or self.is_dummy_iid(item) or self.tree.identify_column(event.x) != "#0":
            return

        # Only clicks on the item icon act here; the expand indicator and the
        # label keep their default Treeview behavior. The icon is laid out as
        # [checkbox][plate(+folder)][info icon in compare mode].
        element = self.tree.identify_element(event.x, event.y)
        if "image" not in element:
            return

        offset = event.x - self.treeview_icon_left_edge(self.tree, event.x, event.y)
        check_end = ICON_SIZE[0] + TREE_ICON_GAP // 2
        plate_end = check_end + ICON_SIZE[0] + TREE_ICON_GAP
        if offset <= check_end:
            self.toggle_folder_checked(item)
            return "break"
        if offset <= plate_end:
            shift_pressed = bool(event.state & 0x0001)
            self.toggle_plate(item, additive=shift_pressed)
            return "break"

        if item in self.compare_detail_by_path:
            base_icon = self.folder_base_icon(item)
            base_width = base_icon.width() if base_icon else 0
            if offset >= ICON_SIZE[0] + TREE_ICON_GAP + base_width:
                self.tree.selection_set(item)
                self.tree.focus(item)
                self.show_compare_detail(item)
                return "break"

    def treeview_icon_left_edge(self, tree, x, y):
        left = x
        while left > 0 and x - left < 160 and "image" in tree.identify_element(left - 1, y):
            left -= 1
        return left

    def toggle_folder_checked(self, path):
        if path in self.checked_folders:
            self.checked_folders.discard(path)
        else:
            self.checked_folders.add(path)
        if self.tree.exists(path):
            icon = self.folder_icon(path)
            if icon:
                self.tree.item(path, image=icon)
        self.update_detail_row_icon(f"folder:{path}")
        self.report_checked_status()

    def toggle_entry_checked(self, entry, iid=""):
        key = id(entry)
        if key in self.checked_file_entries:
            del self.checked_file_entries[key]
        else:
            self.checked_file_entries[key] = entry
        if iid:
            self.update_detail_row_icon(iid)
        self.report_checked_status()

    def checked_item_count(self):
        return len(self.checked_folders) + len(self.checked_file_entries)

    def report_checked_status(self):
        count = self.checked_item_count()
        if count:
            label = "item" if count == 1 else "items"
            self.status_var.set(f"{count:,} {label} checked.")
        else:
            self.status_var.set("No items checked.")

    def set_selection_checked(self, checked):
        for iid in self.details.selection():
            if iid in self.detail_folder_by_iid:
                path = self.detail_folder_by_iid[iid]
                if checked:
                    self.checked_folders.add(path)
                else:
                    self.checked_folders.discard(path)
                if self.tree.exists(path):
                    icon = self.folder_icon(path)
                    if icon:
                        self.tree.item(path, image=icon)
                self.update_detail_row_icon(iid)
            elif iid in self.detail_entry_by_iid:
                entry = self.detail_entry_by_iid[iid]
                if checked:
                    self.checked_file_entries[id(entry)] = entry
                else:
                    self.checked_file_entries.pop(id(entry), None)
                self.update_detail_row_icon(iid)
        self.report_checked_status()

    def clear_all_checks(self):
        if not self.checked_item_count():
            return
        self.checked_folders.clear()
        self.checked_file_entries.clear()
        self.refresh_tree_labels()
        self.render_detail_page()
        self.status_var.set("Cleared all checkboxes.")

    def update_detail_row_icon(self, iid):
        if not iid or not self.details.exists(iid):
            return
        row_number = self.detail_page_index * DETAIL_PAGE_SIZE + self.details.index(iid) + 1
        if iid in self.detail_folder_by_iid:
            sub = self.detail_folder_by_iid[iid]
            base = self.detail_icon_for_path(sub, self.icons["folder"])
            checked = sub in self.checked_folders
        else:
            entry = self.detail_entry_by_iid.get(iid)
            if not entry:
                return
            ext = os.path.splitext(entry.name)[1].lower()
            base = self.detail_icon_for_path(entry.full_path, self.icons.get(ext, self.icons["default"]))
            checked = id(entry) in self.checked_file_entries
        icon = self.detail_numbered_icon(row_number, base, checked=checked)
        if icon:
            self.details.item(iid, image=icon)

    def toggle_plate(self, path, additive=False):
        if additive:
            if path in self.plated_folders:
                self.plated_folders.remove(path)
            else:
                self.plated_folders.add(path)
        else:
            if self.plated_folders == {path}:
                self.plated_folders.clear()
            else:
                self.plated_folders = {path}

        self.refresh_tree_labels()
        self.refresh_details()

    def on_select(self, event):
        selected = self.tree.focus()
        if not selected or self.is_dummy_iid(selected):
            return
        self.current_folder = selected
        self.schedule_breadcrumb_update(selected)
        self.refresh_details()

    def refresh_details(self):
        self.set_busy("Filtering...")
        self.search_after_id = None
        self.detail_render_token += 1
        self.details.delete(*self.details.get_children())
        self.detail_entry_by_iid = {}
        self.detail_folder_by_iid = {}
        query = self.search_var.get().lower().strip()
        plate_mode = bool(self.plated_folders)
        self.detail_plate_mode = plate_mode
        self.detail_folder_count = len(self.tree_data.get(self.current_folder, set()))

        detail_items = []
        if not plate_mode:
            folders = list(self.tree_data.get(self.current_folder, set()))
            folders.sort(key=self.folder_sort_key, reverse=self.sort_descending if self.sort_column == "name" else False)
            for sub in folders:
                name = display_name(sub)
                if query and query not in name.lower():
                    continue
                if not self.folder_matches_filters(sub):
                    continue
                detail_items.append(("folder", sub))

        all_files = self.files_for_current_view()
        all_files.sort(key=lambda item: self.entry_sort_key(item, plate_mode), reverse=self.sort_descending)
        matched_files = []
        for entry in all_files:
            display = self.entry_display_name(entry, plate_mode)
            searchable = " ".join([display, entry.name, entry.full_path, *entry.metadata.values()]).lower()
            if query and query not in searchable:
                continue
            if not self.entry_matches_filters(entry, display):
                continue
            matched_files.append(entry)

        for entry in matched_files:
            detail_items.append(("file", entry))

        self.detail_items = detail_items
        self.detail_page_index = 0
        self.detail_render_index = 0
        self.detail_loading_iid = ""
        self.detail_total_files = len(all_files)
        self.detail_visible_files = len(matched_files)
        self.detail_visible_folders = sum(1 for kind, _payload in detail_items if kind == "folder")
        self.detail_rendered_files = 0
        self.detail_number_icon_cache.clear()
        self.detail_number_width = self.detail_number_width_for(len(detail_items))
        self.detail_number_icon_offset = ICON_SIZE[0] + DETAIL_NUMBER_GAP + self.detail_number_width + DETAIL_NUMBER_GAP
        self.update_no_results_state(bool(self.entries) and not detail_items and bool(query or self.column_filters))
        self.render_detail_page(self.detail_render_token)
        self.clear_busy()

    def update_no_results_state(self, active):
        if not hasattr(self, "no_results_state"):
            return
        if active:
            self.no_results_state.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.no_results_state.lift()
        else:
            self.no_results_state.place_forget()

    def render_detail_page(self, token=None):
        token = self.detail_render_token if token is None else token
        if token != self.detail_render_token:
            return

        self.detail_loading_iid = ""
        self.details.delete(*self.details.get_children())
        self.detail_entry_by_iid = {}
        self.detail_folder_by_iid = {}
        self.detail_number_icon_cache.clear()
        self.detail_rendered_files = 0

        total_items = len(self.detail_items)
        page_count = max(1, (total_items + DETAIL_PAGE_SIZE - 1) // DETAIL_PAGE_SIZE)
        self.detail_page_index = min(max(0, self.detail_page_index), page_count - 1)
        start = self.detail_page_index * DETAIL_PAGE_SIZE
        end = min(start + DETAIL_PAGE_SIZE, total_items)

        for row_number, (kind, payload) in enumerate(self.detail_items[start:end], start=start + 1):
            if kind == "folder":
                sub = payload
                name = display_name(sub)
                compare_tag = self.compare_tag_for_path(sub)
                tags = (compare_tag,) if compare_tag else ()
                icon = self.detail_numbered_icon(row_number, self.detail_icon_for_path(sub, self.icons["folder"]), checked=sub in self.checked_folders)
                iid = self.tree_insert(
                    self.details,
                    "",
                    "end",
                    iid=f"folder:{sub}",
                    text=name,
                    image=icon,
                    values=("",) * len(self.metadata_columns),
                    tags=tags,
                )
                self.detail_folder_by_iid[iid] = sub
                continue

            entry = payload
            display = self.entry_display_name(entry, self.detail_plate_mode)
            ext = os.path.splitext(entry.name)[1].lower()
            icon = self.detail_numbered_icon(row_number, self.detail_icon_for_path(entry.full_path, self.icons.get(ext, self.icons["default"])), checked=id(entry) in self.checked_file_entries)
            values = tuple(entry.metadata.get(column, "") for column in self.metadata_columns)
            deleted = any(looks_deleted(entry.metadata.get(column)) for column in self.metadata_columns if "deleted" in column.lower() or "geloescht" in column.lower() or "gel\u00f6scht" in column.lower())
            tags = []
            if deleted:
                tags.append("deleted")
            compare_tag = self.compare_tag_for_path(entry.full_path)
            if compare_tag:
                tags.append(compare_tag)
            iid = self.tree_insert(self.details, "", "end", text=display, image=icon, values=values, tags=tuple(tags))
            self.detail_entry_by_iid[iid] = entry
            self.detail_rendered_files += 1

        self.detail_render_index = end

        self.details.tag_configure("deleted", foreground=COLORS["danger"])
        self.details.tag_configure("compare_only_first", foreground="#b45309")
        self.details.tag_configure("compare_only_second", foreground="#047857")
        self.details.tag_configure("compare_changed", foreground="#1d4ed8")
        self.update_detail_summary()

    def update_detail_summary(self):
        total_items = len(self.detail_items)
        page_count = max(1, (total_items + DETAIL_PAGE_SIZE - 1) // DETAIL_PAGE_SIZE)
        start = self.detail_page_index * DETAIL_PAGE_SIZE
        end = min(start + DETAIL_PAGE_SIZE, total_items)
        shown_text = "0" if total_items == 0 else f"{start + 1:,}-{end:,}"
        filter_active = self.detail_filter_active()
        self.set_detail_summary_visible(filter_active or page_count > 1)

        if filter_active:
            file_word = "file" if self.detail_visible_files == 1 else "files"
            folder_word = "folder" if self.detail_visible_folders == 1 else "folders"
            self.detail_summary_var.set(
                f"{total_items:,} hits ({self.detail_visible_files:,} {file_word}, {self.detail_visible_folders:,} {folder_word})"
            )
        else:
            self.detail_summary_var.set("")

        self.detail_page_var.set(f"Showing {shown_text} of {total_items:,} | Page {self.detail_page_index + 1:,}/{page_count:,}" if page_count > 1 else "")
        previous_state = "normal" if self.detail_page_index > 0 else "disabled"
        next_state = "normal" if self.detail_page_index < page_count - 1 else "disabled"
        if hasattr(self, "prev_page_button"):
            self.prev_page_button.configure(state=previous_state)
        if hasattr(self, "next_page_button"):
            self.next_page_button.configure(state=next_state)

        scope = "Current view" if self.detail_plate_mode else f"{display_name(self.current_folder)} (direct)"
        if filter_active:
            self.status_var.set(f"{scope}: {total_items:,} hits, showing {shown_text}.")
        else:
            self.status_var.set(f"{scope}: {total_items:,} items.")

    def detail_filter_active(self):
        return bool(self.search_var.get().strip() or self.normalized_filter_clauses())

    def set_detail_summary_visible(self, visible):
        if not hasattr(self, "summary_bar"):
            return
        if visible:
            if not self.summary_bar.winfo_ismapped():
                self.summary_bar.pack(fill="x", pady=(0, 10), before=self.details_frame)
        elif self.summary_bar.winfo_ismapped():
            self.summary_bar.pack_forget()

    def next_detail_page(self):
        page_count = max(1, (len(self.detail_items) + DETAIL_PAGE_SIZE - 1) // DETAIL_PAGE_SIZE)
        if self.detail_page_index >= page_count - 1:
            return
        self.detail_page_index += 1
        self.render_detail_page()

    def previous_detail_page(self):
        if self.detail_page_index <= 0:
            return
        self.detail_page_index -= 1
        self.render_detail_page()

    def detail_number_width_for(self, count):
        digits = len(str(max(1, count)))
        try:
            return max(DETAIL_NUMBER_MIN_WIDTH, tkfont.nametofont("TkDefaultFont").measure("9" * digits) + 4)
        except tk.TclError:
            return max(DETAIL_NUMBER_MIN_WIDTH, digits * 8 + 4)

    def detail_numbered_icon(self, row_number, base_icon, checked=False):
        check_icon = self.icons.get("check_on" if checked else "check_off")
        cache_key = ("numbered", row_number, bool(checked), self.detail_number_width, str(base_icon))
        if cache_key in self.detail_number_icon_cache:
            return self.detail_number_icon_cache[cache_key]

        number_width = self.detail_number_width
        check_width = check_icon.width() if check_icon else 0
        icon_width = base_icon.width() if base_icon else 0
        icon_height = base_icon.height() if base_icon else 0
        height = max(ICON_SIZE[1], icon_height)
        width = check_width + DETAIL_NUMBER_GAP + number_width + DETAIL_NUMBER_GAP + icon_width
        image = tk.PhotoImage(width=width, height=height)

        if check_icon:
            self.copy_photo_part(image, check_icon, 0, max(0, (height - check_icon.height()) // 2))
        number_image = self.render_detail_number_image(row_number, number_width, height)
        self.copy_photo_part(image, number_image, check_width + DETAIL_NUMBER_GAP, 0)
        if base_icon:
            self.copy_photo_part(image, base_icon, check_width + DETAIL_NUMBER_GAP + number_width + DETAIL_NUMBER_GAP, max(0, (height - icon_height) // 2))

        self.detail_number_icon_cache[cache_key] = image
        return image

    def render_detail_number_image(self, row_number, width, height):
        if not Image or not ImageDraw or not ImageFont or not ImageTk:
            return self.render_detail_number_pixel_image(row_number, width, height)

        number_text = str(row_number)
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), number_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = max(0, width - text_width - 2)
        y = max(0, (height - text_height) // 2 - 1)
        draw.text((x, y), number_text, fill=COLORS["muted"], font=font)
        return ImageTk.PhotoImage(canvas)

    def render_detail_number_pixel_image(self, row_number, width, height):
        number_text = str(row_number)
        image = tk.PhotoImage(width=width, height=height)
        scale = 2
        digit_width = 3 * scale
        digit_gap = scale
        text_width = len(number_text) * digit_width + max(0, len(number_text) - 1) * digit_gap
        x = max(0, width - text_width - 2)
        y = max(0, (height - 5 * scale) // 2)

        for digit in number_text:
            pattern = DETAIL_NUMBER_DIGITS.get(digit)
            if not pattern:
                x += digit_width + digit_gap
                continue
            for row_index, row_pattern in enumerate(pattern):
                for col_index, enabled in enumerate(row_pattern):
                    if enabled != "1":
                        continue
                    for dx in range(scale):
                        for dy in range(scale):
                            image.put(COLORS["muted"], (x + col_index * scale + dx, y + row_index * scale + dy))
            x += digit_width + digit_gap
        return image

    def copy_photo_part(self, target, source, x, y):
        if not source:
            return
        target.tk.call(
            target,
            "copy",
            str(source),
            "-from",
            0,
            0,
            source.width(),
            source.height(),
            "-to",
            x,
            y,
        )

    def detail_icon_for_path(self, path, base_icon):
        if path not in self.compare_detail_by_path:
            return base_icon

        info_icon = self.icons.get("info")
        if not info_icon:
            return base_icon

        cache_key = ("detail", str(base_icon))
        if cache_key in self.diff_icon_cache:
            return self.diff_icon_cache[cache_key]

        width = ICON_SIZE[0] * 2 + TREE_ICON_GAP
        image = tk.PhotoImage(width=width, height=ICON_SIZE[1])

        def copy_part(source, x):
            if not source:
                return
            y = max(0, (ICON_SIZE[1] - source.height()) // 2)
            image.tk.call(
                image,
                "copy",
                str(source),
                "-from",
                0,
                0,
                source.width(),
                source.height(),
                "-to",
                x,
                y,
            )

        copy_part(info_icon, 0)
        copy_part(base_icon, ICON_SIZE[0] + TREE_ICON_GAP)
        self.diff_icon_cache[cache_key] = image
        return image

    def on_details_click(self, event):
        item = self.details.identify_row(event.y)
        if not item or item == self.detail_loading_iid:
            return None
        if self.details.identify_column(event.x) != "#0":
            return None

        # The row icon is laid out as [checkbox][row number][type icon
        # (+info icon in compare mode)]; only icon clicks act here.
        element = self.details.identify_element(event.x, event.y)
        if "image" not in element:
            return None

        offset = event.x - self.treeview_icon_left_edge(self.details, event.x, event.y)
        if offset <= ICON_SIZE[0] + DETAIL_NUMBER_GAP // 2:
            if item in self.detail_folder_by_iid:
                self.toggle_folder_checked(self.detail_folder_by_iid[item])
            else:
                entry = self.detail_entry_by_iid.get(item)
                if entry:
                    self.toggle_entry_checked(entry, iid=item)
            return "break"

        path = self.detail_path_for_iid(item)
        if path and path in self.compare_detail_by_path and offset >= self.detail_number_icon_offset:
            self.details.selection_set(item)
            self.details.focus(item)
            self.show_compare_detail(path)
            return "break"
        return None

    def detail_path_for_iid(self, iid):
        if iid in self.detail_folder_by_iid:
            return self.detail_folder_by_iid[iid]
        entry = self.detail_entry_by_iid.get(iid)
        return entry.full_path if entry else ""

    def show_compare_detail(self, path):
        records = self.compare_records_for_path(path)
        if not records:
            return
        if not self.compare_detail_window or not self.compare_detail_window.winfo_exists():
            self.compare_detail_window = CompareDetailWindow(self)
        self.compare_detail_window.load(path, records)
        self.compare_detail_window.deiconify()
        self.compare_detail_window.lift()
        self.compare_detail_window.focus()

    def compare_records_for_path(self, path):
        if path not in self.compare_detail_by_path:
            return []

        if self.compare_scope_is_folder(path):
            records = []
            seen = set()
            for diff_path, detail in self.compare_detail_by_path.items():
                if not self.compare_detail_in_scope(diff_path, detail, path):
                    continue
                if not self.is_concrete_compare_detail(detail):
                    continue
                key = detail.get("pair_key", diff_path)
                if key in seen:
                    continue
                seen.add(key)
                records.append(self.compare_record_for_path(diff_path))
            return sorted(records, key=lambda record: (record["sort_path"].count("/"), record["sort_path"].lower()))
        else:
            paths = [path]

        if not paths:
            paths = [path]
        paths = sorted(paths, key=lambda value: (value.count("/"), value.lower()))
        return [self.compare_record_for_path(diff_path) for diff_path in paths if diff_path in self.compare_detail_by_path]

    def compare_scope_is_folder(self, path):
        return path == "/" or path in self.tree_data

    def path_is_in_scope(self, path, scope):
        path = normalize_path(path) or "/"
        scope = normalize_path(scope) or "/"
        return scope == "/" or path == scope or path.startswith(scope + "/")

    def compare_detail_in_scope(self, path, detail, scope):
        if detail.get("status") == "path_changed":
            return self.path_is_in_scope(detail.get("loaded_path", path), scope) or self.path_is_in_scope(detail.get("compare_path", path), scope)
        return self.path_is_in_scope(path, scope)

    def is_concrete_compare_detail(self, detail):
        status = detail.get("status", "")
        return status in {"only_first", "only_second", "path_changed"} or bool(detail.get("changes"))

    def compare_record_for_path(self, path):
        detail = self.compare_detail_by_path[path]
        status = detail.get("status", "")
        changes = detail.get("changes") or self.path_change_rows(detail)
        label = self.compare_status_label(status, changes)
        summary = self.compare_record_summary(detail)
        display_path = path
        if status == "path_changed":
            display_path = f"{detail.get('loaded_path', path)} -> {detail.get('compare_path', path)}"
        return {
            "path": display_path,
            "sort_path": detail.get("loaded_path", path),
            "status": status,
            "label": label,
            "summary": summary,
            "detail": self.compare_record_detail(detail, changes),
            "changes": changes,
            "loaded_state": self.loaded_state_for_status(status),
            "compare_state": self.compare_state_for_status(status),
        }

    def compare_status_label(self, status, changes):
        if status == "path_changed":
            return "Possible rename/path change"
        if status == "only_first":
            return "Missing in compare"
        if status == "only_second":
            return "New in compare"
        if status == "changed" and changes:
            return "Metadata changed"
        return "Changed"

    def compare_record_summary(self, detail):
        status = detail.get("status", "")
        changes = detail.get("changes") or []
        if status == "path_changed":
            return "Name or path changed; metadata still matches."
        if status == "changed" and changes:
            columns = ", ".join(column for column, _first, _second in changes)
            return f"Changed metadata: {columns}"
        return detail.get("message", "Compare difference.")

    def compare_record_detail(self, detail, changes):
        status = detail.get("status", "")
        if status == "path_changed":
            return "This is probably the same item with a changed filename or folder path. Check the paths below."
        if status == "changed" and changes:
            return "Metadata values differ between the loaded file and the compare file."
        return detail.get("message", "Compare difference.")

    def path_change_rows(self, detail):
        if detail.get("status") != "path_changed":
            return []
        return [("Path", detail.get("loaded_path", ""), detail.get("compare_path", ""))]

    def loaded_state_for_status(self, status):
        if status == "only_second":
            return "missing"
        return "exists"

    def compare_state_for_status(self, status):
        if status == "only_first":
            return "missing"
        return "exists"

    def schedule_refresh_details(self):
        if self.search_after_id is not None:
            self.after_cancel(self.search_after_id)
        self.search_after_id = self.after(180, self.refresh_details)

    def on_detail_scroll(self, *args):
        self.details.yview(*args)

    def on_detail_yview(self, scrollbar, first, last):
        scrollbar.set(first, last)

    def folder_sort_key(self, folder):
        return display_name(folder).lower()

    def entry_sort_key(self, entry, plate_mode):
        if self.sort_column == "name":
            return (0, self.entry_display_name(entry, plate_mode).lower())

        value = entry.metadata.get(self.sort_column, "")
        if self.profile and self.profile.size_units and self.sort_column in self.profile.size_units:
            number = parse_size_label(value)
            if number is not None:
                return (0, number)

        number = parse_number(value)
        if number is not None and looks_numeric_column(self.sort_column):
            return (0, number)

        return (1, value.lower() if isinstance(value, str) else value)

    def files_for_current_view(self):
        if not self.plated_folders:
            return list(self.folder_entries.get(self.current_folder, []))

        files = []
        seen = set()
        for folder, entries in self.folder_entries.items():
            for plated in self.plated_folders:
                prefix = "/" if plated == "/" else plated + "/"
                if folder == plated or folder.startswith(prefix):
                    for entry in entries:
                        key = id(entry)
                        if key not in seen:
                            files.append(entry)
                            seen.add(key)
                    break
        return files

    def entry_display_name(self, entry, plate_mode):
        if not plate_mode:
            return entry.name

        root = self.best_plate_root_for_entry(entry)
        if not root or entry.folder == root:
            return entry.name

        base = "" if root == "/" else root.strip("/") + "/"
        relative_folder = entry.folder.strip("/")
        if base and relative_folder.startswith(base):
            relative_folder = relative_folder[len(base):]
        return f"{relative_folder}/{entry.name}" if relative_folder else entry.name

    def best_plate_root_for_entry(self, entry):
        return self.best_plate_root_for_path(entry.folder)

    def set_sort(self, column):
        if self.sort_column == column:
            self.sort_descending = not self.sort_descending
        else:
            self.sort_column = column
            self.sort_descending = False
        self.update_sort_headings()
        self.refresh_details()

    def update_sort_headings(self):
        filtered = self.filtered_columns()
        name_filter = " *" if FILTER_NAME_COLUMN in filtered else ""
        name_title = "Name" + name_filter
        sort_icon = self.icons.get("sort_desc" if self.sort_descending else "sort_asc")
        self.details.heading("#0", text=name_title, image=sort_icon if self.sort_column == "name" else "", command=lambda: self.set_sort("name"))
        for column in self.metadata_columns:
            filter_marker = " *" if column in filtered else ""
            title = column + filter_marker
            self.details.heading(column, text=title, image=sort_icon if self.sort_column == column else "", command=lambda c=column: self.set_sort(c))

    def entry_properties(self, entry):
        properties = {
            "Filename": entry.name,
            "Full Path": entry.full_path,
            "Folder": entry.folder,
            "Item type": "Folder" if entry.is_folder else "File",
        }
        for column, value in (entry.properties or {}).items():
            properties.setdefault(column, value)
        for column, value in entry.metadata.items():
            properties.setdefault(column, value)
        return properties

    def show_context_item_properties(self):
        if self.context_entry:
            self.show_entry_properties(self.context_entry)

    def show_entry_properties(self, entry):
        properties = self.entry_properties(entry)
        title = entry.name or "Item properties"

        toolbar_bg = "#f6f8fb"
        card_bg = "#ffffff"
        border = "#d9e1ec"
        text = "#1f2937"
        muted = "#64748b"
        accent = "#2563eb"
        accent_hover = "#1d4ed8"
        secondary_hover = "#eef2f7"
        group_bg = "#f8fafc"

        win = tk.Toplevel(self)
        win.title(f"Properties - {title}")
        win.geometry("1180x780")
        win.minsize(900, 560)
        win.transient(self)
        win.configure(bg=toolbar_bg)
        set_window_icon(win)

        def flat_button(parent, label, command, primary=False):
            bg_color = accent if primary else card_bg
            fg_color = "#ffffff" if primary else text
            hover_color = accent_hover if primary else secondary_hover
            btn = tk.Button(
                parent,
                text=label,
                command=command,
                relief="flat",
                bd=0,
                padx=12,
                pady=6,
                cursor="hand2",
                bg=bg_color,
                fg=fg_color,
                activebackground=hover_color,
                activeforeground=fg_color,
                highlightthickness=1,
                highlightbackground=accent if primary else border,
                highlightcolor=accent if primary else border,
                font=("Segoe UI", 9),
            )
            btn.bind("<Enter>", lambda _e: btn.configure(bg=hover_color))
            btn.bind("<Leave>", lambda _e: btn.configure(bg=bg_color))
            return btn

        def wrap_text(value, width=95):
            value = clean_cell(value)
            if not value:
                return ""
            import textwrap
            lines = []
            for part in value.splitlines() or [value]:
                if len(part) <= width:
                    lines.append(part)
                else:
                    lines.extend(textwrap.wrap(part, width=width, break_long_words=False, break_on_hyphens=False) or [part])
            return "\n".join(lines)

        show_empty = tk.BooleanVar(master=win, value=False)
        prop_search = tk.StringVar(master=win, value="")

        property_groups = [
            ("Summary", [
                "Filename", "File name", "Name", "Subject/Title", "Title", "Item type", "Item class", "Message kind",
                "Type", "Workload", "Size", "Date", "Created", "Created by", "Last modified time", "Last modified by",
                "Status", "Category", "Tags",
            ]),
            ("Mail - headers & recipients", [
                "From", "Sender", "To", "To expanded", "CC", "CC expanded", "BCC", "BCC expanded",
                "Email recipients", "Recipient count", "Email recipient domains", "Email sender domain",
                "Email participant domains", "Email action", "Email date sent", "Received",
            ]),
            ("Mail - conversation / message IDs", [
                "Internet message ID", "Client conversation ID", "In reply to ID", "Conversation index",
                "Conversation name", "Conversation topic", "Conversation type", "Email thread", "Email level", "Email set",
                "Email importance", "Email sensitivity", "Email security", "Email delivery receipt", "Email read receipt",
                "Email internet headers", "Is draft", "Is read", "Is external", "Is bcc to me",
            ]),
            ("Calendar / meetings", [
                "Meeting name", "Organizer", "Participants", "Participant expansion", "Meeting start date", "Meeting end date",
                "Teams channel", "Team name", "Teams annoucement title", "Thread participants", "Thread participant domains",
            ]),
            ("Attachments & family", [
                "Has attachment", "Has unique attachment", "Attachment names", "Is attachment from transcript",
                "Is modern attachment", "Modern attachment embedded URLs", "Modern attachment parent ID",
                "Family ID", "Family size", "Family duplicate set", "Parent ID", "Parent node", "Group ID",
            ]),
            ("Paths & locations", [
                "Full Path", "Folder", "Compound path", "Target path", "Original path", "Deduped compound path",
                "Location ID", "Location sub type", "Item source", "Data source", "Source ID",
                "Content source application", "SPO document link", "Preservation original URL", "Retention URL",
                "Native copy from", "Extracted text path", "Redacted file path", "Redacted text path",
            ]),
            ("File / document metadata", [
                "File ID", "Identifier", "Immutable ID", "Input file ID", "File class", "File extension",
                "Original file extension", "Native type", "Native MD5", "Native SHA 256", "Version number",
                "Version group ID", "Doc authors", "Author", "Doc comments", "Doc company", "Doc date created",
                "Doc index", "Doc keywords", "Doc subject", "Doc template", "Document ID index", "Document ID path",
                "Word count", "Extracted text length", "Extracted content type", "Has text",
            ]),
            ("Review / dedup / representatives", [
                "Custodian", "All custodians", "Deduped custodians", "Deduped file IDs", "Deduped group file IDs",
                "Deduped thread file IDs", "Inclusive type", "Is inclusive", "Is representative", "Is group representative",
                "Is thread representative", "Is top for group", "Group representative ID", "Representative ID",
                "Thread representative ID", "Marked as pivot", "Pivot ID", "Set ID", "Set order inclusives first",
                "ND set", "ND ET sort excl attach", "ND ET sort incl attach", "Similarity percent",
                "Potentially privileged", "Was remediated",
            ]),
            ("Processing / errors", [
                "Error warning", "Error code", "Error ignored", "Processing error type", "DG expansion result",
                "Load ID", "Contains deleted message", "Contains edited message", "Is encrypted", "Is partially indexed",
            ]),
            ("Security / labels / sensitivity", [
                "Sensitive type", "Sensitivity label", "Retention label", "Email sensitivity", "Email security",
                "Detected language", "Dominant theme", "Themes list",
            ]),
            ("SharePoint identifiers", [
                "SPO unique ID", "SPO preservation original document unique ID", "Document ID path", "Document ID index",
            ]),
        ]

        header = tk.Frame(win, bg=toolbar_bg, padx=12, pady=10)
        header.pack(fill="x")
        left_header = tk.Frame(header, bg=toolbar_bg)
        left_header.pack(side="left", fill="x", expand=True)
        tk.Label(left_header, text=title, bg=toolbar_bg, fg=text, font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(left_header, text=entry.full_path, bg=toolbar_bg, fg=muted, font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 0))

        search_wrap = tk.Frame(header, bg=card_bg, highlightthickness=1, highlightbackground=border)
        search_wrap.pack(side="right", fill="x", padx=(12, 0))
        tk.Label(search_wrap, text="Search", bg=card_bg, fg=muted, font=("Segoe UI", 9)).pack(side="left", padx=(10, 4))
        search_entry = tk.Entry(
            search_wrap,
            textvariable=prop_search,
            relief="flat",
            bd=0,
            bg=card_bg,
            fg=text,
            insertbackground=text,
            width=32,
            font=("Segoe UI", 10),
        )
        search_entry.pack(side="left", ipady=7, padx=(0, 10))

        option_row = tk.Frame(win, bg=toolbar_bg)
        option_row.pack(fill="x", padx=12, pady=(0, 8))
        tk.Checkbutton(
            option_row,
            text="Show empty fields",
            variable=show_empty,
            command=lambda: populate_props(),
            bg=toolbar_bg,
            fg=text,
            activebackground=toolbar_bg,
            selectcolor=card_bg,
            font=("Segoe UI", 9),
        ).pack(side="left")

        flat_button(option_row, "Copy selected value", lambda: copy_selected_value()).pack(side="right", padx=(6, 0))
        flat_button(option_row, "Copy field + value", lambda: copy_selected_pair()).pack(side="right", padx=(6, 0))
        flat_button(option_row, "Copy all visible", lambda: copy_all_visible(), primary=True).pack(side="right", padx=(6, 0))

        outer = tk.Frame(win, bg=toolbar_bg)
        outer.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        canvas = tk.Canvas(outer, bg=toolbar_bg, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        content = tk.Frame(canvas, bg=toolbar_bg)
        canvas_window = canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def on_content_configure(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def on_canvas_configure(event):
            canvas.itemconfigure(canvas_window, width=event.width)

        content.bind("<Configure>", on_content_configure)
        canvas.bind("<Configure>", on_canvas_configure)

        def on_mousewheel(event):
            try:
                if win.winfo_exists():
                    units = int(-1 * (event.delta / 120)) if getattr(event, "delta", 0) else 0
                    if units:
                        canvas.yview_scroll(units, "units")
            except Exception:
                pass
            return "break"

        for widget in (win, outer, canvas, content):
            widget.bind("<MouseWheel>", on_mousewheel, add="+")

        selected = {"field": "", "value": "", "widget": None}
        visible_pairs = []

        def field_matches(field, value, query):
            if not query:
                return True
            q = query.lower()
            return q in field.lower() or q in clean_cell(value).lower()

        def select_row(row_frame, field, value):
            if selected["widget"] is not None and selected["widget"].winfo_exists():
                selected["widget"].configure(bg=card_bg, highlightbackground=border)
                for child in selected["widget"].winfo_children():
                    try:
                        child.configure(bg=card_bg)
                    except Exception:
                        pass
            selected.update({"field": field, "value": value, "widget": row_frame})
            row_frame.configure(bg="#eff6ff", highlightbackground=accent)
            for child in row_frame.winfo_children():
                try:
                    child.configure(bg="#eff6ff")
                except Exception:
                    pass

        def add_value_row(parent, field, value, is_last=False):
            display_value = wrap_text(value, width=110)
            row_frame = tk.Frame(parent, bg=card_bg, highlightthickness=0)
            row_frame.pack(fill="x")
            row_frame.columnconfigure(1, weight=1)

            field_label = tk.Label(
                row_frame,
                text=field,
                bg=card_bg,
                fg=text,
                anchor="nw",
                justify="left",
                width=30,
                font=("Segoe UI", 9, "bold"),
                padx=12,
                pady=4,
            )
            field_label.grid(row=0, column=0, sticky="nsw")

            value_label = tk.Label(
                row_frame,
                text=display_value,
                bg=card_bg,
                fg=text if display_value else muted,
                anchor="nw",
                justify="left",
                wraplength=820,
                font=("Segoe UI", 9),
                padx=8,
                pady=4,
            )
            value_label.grid(row=0, column=1, sticky="nsew")
            for widget in (row_frame, field_label, value_label):
                widget.bind("<MouseWheel>", on_mousewheel, add="+")
                widget.bind("<Button-1>", lambda _e, rf=row_frame, f=field, v=display_value: select_row(rf, f, v))

            if not is_last:
                divider = tk.Frame(parent, bg="#edf1f6", height=1)
                divider.pack(fill="x", padx=12)

        def add_group(parent, group_name, items):
            if not items:
                return
            card = tk.Frame(parent, bg=card_bg, highlightthickness=1, highlightbackground=border)
            card.pack(fill="x", pady=(0, 10))
            header_row = tk.Frame(card, bg=group_bg)
            header_row.pack(fill="x")
            tk.Label(
                header_row,
                text=group_name,
                bg=group_bg,
                fg=text,
                anchor="w",
                font=("Segoe UI", 10, "bold"),
                padx=12,
                pady=7,
            ).pack(side="left", fill="x", expand=True)
            tk.Label(
                header_row,
                text=f"{len(items)} fields",
                bg=group_bg,
                fg=muted,
                anchor="e",
                font=("Segoe UI", 9),
                padx=12,
                pady=7,
            ).pack(side="right")
            body = tk.Frame(card, bg=card_bg)
            body.pack(fill="x", padx=0, pady=(2, 2))
            for index, (field, value) in enumerate(items):
                add_value_row(body, field, value, is_last=(index == len(items) - 1))

        def populate_props(*_):
            nonlocal visible_pairs
            selected.update({"field": "", "value": "", "widget": None})
            visible_pairs = []
            for child in content.winfo_children():
                child.destroy()
            query = clean_cell(prop_search.get())
            consumed = set()

            for group_name, fields in property_groups:
                items = []
                for field in fields:
                    if field not in properties or field in consumed:
                        continue
                    consumed.add(field)
                    value = properties.get(field, "")
                    if not show_empty.get() and not clean_cell(value):
                        continue
                    if field_matches(field, value, query):
                        items.append((field, value))
                if items:
                    visible_pairs.extend(items)
                    add_group(content, group_name, items)

            other_items = []
            for field, value in properties.items():
                if field in consumed:
                    continue
                if not show_empty.get() and not clean_cell(value):
                    continue
                if field_matches(field, value, query):
                    other_items.append((field, value))
            if other_items:
                visible_pairs.extend(other_items)
                add_group(content, "Other columns", other_items)

            if not visible_pairs:
                tk.Label(
                    content,
                    text="No properties match the current search/filter.",
                    bg=toolbar_bg,
                    fg=muted,
                    font=("Segoe UI", 10),
                    pady=30,
                ).pack(fill="x")

            canvas.yview_moveto(0)

        def copy_to_clipboard(text_value, status):
            if text_value is None:
                return
            win.clipboard_clear()
            win.clipboard_append(str(text_value))
            self.status_var.set(status)

        def copy_selected_value():
            copy_to_clipboard(selected.get("value", ""), "Copied selected property value.")

        def copy_selected_pair():
            field = selected.get("field", "")
            value = selected.get("value", "")
            if field:
                copy_to_clipboard(f"{field}: {value}", "Copied selected property.")

        def copy_all_visible():
            if visible_pairs:
                copy_to_clipboard("\n".join(f"{field}: {clean_cell(value)}" for field, value in visible_pairs), "Copied visible properties.")

        footer = tk.Frame(win, bg=toolbar_bg)
        footer.pack(fill="x", padx=12, pady=(0, 12))
        tk.Label(footer, text="Click a property row, then use the copy buttons.", bg=toolbar_bg, fg=muted, font=("Segoe UI", 9)).pack(side="left")
        flat_button(footer, "Close", win.destroy).pack(side="right")

        prop_search.trace_add("write", populate_props)
        populate_props()
        search_entry.focus_set()

    def open_details_item(self, event):
        if "image" in self.details.identify_element(event.x, event.y):
            # A double-click on the icon area (checkbox/info) acts like a
            # second single click instead of opening the item.
            return self.on_details_click(event)
        item = self.details.identify_row(event.y) or self.details.focus()
        if item.startswith("folder:"):
            path = item.removeprefix("folder:")
            self.select_path(path)
            return

        entry = self.detail_entry_by_iid.get(item)
        if entry:
            self.show_entry_properties(entry)

    def show_tree_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if not item or self.is_dummy_iid(item):
            return
        self.tree.selection_set(item)
        self.tree.focus(item)
        self.context_folder_path = item
        self.context_entry = None
        self.folder_context_menu.tk_popup(event.x_root, event.y_root)

    def show_details_context_menu(self, event):
        item = self.details.identify_row(event.y)
        if not item or item == self.detail_loading_iid:
            if self.detail_items:
                self.context_folder_path = ""
                self.context_entry = None
                self.details_context_menu.tk_popup(event.x_root, event.y_root)
            return

        selection = self.details.selection()
        if item in selection and len(selection) > 1:
            self.details.focus(item)
            self.context_folder_path = ""
            self.context_entry = None
            self.selection_context_menu.tk_popup(event.x_root, event.y_root)
            return

        if item.startswith("folder:"):
            self.details.selection_set(item)
            self.details.focus(item)
            self.context_folder_path = item.removeprefix("folder:")
            self.context_entry = None
            self.detail_folder_context_menu.tk_popup(event.x_root, event.y_root)
            return

        entry = self.detail_entry_by_iid.get(item)
        if not entry:
            return
        self.details.selection_set(item)
        self.details.focus(item)
        self.context_entry = entry
        self.context_folder_path = ""
        self.item_context_menu.tk_popup(event.x_root, event.y_root)

    def open_context_folder_tree_dialog(self):
        if not self.context_folder_path:
            return
        root = self.context_folder_path
        self.open_tree_export_dialog(
            root,
            self.tree_data,
            self.folder_entries,
            self.tree_export_root_label(root),
            display_name(root),
            checked_items=self.checked_items_under_root(root),
        )

    def open_selection_tree_dialog(self):
        items = self.selected_export_items()
        entries = [payload for kind, payload in items if kind == "file"]
        folder_roots = [payload for kind, payload in items if kind == "folder"]
        if not entries and not folder_roots:
            messagebox.showinfo("Nothing selected", "Select one or more rows first.")
            return

        tree_data, folder_entries = self.structure_for_selection(entries, folder_roots)
        root_label = f"{self.tree_export_root_label('/')} (selection)"
        self.open_tree_export_dialog("/", tree_data, folder_entries, root_label, "the selection", selection=True)

    def tree_export_root_label(self, root):
        if root == "/" and self.current_file:
            return os.path.splitext(os.path.basename(self.current_file))[0]
        return display_name(root)

    def open_tree_export_dialog(self, root, tree_data, folder_entries, root_label, scope_label, selection=False, checked_items=None):
        checked_entries, checked_roots = checked_items or ([], [])
        checked_count = len(checked_entries) + len(checked_roots)
        dialog = TreeExportDialog(self, scope_label, has_sizes=self.has_folder_sizes(), selection=selection, checked_count=checked_count)
        self.wait_window(dialog)
        options = dialog.result
        if not options:
            return

        if options.get("checked_only"):
            tree_data, folder_entries = self.structure_for_selection(checked_entries, checked_roots)
            scope_label = f"checked items in {scope_label}"

        stats = compute_tree_stats(root, tree_data, folder_entries, self.entry_size_bytes)
        render_options = {
            "include_files": options["include_files"],
            "max_depth": options["max_depth"],
            "annotate": options["annotate"],
            "show_sizes": self.has_folder_sizes(),
            "entry_size": self.entry_size_bytes,
            "stats": stats,
        }

        action = options["action"]
        if action == "clipboard":
            text = generate_tree_text(root, root_label, tree_data, folder_entries, **render_options)
            self.copy_text(text, f"Copied tree for {scope_label} to the clipboard.")
            return

        if action == "html":
            extension, filetypes = ".html", [("HTML", "*.html"), ("All files", "*.*")]
        else:
            extension, filetypes = ".txt", [("Text", "*.txt"), ("All files", "*.*")]
        export_path = filedialog.asksaveasfilename(
            defaultextension=extension,
            initialfile=f"{self.safe_export_name(root_label)}_tree{extension}",
            filetypes=filetypes,
        )
        if not export_path:
            return

        if action == "html":
            content = generate_tree_html(
                root,
                root_label,
                tree_data,
                folder_entries,
                source_name=os.path.basename(self.current_file or ""),
                **render_options,
            )
        else:
            content = generate_tree_text(root, root_label, tree_data, folder_entries, **render_options)

        try:
            with open(export_path, "w", encoding="utf-8") as handle:
                handle.write(content)
        except OSError as exc:
            messagebox.showerror("Export failed", str(exc))
            return
        self.status_var.set(f"Exported tree for {scope_label} to {export_path}.")

    def safe_export_name(self, label):
        cleaned = "".join(char if char.isalnum() or char in "._- " else "_" for char in label).strip().replace(" ", "_")
        return cleaned or "tree"

    def selected_export_items(self):
        items = []
        for iid in self.details.selection():
            if iid in self.detail_folder_by_iid:
                items.append(("folder", self.detail_folder_by_iid[iid]))
            elif iid in self.detail_entry_by_iid:
                items.append(("file", self.detail_entry_by_iid[iid]))
        return items

    def structure_for_selection(self, entries, folder_roots):
        tree_data = {"/": set()}
        folder_entries = {}
        seen_files = set()

        def ensure_local_folder(folder):
            folder = normalize_path(folder) or "/"
            if folder == "/":
                return
            parts = folder.strip("/").split("/")
            current = ""
            for part in parts:
                current += "/" + part
                parent = parent_path(current)
                tree_data.setdefault(parent, set()).add(current)
                tree_data.setdefault(current, set())

        def add_file(entry):
            if id(entry) in seen_files:
                return
            seen_files.add(id(entry))
            ensure_local_folder(entry.folder)
            folder_entries.setdefault(entry.folder, []).append(entry)

        def add_subtree(folder):
            ensure_local_folder(folder)
            for entry in self.folder_entries.get(folder, []):
                add_file(entry)
            for child in self.tree_data.get(folder, set()):
                add_subtree(child)

        for folder in folder_roots:
            add_subtree(folder)
        for entry in entries:
            add_file(entry)
        return tree_data, folder_entries

    def copy_selected_full_paths(self):
        items = self.selected_export_items()
        if not items:
            return
        lines = [payload + "/" if kind == "folder" else payload.full_path for kind, payload in items]
        label = "path" if len(lines) == 1 else "paths"
        self.copy_text("\n".join(lines), f"Copied {len(lines):,} {label} to the clipboard.")

    def checked_items_under_root(self, root):
        root = normalize_path(root) or "/"
        for folder in self.checked_folders:
            if folder != root and self.path_is_under_root(root, folder):
                return [], [root]

        folder_roots = sorted((folder for folder in self.checked_folders if self.path_is_under_root(folder, root)), key=str.lower)
        entries = sorted(
            (entry for entry in self.checked_file_entries.values() if self.path_is_under_root(entry.full_path, root)),
            key=lambda entry: entry.full_path.lower(),
        )
        return entries, folder_roots

    def checked_export_items(self):
        items = [("folder", path) for path in sorted(self.checked_folders, key=str.lower)]
        entries = sorted(self.checked_file_entries.values(), key=lambda entry: entry.full_path.lower())
        items.extend(("file", entry) for entry in entries)
        return items

    def export_checked_csv(self):
        self.export_items_csv(self.checked_export_items(), "checked", "Check one or more items first.")

    def copy_context_folder_children(self, recursive):
        if not self.context_folder_path:
            return

        text = self.generate_folder_items_text(self.context_folder_path, recursive)
        scope = "all child items" if recursive else "direct child items"
        self.copy_text(text, f"Copied {scope} for {display_name(self.context_folder_path)} to the clipboard.")

    def copy_context_item_information(self):
        if not self.context_entry:
            return

        entry = self.context_entry
        lines = [f"{field}: {clean_cell(value)}" for field, value in self.entry_properties(entry).items()]
        self.copy_text("\n".join(lines), f"Copied information for {entry.name}.")

    def copy_context_item_filename(self):
        if self.context_entry:
            self.copy_text(self.context_entry.name, f"Copied filename for {self.context_entry.name}.")

    def copy_context_item_full_path(self):
        if self.context_entry:
            self.copy_text(self.context_entry.full_path, f"Copied full path for {self.context_entry.name}.")

    def export_current_view_csv(self):
        self.export_items_csv(self.detail_items, "filtered_view", "The current view has no rows to export.")

    def export_selected_csv(self):
        self.export_items_csv(self.selected_export_items(), "selection", "Select one or more rows first.")

    def export_items_csv(self, items, suffix, empty_message):
        if not items:
            messagebox.showinfo("Nothing to export", empty_message)
            return

        base_name = os.path.splitext(os.path.basename(self.current_file or "file_view"))[0] or "file_view"
        export_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=f"{base_name}_{suffix}.csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
        )
        if not export_path:
            return

        columns = ["Row", "Type", "Name", "Full Path", *self.metadata_columns]
        try:
            with open(export_path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle)
                writer.writerow(columns)
                for row_number, (kind, payload) in enumerate(items, start=1):
                    if kind == "folder":
                        path = payload
                        writer.writerow([row_number, "folder", display_name(path), path, *([""] * len(self.metadata_columns))])
                    else:
                        entry = payload
                        writer.writerow([
                            row_number,
                            "file",
                            entry.name,
                            entry.full_path,
                            *(entry.metadata.get(column, "") for column in self.metadata_columns),
                        ])
        except OSError as exc:
            messagebox.showerror("Export failed", str(exc))
            return

        self.status_var.set(f"Exported {len(items):,} rows to {export_path}.")

    def copy_text(self, text, status):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_var.set(status)

    def generate_folder_items_text(self, root, recursive):
        lines = []

        def append_items(folder):
            folders = sorted(self.tree_data.get(folder, set()), key=lambda path: display_name(path).lower())
            files = sorted(self.folder_entries.get(folder, []), key=lambda entry: entry.name.lower())

            for child in folders:
                lines.append(child + "/")
                if recursive:
                    append_items(child)
            for entry in files:
                lines.append(entry.full_path)

        append_items(root)
        return "\n".join(lines)

    def schedule_breadcrumb_update(self, path=None):
        if path is not None:
            self.breadcrumb_pending_path = path
        if self.breadcrumb_after_id is not None:
            self.after_cancel(self.breadcrumb_after_id)
        self.breadcrumb_after_id = self.after_idle(self.run_breadcrumb_update)

    def run_breadcrumb_update(self):
        self.breadcrumb_after_id = None
        self.update_breadcrumb(self.breadcrumb_pending_path or self.current_folder)

    def update_breadcrumb(self, path):
        if not self.breadcrumb.winfo_exists():
            return

        for widget in list(self.breadcrumb.winfo_children()):
            if widget.winfo_exists():
                widget.destroy()

        crumbs = [("Root", "/")]
        current = ""
        if path != "/":
            for part in path.strip("/").split("/"):
                current += "/" + part
                crumbs.append((part, current))

        max_width = max(self.breadcrumb.winfo_width() - 8, 260)
        x = 0
        y = 0
        row_height = 20
        max_rows = 2
        crumb_bg = self.breadcrumb.cget("bg")

        for index, (label, crumb_path) in enumerate(crumbs):
            label_text = shorten_label(label)
            width = self.breadcrumb_font.measure(label_text) + 8
            link = tk.Label(
                self.breadcrumb,
                text=label_text,
                bd=0,
                padx=1,
                pady=0,
                bg=crumb_bg,
                fg=COLORS["accent"],
                font=self.breadcrumb_font,
                cursor="hand2",
            )
            link.bind("<Button-1>", lambda event, p=crumb_path: self.select_path(p))
            if index > 0:
                sep_text = ">"
                sep_width = self.breadcrumb_font.measure(sep_text) + 5
                sep = tk.Label(
                    self.breadcrumb,
                    text=sep_text,
                    bg=crumb_bg,
                    fg=COLORS["muted"],
                    font=self.breadcrumb_font,
                )
            else:
                sep = None
                sep_width = 0

            if x and x + sep_width + width > max_width and y < row_height * (max_rows - 1):
                x = 0
                y += row_height

            if y >= row_height * max_rows and index < len(crumbs) - 1:
                link.destroy()
                if sep:
                    sep.destroy()
                continue

            if sep:
                sep.place(x=x, y=y, height=16)
                x += sep_width + 3
            link.place(x=x, y=y, height=16)
            x += width + 5

        self.breadcrumb.configure(height=row_height * max_rows)

    def select_path(self, path):
        self.ensure_tree_path_visible(path)
        if self.tree.exists(path):
            self.tree.selection_set(path)
            self.tree.focus(path)
            self.tree.see(path)
            self.current_folder = path
            self.schedule_breadcrumb_update(path)
            self.refresh_details()

    def ensure_tree_path_visible(self, path):
        if path == "/":
            return

        current = "/"
        self.populate_tree_node(current)
        for part in path.strip("/").split("/"):
            current = normalize_path(f"{current}/{part}")
            parent = parent_path(current)
            self.populate_tree_node(parent)
            if self.tree.exists(parent):
                self.tree.item(parent, open=True)




def main():
    app = FileBrowser()
    app.mainloop()


if __name__ == "__main__":
    main()
