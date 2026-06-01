from dataclasses import dataclass
from typing import Optional

APP_TITLE = "CSV File Browser"
NO_COLUMN = "(none)"
FILTER_NAME_COLUMN = "Name"
FILTER_PATH_COLUMN = "Full Path"
FILTER_ANY = "Any"
FILTER_OPERATORS = (
    FILTER_ANY,
    "Contains",
    "Does not contain",
    "Equals",
    "Does not equal",
    "Starts with",
    "Does not start with",
    "Ends with",
    "Does not end with",
    "Is empty",
    "Is not empty",
    "Is set",
    "Is not set",
    "Greater than",
    "Less than",
)
VALUELESS_FILTERS = {FILTER_ANY, "Is empty", "Is not empty", "Is set", "Is not set"}
NUMERIC_FILTERS = {"Greater than", "Less than"}
FILTER_PRESET_NONE = "No preset"
FILTER_PRESET_IMAGES = "Image files"
FILTER_PRESET_VIDEOS = "Video files"
FILTER_PRESET_OFFICE = "Office files"
FILTER_PRESET_USER_DATA = "User data"
FILTER_VISIBLE_CHIPS = 5
PATH_STYLE_AUTO = "auto"
PATH_STYLE_WINDOWS = "windows"
PATH_STYLE_POSIX = "posix"
PATH_STYLE_CHOICES = (
    ("Auto detect", PATH_STYLE_AUTO),
    ("Windows paths", PATH_STYLE_WINDOWS),
    ("Linux/macOS paths", PATH_STYLE_POSIX),
)

COLORS = {
    "app_bg": "#f4f6f8",
    "panel": "#ffffff",
    "panel_alt": "#f8fafc",
    "sidebar": "#f8fafc",
    "sidebar_hover": "#e8eef5",
    "sidebar_text": "#172033",
    "text": "#172033",
    "muted": "#667085",
    "border": "#dce3ec",
    "accent": "#0f766e",
    "accent_hover": "#0d5f59",
    "danger": "#b42318",
}

ICON_SIZE = (18, 18)
TREE_ICON_GAP = 5
TREE_COMBINED_ICON_WIDTH = ICON_SIZE[0] * 2 + TREE_ICON_GAP
PLATE_HITBOX_WIDTH = ICON_SIZE[0] + 4
PLATE_HITBOX_OFFSET = 10
TREE_PREFIX_CHARS = " \u00aa\u00a6\u2502\u2503|"
DIFF_INFO_HITBOX_WIDTH = ICON_SIZE[0] + 4
DETAIL_PAGE_SIZE = 1000
TREE_DUMMY_SUFFIX = "::dummy"
DETAIL_NUMBER_GAP = 6
DETAIL_NUMBER_MIN_WIDTH = 18
DETAIL_NUMBER_DIGITS = {
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "010", "010", "010"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
}


@dataclass
class ImportProfile:
    full_path_column: str = ""
    folder_column: str = ""
    filename_column: str = ""
    metadata_columns: tuple[str, ...] = ()
    size_units: Optional[dict] = None
    path_style: str = PATH_STYLE_AUTO


@dataclass
class ColumnFilter:
    operator: str
    value: str = ""


@dataclass
class FilterClause:
    column: str
    operator: str
    value: str = ""
    logical: str = "AND"


@dataclass
class FileEntry:
    name: str
    folder: str
    full_path: str
    metadata: dict
    is_folder: bool = False
    properties: Optional[dict] = None


