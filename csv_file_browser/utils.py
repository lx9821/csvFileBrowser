import posixpath

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


def normalize_path(path):
    path = clean_cell(path).strip('"').replace("\\", "/")
    while "//" in path:
        path = path.replace("//", "/")
    path = path.strip()
    if not path:
        return ""
    path = path.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return posixpath.normpath(path)


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


