import posixpath

from .models import PATH_STYLE_AUTO, PATH_STYLE_POSIX, PATH_STYLE_WINDOWS

def clean_cell(value):
    if value is None:
        return ""
    return str(value).replace("\x00", "").strip()


def split_filter_values(value):
    text = clean_cell(value)
    if not text:
        return []
    values = []
    for line in text.replace("\r", "\n").split("\n"):
        for part in line.split(";"):
            part = clean_cell(part)
            if part:
                values.append(part)
    return values or [text]


def normalize_path(path, path_style=PATH_STYLE_WINDOWS):
    path = clean_cell(path).strip('"')
    if path_style != PATH_STYLE_POSIX:
        path = path.replace("\\", "/")
    while "//" in path:
        path = path.replace("//", "/")
    path = path.strip()
    if not path:
        return ""
    path = path.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return posixpath.normpath(path)


def path_has_windows_drive(path):
    text = clean_cell(path).strip('"')
    return len(text) >= 3 and text[1] == ":" and text[0].isalpha() and text[2] in "\\/"


def path_has_unc_prefix(path):
    text = clean_cell(path).strip('"')
    return text.startswith("\\\\") or text.startswith("//")


def path_is_posix_absolute(path):
    text = clean_cell(path).strip('"')
    return text.startswith("/") and not text.startswith("//")


def path_separator_stats(paths):
    stats = {
        "total": 0,
        "slash": 0,
        "backslash": 0,
        "windows_drive": 0,
        "unc": 0,
        "posix_absolute": 0,
        "mixed": 0,
        "posix_with_backslash": 0,
        "relative_with_backslash": 0,
        "backslash_samples": [],
        "mixed_samples": [],
    }
    for raw_path in paths:
        text = clean_cell(raw_path).strip('"')
        if not text:
            continue
        stats["total"] += 1
        has_slash = "/" in text
        has_backslash = "\\" in text
        if has_slash:
            stats["slash"] += 1
        if has_backslash:
            stats["backslash"] += 1
            if len(stats["backslash_samples"]) < 3:
                stats["backslash_samples"].append(text)
        if has_slash and has_backslash:
            stats["mixed"] += 1
            if len(stats["mixed_samples"]) < 3:
                stats["mixed_samples"].append(text)
        if path_has_windows_drive(text):
            stats["windows_drive"] += 1
        if path_has_unc_prefix(text):
            stats["unc"] += 1
        if path_is_posix_absolute(text):
            stats["posix_absolute"] += 1
            if has_backslash:
                stats["posix_with_backslash"] += 1
        elif has_backslash and not path_has_windows_drive(text) and not path_has_unc_prefix(text):
            stats["relative_with_backslash"] += 1
    return stats


def infer_path_style(paths):
    stats = path_separator_stats(paths)
    if stats["windows_drive"] or stats["unc"]:
        return PATH_STYLE_WINDOWS, stats
    if stats["posix_absolute"]:
        return PATH_STYLE_POSIX, stats
    if stats["backslash"] > stats["slash"]:
        return PATH_STYLE_WINDOWS, stats
    if stats["slash"] and not stats["backslash"]:
        return PATH_STYLE_POSIX, stats
    return PATH_STYLE_WINDOWS, stats


def resolve_path_style(path_style, paths):
    if path_style and path_style != PATH_STYLE_AUTO:
        return path_style, path_separator_stats(paths)
    return infer_path_style(paths)


def path_style_label(path_style):
    labels = {
        PATH_STYLE_AUTO: "Auto detect",
        PATH_STYLE_WINDOWS: "Windows paths",
        PATH_STYLE_POSIX: "Linux/macOS paths",
    }
    return labels.get(path_style, "Auto detect")


