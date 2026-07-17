import tkinter as tk
from tkinter import messagebox, ttk

from .icons import set_window_icon
from .models import (
    COLORS,
    FILTER_ANY,
    FILTER_NAME_COLUMN,
    FILTER_OPERATORS,
    FILTER_PATH_COLUMN,
    FILTER_PRESET_IMAGES,
    FILTER_PRESET_NONE,
    FILTER_PRESET_OFFICE,
    FILTER_PRESET_USER_DATA,
    FILTER_PRESET_VIDEOS,
    FILTER_VISIBLE_CHIPS,
    NO_COLUMN,
    NUMERIC_FILTERS,
    PATH_STYLE_AUTO,
    PATH_STYLE_CHOICES,
    VALUELESS_FILTERS,
    FilterClause,
    ImportProfile,
)
from .parsing import best_column
from .utils import clean_cell, detect_size_unit, normalize_path, parse_number, parse_size_label, split_filter_values


class Tooltip:
    """Small hover tooltip for a single widget."""

    def __init__(self, widget, text, delay=500):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.after_id = None
        self.window = None
        widget.bind("<Enter>", self.schedule, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")
        widget.bind("<Destroy>", self.hide, add="+")

    def schedule(self, _event=None):
        self.cancel()
        self.after_id = self.widget.after(self.delay, self.show)

    def cancel(self):
        if self.after_id is not None:
            self.widget.after_cancel(self.after_id)
            self.after_id = None

    def show(self):
        self.after_id = None
        if self.window is not None or not self.widget.winfo_exists():
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        self.window.wm_geometry(f"+{x}+{y}")
        tk.Label(
            self.window,
            text=self.text,
            bg="#1f2937",
            fg="#f8fafc",
            padx=9,
            pady=5,
            justify="left",
            font=("TkDefaultFont", 9),
        ).pack()

    def hide(self, _event=None):
        self.cancel()
        if self.window is not None:
            if self.window.winfo_exists():
                self.window.destroy()
            self.window = None


class ImportDialog(tk.Toplevel):
    def __init__(self, parent, headers, profile=None, selected_metadata=None, action_label="Import"):
        super().__init__(parent)
        self.title("Manage CSV Columns")
        set_window_icon(self)
        self.geometry("820x620")
        self.minsize(720, 520)
        self.resizable(True, True)
        self.result = None
        self.headers = list(headers)
        self.profile = profile or ImportProfile()
        self.action_label = action_label
        self.column_choices = [NO_COLUMN] + self.headers

        self.full_path_var = tk.StringVar(value=self.profile.full_path_column or best_column(headers, ("Full Path", "Path", "Pfad", "Dateipfad")))
        self.folder_var = tk.StringVar(value=self.profile.folder_column or best_column(headers, ("Folder", "Directory", "Parent Path", "Ordner")))
        self.filename_var = tk.StringVar(value=self.profile.filename_column or best_column(headers, ("Filename", "File Name", "Name", "Dateiname")))
        self.path_style_values = {label: value for label, value in PATH_STYLE_CHOICES}
        self.path_style_labels = {value: label for label, value in PATH_STYLE_CHOICES}
        self.path_style_var = tk.StringVar(value=self.path_style_labels.get(self.profile.path_style or PATH_STYLE_AUTO, "Auto detect"))
        self.current_columns = self.initial_metadata_columns(selected_metadata)
        self.all_column_headers = []

        self._build()
        self.refresh_column_lists()
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.wait_visibility()
        self.focus()

    def initial_metadata_columns(self, selected_metadata):
        if selected_metadata is not None:
            return self.sanitize_columns(selected_metadata)
        if self.profile.metadata_columns:
            return self.sanitize_columns(self.profile.metadata_columns)
        return self.default_metadata_columns()

    def sanitize_columns(self, columns):
        result = []
        seen = set()
        for column in columns or []:
            if column in self.headers and column not in seen:
                result.append(column)
                seen.add(column)
        return result

    def default_metadata_columns(self):
        path_columns = {self.full_path_var.get(), self.folder_var.get(), self.filename_var.get(), NO_COLUMN, ""}
        preferred = {"size", "created", "modified", "accessed", "is deleted", "deleted", "extension", "hash", "md5", "sha1"}
        result = []

        for header in self.headers:
            lowered = header.lower()
            if header not in path_columns and (len(result) < 8 or any(p in lowered for p in preferred)):
                result.append(header)
        return result

    def _build(self):
        self.configure(bg=COLORS["app_bg"])
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        outer = ttk.Frame(self, padding=18, style="Panel.TFrame")
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(5, weight=1)

        ttk.Label(
            outer,
            text="Choose path columns and manage which metadata columns are visible in the browser.",
            wraplength=720,
            style="PanelMuted.TLabel",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        self._combo_row(outer, 1, "Full path column", self.full_path_var)
        self._combo_row(outer, 2, "Folder/path column", self.folder_var)
        self._combo_row(outer, 3, "Filename column", self.filename_var)
        self._path_style_row(outer, 4)

        ttk.Label(outer, text="Columns").grid(row=5, column=0, sticky="nw", pady=(14, 0))

        columns_frame = ttk.Frame(outer, style="Panel.TFrame")
        columns_frame.grid(row=5, column=1, rowspan=2, sticky="nsew", pady=(14, 0))
        columns_frame.columnconfigure(0, weight=1)
        columns_frame.columnconfigure(2, weight=1)
        columns_frame.rowconfigure(1, weight=1)

        ttk.Label(columns_frame, text="All columns", style="PanelMuted.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        ttk.Label(columns_frame, text="Current columns", style="PanelMuted.TLabel").grid(row=0, column=2, sticky="w", pady=(0, 6))

        all_frame = ttk.Frame(columns_frame)
        all_frame.grid(row=1, column=0, sticky="nsew")
        all_frame.columnconfigure(0, weight=1)
        all_frame.rowconfigure(0, weight=1)
        self.all_columns_list = self._column_listbox(all_frame)
        all_scroll = ttk.Scrollbar(all_frame, orient="vertical", command=self.all_columns_list.yview)
        self.all_columns_list.configure(yscrollcommand=all_scroll.set)
        self.all_columns_list.grid(row=0, column=0, sticky="nsew")
        all_scroll.grid(row=0, column=1, sticky="ns")

        transfer_buttons = ttk.Frame(columns_frame, style="Panel.TFrame")
        transfer_buttons.grid(row=1, column=1, sticky="ns", padx=10)
        ttk.Button(transfer_buttons, text=">", width=4, command=self.add_columns).pack(pady=(42, 8))
        ttk.Button(transfer_buttons, text="<", width=4, command=self.remove_columns).pack()

        current_frame = ttk.Frame(columns_frame)
        current_frame.grid(row=1, column=2, sticky="nsew")
        current_frame.columnconfigure(0, weight=1)
        current_frame.rowconfigure(0, weight=1)
        self.current_columns_list = self._column_listbox(current_frame)
        current_scroll = ttk.Scrollbar(current_frame, orient="vertical", command=self.current_columns_list.yview)
        self.current_columns_list.configure(yscrollcommand=current_scroll.set)
        self.current_columns_list.grid(row=0, column=0, sticky="nsew")
        current_scroll.grid(row=0, column=1, sticky="ns")

        order_buttons = ttk.Frame(columns_frame, style="Panel.TFrame")
        order_buttons.grid(row=1, column=3, sticky="ns", padx=(10, 0))
        ttk.Button(order_buttons, text="^", width=4, command=lambda: self.move_current_columns(-1)).pack(pady=(42, 8))
        ttk.Button(order_buttons, text="v", width=4, command=lambda: self.move_current_columns(1)).pack()

        button_row = ttk.Frame(outer)
        button_row.grid(row=7, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(button_row, text="Cancel", command=self.cancel).pack(side="right")
        ttk.Button(button_row, text=self.action_label, command=self.accept, style="Accent.TButton").pack(side="right", padx=(0, 8))

    def _column_listbox(self, parent):
        return tk.Listbox(
            parent,
            selectmode="extended",
            width=48,
            height=10,
            exportselection=False,
            bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            selectbackground=COLORS["accent"],
            selectforeground="#ffffff",
            font=("TkDefaultFont", 10),
        )

    def _combo_row(self, parent, row, label, variable):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 12))
        combo = ttk.Combobox(parent, textvariable=variable, values=self.column_choices, width=46, state="readonly")
        combo.grid(row=row, column=1, sticky="ew", pady=4)
        if not variable.get():
            variable.set(NO_COLUMN)

    def _path_style_row(self, parent, row):
        ttk.Label(parent, text="Path style").grid(row=row, column=0, sticky="w", pady=4, padx=(0, 12))
        combo = ttk.Combobox(
            parent,
            textvariable=self.path_style_var,
            values=[label for label, _value in PATH_STYLE_CHOICES],
            width=46,
            state="readonly",
        )
        combo.grid(row=row, column=1, sticky="ew", pady=4)

    def refresh_column_lists(self, selected_current=()):
        current_set = set(self.current_columns)
        self.all_column_headers = []
        self.all_columns_list.delete(0, "end")
        for header in self.headers:
            shown = header in current_set
            label = f"[shown] {header}" if shown else header
            self.all_column_headers.append(header)
            self.all_columns_list.insert("end", label)
            index = self.all_columns_list.size() - 1
            self.all_columns_list.itemconfig(index, foreground=COLORS["accent"] if shown else COLORS["text"])

        self.current_columns_list.delete(0, "end")
        for header in self.current_columns:
            self.current_columns_list.insert("end", header)

        for index in selected_current:
            if 0 <= index < len(self.current_columns):
                self.current_columns_list.selection_set(index)
                self.current_columns_list.see(index)

    def add_columns(self):
        selected = [self.all_column_headers[index] for index in self.all_columns_list.curselection()]
        if not selected:
            return

        new_indices = []
        for header in selected:
            if header not in self.current_columns:
                self.current_columns.append(header)
                new_indices.append(len(self.current_columns) - 1)
        self.refresh_column_lists(new_indices)

    def remove_columns(self):
        selected = set(self.current_columns_list.curselection())
        if not selected:
            return

        self.current_columns = [column for index, column in enumerate(self.current_columns) if index not in selected]
        next_index = min(selected) if selected else 0
        if next_index >= len(self.current_columns):
            next_index = len(self.current_columns) - 1
        self.refresh_column_lists([next_index] if next_index >= 0 else [])

    def move_current_columns(self, direction):
        selected = list(self.current_columns_list.curselection())
        if not selected:
            return

        if direction < 0:
            for index in selected:
                if index > 0 and index - 1 not in selected:
                    self.current_columns[index - 1], self.current_columns[index] = self.current_columns[index], self.current_columns[index - 1]
            new_selection = [max(0, index - 1) for index in selected]
        else:
            for index in reversed(selected):
                if index < len(self.current_columns) - 1 and index + 1 not in selected:
                    self.current_columns[index + 1], self.current_columns[index] = self.current_columns[index], self.current_columns[index + 1]
            new_selection = [min(len(self.current_columns) - 1, index + 1) for index in selected]

        self.refresh_column_lists(new_selection)

    def accept(self):
        full_path = "" if self.full_path_var.get() == NO_COLUMN else self.full_path_var.get()
        folder = "" if self.folder_var.get() == NO_COLUMN else self.folder_var.get()
        filename = "" if self.filename_var.get() == NO_COLUMN else self.filename_var.get()

        if not full_path and not filename:
            messagebox.showerror("Missing mapping", "Select either a full path column or a filename column.")
            return

        metadata = tuple(self.current_columns)
        existing_units = dict(self.profile.size_units or {})
        size_units = {
            header: existing_units.get(header, unit)
            for header in metadata
            if (unit := existing_units.get(header) or detect_size_unit(header)) and unit != "ask"
        }
        path_style = self.path_style_values.get(self.path_style_var.get(), PATH_STYLE_AUTO)
        self.result = ImportProfile(full_path, folder, filename, metadata, size_units, path_style=path_style)
        self.destroy()

    def cancel(self):
        self.result = None
        self.destroy()


class SizeUnitDialog(tk.Toplevel):
    def __init__(self, parent, columns):
        super().__init__(parent)
        self.title("Interpret Size Columns")
        set_window_icon(self)
        self.resizable(False, False)
        self.result = None
        self.vars = {}

        self.configure(bg=COLORS["app_bg"])
        outer = ttk.Frame(self, padding=18, style="Panel.TFrame")
        outer.grid(row=0, column=0, sticky="nsew")

        ttk.Label(
            outer,
            text="These size columns do not show a unit in the header. Choose a unit or keep the value unchanged.",
            wraplength=560,
            style="PanelMuted.TLabel",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        choices = ("Keep unchanged", "Bytes", "KB", "MB", "GB")
        for row, column in enumerate(columns, start=1):
            ttk.Label(outer, text=column).grid(row=row, column=0, sticky="w", padx=(0, 14), pady=4)
            var = tk.StringVar(value="Bytes")
            combo = ttk.Combobox(outer, textvariable=var, values=choices, state="readonly", width=28)
            combo.grid(row=row, column=1, sticky="ew", pady=4)
            self.vars[column] = var

        button_row = ttk.Frame(outer, style="Panel.TFrame")
        button_row.grid(row=len(columns) + 1, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(button_row, text="Cancel", command=self.cancel).pack(side="right")
        ttk.Button(button_row, text="Apply", command=self.accept, style="Accent.TButton").pack(side="right", padx=(0, 8))

        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.wait_visibility()
        self.focus()

    def accept(self):
        mapping = {
            "Keep unchanged": "keep",
            "Bytes": "bytes",
            "KB": "kb",
            "MB": "mb",
            "GB": "gb",
        }
        self.result = {column: mapping[var.get()] for column, var in self.vars.items()}
        self.destroy()

    def cancel(self):
        self.result = None
        self.destroy()


class FilterListDialog(tk.Toplevel):
    def __init__(self, parent, values):
        super().__init__(parent)
        self.title("Edit Filter List")
        set_window_icon(self)
        self.resizable(False, False)
        self.result = None
        self.text_var = tk.StringVar(value="; ".join(values))

        self.configure(bg=COLORS["app_bg"])
        outer = ttk.Frame(self, padding=16, style="Panel.TFrame")
        outer.grid(row=0, column=0, sticky="nsew")
        ttk.Label(
            outer,
            text="Separate values with semicolons.",
            style="PanelMuted.TLabel",
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))
        entry = ttk.Entry(outer, textvariable=self.text_var, width=76, style="Filter.TEntry")
        entry.grid(row=1, column=0, sticky="ew")

        button_row = ttk.Frame(outer, style="Panel.TFrame")
        button_row.grid(row=2, column=0, sticky="e", pady=(12, 0))
        ttk.Button(button_row, text="Cancel", command=self.cancel, style="FilterGhost.TButton").pack(side="right")
        ttk.Button(button_row, text="Apply", command=self.accept, style="Accent.TButton").pack(side="right", padx=(0, 8))

        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.wait_visibility()
        entry.focus_set()

    def accept(self):
        self.result = split_filter_values(self.text_var.get())
        self.destroy()

    def cancel(self):
        self.result = None
        self.destroy()


class ColumnFilterDialog(tk.Toplevel):
    def __init__(self, parent, columns, filters):
        super().__init__(parent)
        self.title("Column Filters")
        set_window_icon(self)
        self.geometry("940x560")
        self.minsize(820, 460)
        self.result = None
        self.columns = columns
        self.filters = self.normalize_filters(filters)
        self.preset_var = tk.StringVar(value=FILTER_PRESET_NONE)
        self.rows = []
        self._syncing_rows = False

        self._build()
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.wait_visibility()
        self.focus()

    def _build(self):
        self.configure(bg=COLORS["app_bg"])
        outer = ttk.Frame(self, padding=(18, 16), style="Panel.TFrame")
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        preset_shell = tk.Frame(outer, bg="#99f6e4", bd=0)
        preset_shell.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        preset_shell.columnconfigure(0, weight=1)
        preset_row = ttk.Frame(preset_shell, style="FilterPreset.TFrame", padding=(12, 10))
        preset_row.grid(row=0, column=0, sticky="ew", padx=1, pady=1)
        preset_row.columnconfigure(1, weight=1)
        ttk.Label(preset_row, text="Preset", style="FilterPreset.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 10))
        preset = ttk.Combobox(
            preset_row,
            textvariable=self.preset_var,
            values=(FILTER_PRESET_NONE, FILTER_PRESET_IMAGES, FILTER_PRESET_VIDEOS, FILTER_PRESET_OFFICE, FILTER_PRESET_USER_DATA),
            state="readonly",
            width=28,
            style="Filter.TCombobox",
        )
        preset.grid(row=0, column=1, sticky="w")
        ttk.Button(preset_row, text="Apply preset", command=self.apply_preset, style="FilterPreset.TButton").grid(row=0, column=2, sticky="e", padx=(8, 0))

        list_shell = tk.Frame(outer, bg="#bfdbfe", bd=0)
        list_shell.grid(row=1, column=0, columnspan=2, sticky="nsew")
        list_shell.columnconfigure(0, weight=1)
        list_shell.rowconfigure(0, weight=1)
        list_body = ttk.Frame(list_shell, style="Panel.TFrame", padding=(10, 8))
        list_body.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        list_body.columnconfigure(0, weight=1)
        list_body.rowconfigure(0, weight=1)

        canvas = tk.Canvas(list_body, bg=COLORS["panel"], bd=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_body, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        inner = ttk.Frame(canvas, style="Panel.TFrame", padding=(2, 0, 8, 2))
        self.inner = inner
        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.columnconfigure(0, weight=1)

        header_frame = ttk.Frame(inner, style="Panel.TFrame")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.configure_filter_row_grid(header_frame)
        ttk.Label(header_frame, text="Logic", style="FilterHeader.TLabel").grid(row=0, column=0, sticky="w", padx=(10, 12))
        ttk.Label(header_frame, text="Column", style="FilterHeader.TLabel").grid(row=0, column=1, sticky="w", padx=(0, 12))
        ttk.Label(header_frame, text="Operator", style="FilterHeader.TLabel").grid(row=0, column=2, sticky="w", padx=(0, 12))
        ttk.Label(header_frame, text="Value", style="FilterHeader.TLabel").grid(row=0, column=3, sticky="w", padx=(0, 12))
        ttk.Button(header_frame, text="+", width=3, style="FilterAdd.TButton", command=self.append_filter_row).grid(row=0, column=4, sticky="e")

        def sync_scroll_region(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def sync_inner_width(event):
            canvas.itemconfigure(window_id, width=event.width)

        inner.bind("<Configure>", sync_scroll_region)
        canvas.bind("<Configure>", sync_inner_width)
        canvas.bind("<MouseWheel>", lambda event: canvas.yview_scroll(int(-1 * (event.delta / 120)), "units"))

        initial_filters = self.filters or [FilterClause(column=self.columns[0], operator=FILTER_ANY)]
        for clause in initial_filters:
            self.add_filter_row(clause)

        button_row = ttk.Frame(outer, style="Panel.TFrame")
        button_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        button_row.columnconfigure(0, weight=1)
        ttk.Button(button_row, text="Reset", command=self.clear, style="FilterGhost.TButton").grid(row=0, column=0, sticky="w")
        ttk.Button(button_row, text="Cancel", command=self.cancel, style="FilterGhost.TButton").grid(row=0, column=1, sticky="e", padx=(0, 8))
        ttk.Button(button_row, text="Apply", command=self.accept, style="Accent.TButton").grid(row=0, column=2, sticky="e")

    def configure_filter_row_grid(self, frame):
        frame.columnconfigure(0, minsize=76)
        frame.columnconfigure(1, minsize=175, weight=0)
        frame.columnconfigure(2, minsize=145, weight=0)
        frame.columnconfigure(3, minsize=360, weight=1)
        frame.columnconfigure(4, minsize=48)

    def normalize_filters(self, filters):
        if isinstance(filters, dict):
            return [
                FilterClause(column=column, operator=column_filter.operator, value=column_filter.value)
                for column, column_filter in filters.items()
            ]
        normalized = []
        for clause in filters or []:
            normalized.append(
                FilterClause(
                    column=getattr(clause, "column", self.columns[0]),
                    operator=getattr(clause, "operator", FILTER_ANY),
                    value=getattr(clause, "value", ""),
                    logical=getattr(clause, "logical", "AND") or "AND",
                )
            )
        return normalized

    def add_filter_row(self, clause=None):
        if clause is None:
            clause = FilterClause(column=self.columns[0], operator=FILTER_ANY, logical="AND")

        row_number = len(self.rows) + 1
        logical_var = tk.StringVar(value=clause.logical if clause.logical in {"AND", "OR"} else "AND")
        column_var = tk.StringVar(value=clause.column if clause.column in self.columns else self.columns[0])
        op_var = tk.StringVar(value=clause.operator if clause.operator in FILTER_OPERATORS else FILTER_ANY)
        value_var = tk.StringVar(value=clause.value)
        widgets = []

        row_shell = tk.Frame(self.inner, bg="#dbeafe", bd=0)
        row_shell.grid(row=row_number, column=0, columnspan=5, sticky="ew", pady=4)
        row_shell.columnconfigure(0, weight=1)
        row_frame = ttk.Frame(row_shell, style="FilterRule.TFrame", padding=(9, 7))
        row_frame.grid(row=0, column=0, sticky="ew", padx=1, pady=1)
        self.configure_filter_row_grid(row_frame)
        widgets.append(row_shell)

        if row_number == 1:
            logical_widget = ttk.Label(row_frame, text="Where", style="FilterRuleMuted.TLabel")
        else:
            logical_widget = ttk.Combobox(row_frame, textvariable=logical_var, values=("AND", "OR"), state="readonly", width=7, style="Filter.TCombobox")
        logical_widget.grid(row=0, column=0, sticky="ew", padx=(0, 12))

        column_combo = ttk.Combobox(row_frame, textvariable=column_var, values=self.columns, state="readonly", width=22, style="Filter.TCombobox")
        column_combo.grid(row=0, column=1, sticky="ew", padx=(0, 8))

        operator = ttk.Combobox(row_frame, textvariable=op_var, values=FILTER_OPERATORS, state="readonly", width=17, style="Filter.TCombobox")
        operator.grid(row=0, column=2, sticky="ew", padx=(0, 8))

        value_frame = ttk.Frame(row_frame, style="FilterRule.TFrame")
        value_frame.grid(row=0, column=3, sticky="ew", padx=(0, 8))
        value_frame.columnconfigure(0, weight=1)
        value = ttk.Entry(value_frame, textvariable=value_var, width=34, style="Filter.TEntry")
        value.grid(row=0, column=0, sticky="ew")
        Tooltip(value, "Separate multiple values with a semicolon,\ne.g. .png; .jpg; report")
        value_hint = ttk.Label(value_frame, text="No value needed", style="FilterHint.TLabel")
        chip_frame = ttk.Frame(value_frame, style="FilterRule.TFrame")
        chip_frame.columnconfigure(0, weight=1)
        chip_frame.columnconfigure(1, minsize=32, weight=0)

        row_state = {
            "logical": logical_var,
            "column": column_var,
            "operator": op_var,
            "value": value_var,
            "value_widget": value,
            "value_hint": value_hint,
            "chip_frame": chip_frame,
            "value_frame": value_frame,
            "widgets": widgets,
        }

        action_frame = ttk.Frame(row_frame, style="FilterRule.TFrame")
        action_frame.grid(row=0, column=4, sticky="e")
        remove_button = ttk.Button(action_frame, text="-", width=3, style="FilterDelete.TButton", command=lambda r=row_state: self.remove_filter_row(r))
        remove_button.pack(side="left")

        self.rows.append(row_state)

        def on_operator_change(*_args, r=row_state):
            self.sync_value_entry(r)
            self.mark_custom_filter()

        op_var.trace_add("write", on_operator_change)
        for var in (logical_var, column_var, value_var):
            var.trace_add("write", lambda *_args, r=row_state: self.on_filter_row_value_changed(r))
        self.sync_value_entry(row_state)

    def mark_custom_filter(self, *_args):
        if self._syncing_rows:
            return
        self.preset_var.set(FILTER_PRESET_NONE)

    def clause_from_row(self, row):
        return FilterClause(
            column=row["column"].get(),
            operator=row["operator"].get(),
            value=row["value"].get(),
            logical=row["logical"].get() if row["logical"].get() in {"AND", "OR"} else "AND",
        )

    def append_filter_row(self):
        self.mark_custom_filter()
        self.add_filter_row()

    def remove_filter_row(self, row):
        if row not in self.rows:
            return
        self.mark_custom_filter()
        if len(self.rows) == 1:
            self.set_filter_rows([FilterClause(column=self.columns[0], operator=FILTER_ANY)])
            return
        clauses = [self.clause_from_row(existing) for existing in self.rows if existing is not row]
        self.set_filter_rows(clauses)

    def apply_preset(self):
        preset = self.preset_var.get()
        if preset == FILTER_PRESET_IMAGES:
            self.set_filter_rows(self.extension_clauses((".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp", ".heic")))
        elif preset == FILTER_PRESET_VIDEOS:
            self.set_filter_rows(self.extension_clauses((".mp4", ".mov", ".avi", ".mkv", ".wmv", ".m4v", ".3gp")))
        elif preset == FILTER_PRESET_OFFICE:
            self.set_filter_rows(self.extension_clauses((
                ".doc", ".docx", ".docm", ".dot", ".dotx", ".dotm",
                ".xls", ".xlsx", ".xlsm", ".xlsb", ".xlt", ".xltx", ".xltm", ".xlam",
                ".ppt", ".pptx", ".pptm", ".pot", ".potx", ".potm", ".pps", ".ppsx", ".ppsm",
                ".rtf", ".odt", ".ods", ".odp",
            )))
        elif preset == FILTER_PRESET_USER_DATA:
            self.set_filter_rows(self.user_data_clauses())
        else:
            self.set_filter_rows([FilterClause(column=self.columns[0], operator=FILTER_ANY)])

    def extension_clauses(self, extensions):
        return [
            FilterClause(
                column=FILTER_NAME_COLUMN if FILTER_NAME_COLUMN in self.columns else self.columns[0],
                operator="Ends with",
                value="; ".join(extensions),
                logical="AND",
            )
        ]

    def user_data_clauses(self):
        clauses = [
            FilterClause(column=FILTER_PATH_COLUMN, operator="Contains", value="/Users/; /$Recycle.Bin/; /Recycler/", logical="AND"),
            FilterClause(column=FILTER_PATH_COLUMN, operator="Does not contain", value="/AppData/; /Temp/; /Tmp/; /Windows/; /Microsoft/", logical="AND"),
            FilterClause(column=FILTER_NAME_COLUMN, operator="Does not contain", value="$I30; desktop.ini; NTUSER.DAT", logical="AND"),
            FilterClause(column=FILTER_NAME_COLUMN, operator="Does not end with", value=".url; .lnk; .library-ms; .search-ms; .searchconnector-ms", logical="AND"),
        ]

        size_column = self.find_filter_column(("Size (bytes)", "File Size", "Size"), ("size", "byte"))
        if size_column:
            clauses.append(FilterClause(column=size_column, operator="Greater than", value="1 KB", logical="AND"))

        deleted_column = self.find_filter_column(("Is Deleted", "Deleted"), ("deleted", "geloescht", "gelöscht"))
        if deleted_column:
            clauses.append(FilterClause(column=deleted_column, operator="Does not contain", value="yes", logical="AND"))

        created_column = self.find_filter_column(("Created", "Created Time", "Creation Time", "Creation Date"), ("created", "creation", "erstellt"))
        if created_column:
            clauses.append(FilterClause(column=created_column, operator="Is set", logical="AND"))

        return clauses

    def find_filter_column(self, exact_names, required_parts):
        lookup = {column.lower(): column for column in self.columns}
        for name in exact_names:
            column = lookup.get(name.lower())
            if column:
                return column

        for column in self.columns:
            lowered = column.lower()
            if any(part in lowered for part in required_parts):
                return column
        return ""

    def set_filter_rows(self, clauses):
        self._syncing_rows = True
        try:
            for row in self.rows:
                for widget in row["widgets"]:
                    widget.destroy()
            self.rows.clear()
            normalized = []
            for index, clause in enumerate(clauses or []):
                normalized.append(
                    FilterClause(
                        column=clause.column if clause.column in self.columns else self.columns[0],
                        operator=clause.operator if clause.operator in FILTER_OPERATORS else FILTER_ANY,
                        value=clause.value,
                        logical="AND" if index == 0 else (clause.logical if clause.logical in {"AND", "OR"} else "AND"),
                    )
                )
            if not normalized:
                normalized = [FilterClause(column=self.columns[0], operator=FILTER_ANY)]
            for clause in normalized:
                self.add_filter_row(clause)
        finally:
            self._syncing_rows = False

    def sync_value_entry(self, row):
        entry = row["value_widget"]
        hint = row["value_hint"]
        chip_frame = row["chip_frame"]
        if row["operator"].get() in VALUELESS_FILTERS:
            row["value"].set("")
            entry.grid_remove()
            chip_frame.grid_remove()
            hint.grid(row=0, column=0, sticky="ew")
        elif len(split_filter_values(row["value"].get())) > 1:
            hint.grid_remove()
            entry.grid_remove()
            self.render_value_chips(row)
            chip_frame.grid(row=0, column=0, sticky="ew")
        else:
            hint.grid_remove()
            chip_frame.grid_remove()
            entry.grid(row=0, column=0, sticky="ew")
            entry.configure(state="normal")

    def on_filter_row_value_changed(self, row):
        self.sync_value_entry(row)
        self.mark_custom_filter()

    def render_value_chips(self, row):
        chip_frame = row["chip_frame"]
        for widget in chip_frame.winfo_children():
            widget.destroy()

        values = split_filter_values(row["value"].get())
        visible_values = values[:FILTER_VISIBLE_CHIPS]
        chip_area = tk.Frame(chip_frame, bg="#f8fafc", bd=0)
        chip_area.grid(row=0, column=0, sticky="w")
        mode_text, mode_bg, mode_fg = self.group_mode_badge(row["operator"].get())
        mode_badge = tk.Label(
            chip_area,
            text=mode_text,
            bg=mode_bg,
            fg=mode_fg,
            padx=7,
            pady=3,
            font=("TkDefaultFont", 9, "bold"),
        )
        mode_badge.pack(side="left", padx=(0, 7))
        for index, value in enumerate(visible_values):
            chip = tk.Label(
                chip_area,
                text=value,
                bg="#dbeafe",
                fg="#1e3a8a",
                padx=7,
                pady=3,
                font=("TkDefaultFont", 9),
            )
            chip.pack(side="left", padx=(0, 5))

        if len(values) > len(visible_values):
            more = tk.Label(
                chip_area,
                text=f"+{len(values) - len(visible_values)} more",
                bg="#e2e8f0",
                fg="#475569",
                padx=7,
                pady=3,
                font=("TkDefaultFont", 9, "bold"),
            )
            more.pack(side="left", padx=(0, 5))

        edit_icon = getattr(self.master, "icons", {}).get("edit")
        edit_button = ttk.Button(
            chip_frame,
            image=edit_icon,
            text="" if edit_icon else "Edit",
            width=3,
            style="FilterEdit.TButton",
            command=lambda r=row: self.edit_filter_list(r),
        )
        if edit_icon:
            edit_button.image = edit_icon
        edit_button.grid(row=0, column=1, sticky="ne", padx=(8, 0))

    def group_mode_badge(self, operator):
        if operator.startswith("Does not"):
            return "NONE OF", "#fee2e2", COLORS["danger"]
        return "ANY OF", "#ccfbf1", COLORS["accent"]

    def edit_filter_list(self, row):
        dialog = FilterListDialog(self, split_filter_values(row["value"].get()))
        self.wait_window(dialog)
        if dialog.result is None:
            return
        row["value"].set("; ".join(dialog.result))

    def clear(self):
        self.preset_var.set(FILTER_PRESET_NONE)
        self.set_filter_rows([FilterClause(column=self.columns[0], operator=FILTER_ANY)])

    def accept(self):
        result = []
        for row in self.rows:
            column = row["column"].get()
            operator = row["operator"].get()
            value_var = row["value"]
            value = clean_cell(value_var.get())
            if operator == FILTER_ANY:
                continue
            if operator not in VALUELESS_FILTERS and not value:
                continue
            if operator in NUMERIC_FILTERS and parse_number(value) is None and parse_size_label(value) is None:
                messagebox.showerror("Invalid filter", f"Enter a numeric value for {column}.")
                return
            logical = row["logical"].get() if result else "AND"
            result.append(FilterClause(column=column, operator=operator, value=value, logical=logical))
        self.result = result
        self.destroy()

    def cancel(self):
        self.result = None
        self.destroy()


class CompareRootDialog(tk.Toplevel):
    def __init__(self, parent, first_roots, second_roots, has_metadata_fields):
        super().__init__(parent)
        self.title("Compare Roots")
        set_window_icon(self)
        self.resizable(False, False)
        self.result = None
        self.first_roots = first_roots
        self.second_roots = second_roots
        self.has_metadata_fields = has_metadata_fields
        self.first_var = tk.StringVar(value="/")
        self.second_var = tk.StringVar(value="/")
        self.compare_metadata_var = tk.BooleanVar(value=False)

        self._build()
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.wait_visibility()
        self.focus()

    def _build(self):
        self.configure(bg=COLORS["app_bg"])
        outer = ttk.Frame(self, padding=18, style="Panel.TFrame")
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(1, weight=1)

        ttk.Label(
            outer,
            text="Choose which folder in each import should be treated as the same root.",
            wraplength=560,
            style="PanelMuted.TLabel",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 14))

        ttk.Label(outer, text="Loaded file root").grid(row=1, column=0, sticky="w", padx=(0, 12), pady=5)
        ttk.Combobox(outer, textvariable=self.first_var, values=self.first_roots, width=64).grid(row=1, column=1, sticky="ew", pady=5)

        ttk.Label(outer, text="Compare file root").grid(row=2, column=0, sticky="w", padx=(0, 12), pady=5)
        ttk.Combobox(outer, textvariable=self.second_var, values=self.second_roots, width=64).grid(row=2, column=1, sticky="ew", pady=5)

        button_row_index = 3
        if self.has_metadata_fields:
            mode_frame = ttk.Frame(outer, style="Panel.TFrame")
            mode_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))
            ttk.Label(mode_frame, text="Compare mode").grid(row=0, column=0, sticky="w", padx=(0, 12))
            options = ttk.Frame(mode_frame, style="Panel.TFrame")
            options.grid(row=0, column=1, sticky="w")
            ttk.Radiobutton(
                options,
                text="Names and paths only",
                variable=self.compare_metadata_var,
                value=False,
            ).pack(anchor="w")
            ttk.Radiobutton(
                options,
                text="Names, paths, and metadata fields",
                variable=self.compare_metadata_var,
                value=True,
            ).pack(anchor="w", pady=(3, 0))
            button_row_index = 4

        button_row = ttk.Frame(outer, style="Panel.TFrame")
        button_row.grid(row=button_row_index, column=0, columnspan=2, sticky="e", pady=(16, 0))
        ttk.Button(button_row, text="Cancel", command=self.cancel).pack(side="right")
        ttk.Button(button_row, text="Compare", command=self.accept, style="Accent.TButton").pack(side="right", padx=(0, 8))

    def accept(self):
        self.result = (
            normalize_path(self.first_var.get()) or "/",
            normalize_path(self.second_var.get()) or "/",
            bool(self.compare_metadata_var.get()) if self.has_metadata_fields else False,
        )
        self.destroy()

    def cancel(self):
        self.result = None
        self.destroy()


class CompareDetailWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Compare Details")
        set_window_icon(self)
        self.geometry("980x620")
        self.minsize(760, 460)
        self.records = []
        self.record_by_iid = {}

        self.configure(bg=COLORS["app_bg"])
        outer = ttk.Frame(self, padding=16, style="Panel.TFrame")
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)
        outer.rowconfigure(3, weight=1)

        self.scope_var = tk.StringVar()
        self.summary_var = tk.StringVar()
        ttk.Label(outer, textvariable=self.scope_var, style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(outer, textvariable=self.summary_var, style="PanelMuted.TLabel").grid(row=0, column=1, sticky="e", padx=(12, 0))

        list_frame = ttk.Frame(outer, style="Panel.TFrame")
        list_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(12, 10))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.diff_list = ttk.Treeview(
            list_frame,
            columns=("status", "path", "summary"),
            show="headings",
            style="Details.Treeview",
        )
        self.diff_list.heading("status", text="Status")
        self.diff_list.heading("path", text="Path")
        self.diff_list.heading("summary", text="Difference")
        self.diff_list.column("status", width=130, minwidth=100, stretch=False)
        self.diff_list.column("path", width=360, minwidth=180, stretch=True)
        self.diff_list.column("summary", width=380, minwidth=180, stretch=True)
        self.diff_list.grid(row=0, column=0, sticky="nsew")
        diff_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.diff_list.yview)
        diff_scroll.grid(row=0, column=1, sticky="ns")
        self.diff_list.configure(yscrollcommand=diff_scroll.set)
        self.diff_list.tag_configure("only_first", foreground="#b45309")
        self.diff_list.tag_configure("only_second", foreground="#047857")
        self.diff_list.tag_configure("path_changed", foreground="#1d4ed8")
        self.diff_list.tag_configure("changed", foreground="#1d4ed8")
        self.diff_list.bind("<<TreeviewSelect>>", self.on_select)

        self.note_var = tk.StringVar()
        ttk.Label(outer, textvariable=self.note_var, style="PanelMuted.TLabel").grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 6))

        self.detail_frame = ttk.Frame(outer, style="Panel.TFrame")
        self.detail_frame.grid(row=3, column=0, columnspan=2, sticky="nsew")
        self.detail_frame.columnconfigure(0, weight=1)
        self.detail_frame.rowconfigure(0, weight=1)
        self.change_table = ttk.Treeview(
            self.detail_frame,
            columns=("field", "loaded", "compare"),
            show="headings",
            style="Details.Treeview",
        )
        self.change_table.heading("field", text="What changed")
        self.change_table.heading("loaded", text="Loaded file")
        self.change_table.heading("compare", text="Compare file")
        self.change_table.column("field", width=180, minwidth=120, stretch=False)
        self.change_table.column("loaded", width=360, minwidth=160, stretch=True)
        self.change_table.column("compare", width=360, minwidth=160, stretch=True)
        self.change_table.grid(row=0, column=0, sticky="nsew")
        change_scroll = ttk.Scrollbar(self.detail_frame, orient="vertical", command=self.change_table.yview)
        change_scroll.grid(row=0, column=1, sticky="ns")
        self.change_table.configure(yscrollcommand=change_scroll.set)

        button_row = ttk.Frame(outer, style="Panel.TFrame")
        button_row.grid(row=4, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(button_row, text="Copy all", command=self.copy_all).pack(side="right")
        ttk.Button(button_row, text="Close", command=self.destroy).pack(side="right", padx=(0, 8))

        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def load(self, scope_path, records):
        self.records = records
        self.record_by_iid = {}
        self.scope_var.set(f"Compare details: {'Root' if scope_path == '/' else scope_path}")
        self.summary_var.set(f"{len(records):,} difference{'s' if len(records) != 1 else ''}")
        self.diff_list.delete(*self.diff_list.get_children())
        self.change_table.delete(*self.change_table.get_children())
        self.detail_frame.grid_remove()
        self.note_var.set("")

        for index, record in enumerate(records):
            iid = str(index)
            self.record_by_iid[iid] = record
            self.diff_list.insert(
                "",
                "end",
                iid=iid,
                values=(record["label"], record["path"], record["summary"]),
                tags=(record["status"],),
            )

        children = self.diff_list.get_children()
        if children:
            self.diff_list.selection_set(children[0])
            self.diff_list.focus(children[0])
            self.show_record(children[0])

    def on_select(self, event=None):
        selected = self.diff_list.focus()
        if selected:
            self.show_record(selected)

    def show_record(self, iid):
        record = self.record_by_iid.get(iid)
        if not record:
            return
        self.change_table.delete(*self.change_table.get_children())
        self.note_var.set(record["detail"])
        changes = record.get("changes") or []
        if changes:
            self.detail_frame.grid()
            for column, first_value, second_value in changes:
                self.change_table.insert("", "end", values=(column, self.value_text(first_value), self.value_text(second_value)))
        else:
            self.detail_frame.grid_remove()

    def copy_all(self):
        lines = []
        for record in self.records:
            lines.append(f"{record['label']}\t{record['path']}\t{record['summary']}")
            for column, first_value, second_value in record.get("changes") or []:
                lines.append(f"  {column}\tloaded: {self.value_text(first_value)}\tcompare: {self.value_text(second_value)}")
        text = "\n".join(lines)
        self.clipboard_clear()
        self.clipboard_append(text)

    def value_text(self, value):
        return value if value != "" else "[empty]"


class TreeExportDialog(tk.Toplevel):
    """Options for copying or exporting a folder tree.

    ``result`` is None on cancel, otherwise a dict with:
    action ("clipboard" | "text" | "html"), include_files (bool),
    max_depth (int, 0 = unlimited), annotate (bool), checked_only (bool).
    """

    def __init__(self, parent, scope_label, has_sizes=False, selection=False, checked_count=0):
        super().__init__(parent)
        self.title("Copy tree")
        set_window_icon(self)
        self.resizable(False, False)
        self.result = None

        self.include_files_var = tk.StringVar(value="files")
        self.scope_var = tk.StringVar(value="all")
        self.depth_var = tk.StringVar(value="0")
        self.annotate_var = tk.BooleanVar(value=False)

        self.configure(bg=COLORS["app_bg"])
        outer = ttk.Frame(self, padding=18, style="Panel.TFrame")
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(1, weight=1)

        if selection:
            heading = f"Tree of the selected items in {scope_label}" if scope_label else "Tree of the selected items"
        else:
            heading = f"Tree for {scope_label}" if scope_label else "Tree export"
        row = 0
        ttk.Label(outer, text=heading, style="PanelTitle.TLabel").grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 12))
        row += 1

        ttk.Label(outer, text="Include").grid(row=row, column=0, sticky="nw", padx=(0, 14), pady=(0, 4))
        include_options = ttk.Frame(outer, style="Panel.TFrame")
        include_options.grid(row=row, column=1, sticky="w", pady=(0, 4))
        ttk.Radiobutton(include_options, text="Folders and files", variable=self.include_files_var, value="files").pack(anchor="w")
        ttk.Radiobutton(include_options, text="Folders only", variable=self.include_files_var, value="folders").pack(anchor="w", pady=(3, 0))
        row += 1

        if checked_count:
            ttk.Label(outer, text="Items").grid(row=row, column=0, sticky="nw", padx=(0, 14), pady=(10, 0))
            scope_options = ttk.Frame(outer, style="Panel.TFrame")
            scope_options.grid(row=row, column=1, sticky="w", pady=(10, 0))
            ttk.Radiobutton(scope_options, text="All items", variable=self.scope_var, value="all").pack(anchor="w")
            checked_label = f"Only checked items ({checked_count:,})"
            ttk.Radiobutton(scope_options, text=checked_label, variable=self.scope_var, value="checked").pack(anchor="w", pady=(3, 0))
            ttk.Label(
                outer,
                text="Exactly the checked folders and files are exported.",
                wraplength=420,
                style="PanelMuted.TLabel",
            ).grid(row=row + 1, column=1, sticky="w", pady=(2, 0))
            row += 2

        ttk.Label(outer, text="Maximum depth").grid(row=row, column=0, sticky="w", padx=(0, 14), pady=(10, 0))
        depth_row = ttk.Frame(outer, style="Panel.TFrame")
        depth_row.grid(row=row, column=1, sticky="w", pady=(10, 0))
        ttk.Spinbox(depth_row, from_=0, to=999, textvariable=self.depth_var, width=6).pack(side="left")
        ttk.Label(depth_row, text="0 = all levels", style="PanelMuted.TLabel").pack(side="left", padx=(10, 0))
        row += 1

        ttk.Label(
            outer,
            text="Levels below the depth limit are shown as […] with the number of hidden folders and files.",
            wraplength=420,
            style="PanelMuted.TLabel",
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(6, 0))
        row += 1

        annotate_text = "Show file count and total size for each folder" if has_sizes else "Show file count for each folder"
        ttk.Checkbutton(outer, text=annotate_text, variable=self.annotate_var).grid(row=row, column=0, columnspan=2, sticky="w", pady=(12, 0))
        row += 1

        button_row = ttk.Frame(outer, style="Panel.TFrame")
        button_row.grid(row=row, column=0, columnspan=2, sticky="e", pady=(18, 0))
        ttk.Button(button_row, text="Cancel", command=self.cancel, style="FilterGhost.TButton").pack(side="right")
        ttk.Button(button_row, text="Save as HTML...", command=lambda: self.accept("html"), style="Tool.TButton").pack(side="right", padx=(0, 8))
        ttk.Button(button_row, text="Save as text...", command=lambda: self.accept("text"), style="Tool.TButton").pack(side="right", padx=(0, 8))
        ttk.Button(button_row, text="Copy to clipboard", command=lambda: self.accept("clipboard"), style="Accent.TButton").pack(side="right", padx=(0, 8))

        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.bind("<Return>", lambda _event: self.accept("clipboard"))
        self.bind("<Escape>", lambda _event: self.cancel())
        self.wait_visibility()
        self.focus()

    def accept(self, action):
        depth_text = clean_cell(self.depth_var.get())
        try:
            max_depth = int(depth_text) if depth_text else 0
        except ValueError:
            max_depth = -1
        if max_depth < 0:
            messagebox.showerror("Invalid depth", "Maximum depth must be a whole number (0 = all levels).", parent=self)
            return

        self.result = {
            "action": action,
            "include_files": self.include_files_var.get() == "files",
            "max_depth": max_depth,
            "annotate": bool(self.annotate_var.get()),
            "checked_only": self.scope_var.get() == "checked",
        }
        self.destroy()

    def cancel(self):
        self.result = None
        self.destroy()