def path_style_warnings(paths, path_style=PATH_STYLE_AUTO):
    resolved_style, stats = resolve_path_style(path_style, paths)
    warnings = []
    if not stats["total"]:
        warnings.append("No path values were found in the selected path columns.")
        return resolved_style, warnings, stats

    if path_style == PATH_STYLE_AUTO:
        warnings.append(f"Path style auto-detected as {path_style_label(resolved_style)}.")

    if stats["mixed"]:
        samples = "; ".join(stats["mixed_samples"])
        warnings.append(f"{stats['mixed']:,} path(s) contain both '/' and '\\'. Example: {samples}")

    if resolved_style == PATH_STYLE_POSIX and stats["posix_with_backslash"]:
        samples = "; ".join(stats["backslash_samples"])
        warnings.append(
            f"{stats['posix_with_backslash']:,} POSIX-looking path(s) contain backslashes. "
            f"Backslashes will be kept as filename characters. Example: {samples}"
        )

    if resolved_style == PATH_STYLE_WINDOWS and stats["relative_with_backslash"] and not stats["windows_drive"] and not stats["unc"]:
        samples = "; ".join(stats["backslash_samples"])
        warnings.append(
            f"{stats['relative_with_backslash']:,} relative path(s) use backslashes without a drive or UNC prefix. "
            f"They are treated as Windows separators. Example: {samples}"
        )

    return resolved_style, warnings, stats


def parent_path(path):
    parent = posixpath.dirname(path)
    return parent if parent and parent != "." else "/"


def display_name(path):
    if path == "/":
        return "Root"
    return posixpath.basename(path)


def shorten_label(label, max_length=28):
    if len(label) <= max_length:
        return label
    return label[: max_length - 3] + "..."


def looks_deleted(value):
    return clean_cell(value).lower() in {"yes", "ja", "true", "1", "deleted", "geloescht", "gel\u00f6scht"}


def parse_number(value):
    text = clean_cell(value)
    if not text:
        return None
    text = text.replace("\u00a0", "").replace(" ", "")
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def format_size(value, unit):
    number = parse_number(value)
    if number is None or unit == "keep":
        return clean_cell(value)

    multiplier = {
        "bytes": 1,
        "kb": 1024,
        "mb": 1024**2,
        "gb": 1024**3,
    }.get(unit, 1)
    size = number * multiplier

    labels = ("B", "KB", "MB", "GB", "TB")
    index = 0
    while size >= 1024 and index < len(labels) - 1:
        size /= 1024
        index += 1

    if index == 0:
        return f"{int(size):,} {labels[index]}"
    if size < 10:
        return f"{size:.2f} {labels[index]}"
    if size < 100:
        return f"{size:.1f} {labels[index]}"
    return f"{size:.0f} {labels[index]}"


def format_size_bytes(size):
    labels = ("B", "KB", "MB", "GB", "TB")
    index = 0
    size = float(size or 0)
    while size >= 1024 and index < len(labels) - 1:
        size /= 1024
        index += 1

    if index == 0:
        return f"{int(size):,} {labels[index]}"
    if size < 10:
        return f"{size:.2f} {labels[index]}"
    if size < 100:
        return f"{size:.1f} {labels[index]}"
    return f"{size:.0f} {labels[index]}"


def detect_size_unit(column):
    lowered = column.lower().replace("_", " ").replace("-", " ")
    if "byte" in lowered or "(b)" in lowered:
        return "bytes"
    if "kilobyte" in lowered or "kbyte" in lowered or "(kb)" in lowered or " kb" in lowered:
        return "kb"
    if "megabyte" in lowered or "mbyte" in lowered or "(mb)" in lowered or " mb" in lowered:
        return "mb"
    if "gigabyte" in lowered or "gbyte" in lowered or "(gb)" in lowered or " gb" in lowered:
        return "gb"
    if "filesize" in lowered.replace(" ", "") or "file size" in lowered or "size" in lowered or "groesse" in lowered:
        return "ask"
    return ""


def parse_size_label(value):
    text = clean_cell(value)
    if not text:
        return None
    parts = text.split()
    if not parts:
        return None
    number = parse_number(parts[0])
    if number is None:
        return None
    unit = parts[1].upper() if len(parts) > 1 else "B"
    multiplier = {
        "B": 1,
        "KB": 1024,
        "MB": 1024**2,
        "GB": 1024**3,
        "TB": 1024**4,
    }.get(unit)
    if multiplier is None:
        return None
    return number * multiplier


def looks_numeric_column(column):
    lowered = column.lower()
    hints = ("count", "number", "num", "id", "size", "bytes", "length", "anzahl", "nummer", "groesse")
    return any(hint in lowered for hint in hints)


