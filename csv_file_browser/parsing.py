import csv
import hashlib

from .models import FileEntry, ImportProfile, TREE_PREFIX_CHARS
from .utils import clean_cell, detect_size_unit, normalize_path

def best_column(headers, candidates):
    normalized = {header.lower().replace("_", " ").strip(): header for header in headers}
    for candidate in candidates:
        key = candidate.lower().replace("_", " ").strip()
        if key in normalized:
            return normalized[key]
    for header in headers:
        lowered = header.lower()
        if any(candidate.lower() in lowered for candidate in candidates):
            return header
    return ""


def normalized_header_name(header):
    return clean_cell(header).lower().replace("_", " ").strip()


def is_ftk_listing(headers):
    names = {normalized_header_name(header) for header in headers}
    has_core_path = "filename" in names and "full path" in names
    has_ftk_metadata = "is deleted" in names or any(name.startswith("size") for name in names)
    return has_core_path and has_ftk_metadata


def detect_import_profile(headers):
    full_path = best_column(headers, ("Full Path", "Path", "Pfad", "Dateipfad"))
    filename = best_column(headers, ("Filename", "File Name", "Name", "Dateiname"))
    folder = best_column(headers, ("Folder", "Directory", "Parent Path", "Ordner"))

    if not full_path and not filename:
        return None

    path_columns = {full_path, filename, folder, ""}
    metadata = tuple(header for header in headers if header not in path_columns)
    size_units = {header: unit for header in metadata if (unit := detect_size_unit(header)) and unit != "ask"}
    return ImportProfile(
        full_path_column=full_path,
        folder_column=folder,
        filename_column=filename,
        metadata_columns=metadata,
        size_units=size_units,
    )


def read_csv_rows(file_path):
    encodings = ("utf-16", "utf-8-sig", "utf-8", "cp1252", "latin1")
    last_error = None

    for encoding in encodings:
        try:
            with open(file_path, "r", encoding=encoding, newline="") as handle:
                sample = handle.read(8192)
                handle.seek(0)
                delimiter = sniff_delimiter(sample)
                reader = csv.DictReader(handle, delimiter=delimiter)
                rows = [
                    {clean_cell(key): clean_cell(value) for key, value in row.items() if key is not None}
                    for row in reader
                ]
                headers = [clean_cell(header) for header in (reader.fieldnames or [])]
                if headers:
                    return headers, rows, encoding, delimiter
        except Exception as exc:
            last_error = exc

    raise ValueError(f"CSV could not be read: {last_error}")


def sniff_delimiter(sample):
    if not sample:
        return ","
    try:
        return csv.Sniffer().sniff(sample, delimiters="\t,;|").delimiter
    except csv.Error:
        counts = {delimiter: sample.count(delimiter) for delimiter in ("\t", ";", ",", "|")}
        return max(counts, key=counts.get)


def file_md5(file_path):
    digest = hashlib.md5()
    with open(file_path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def child_tree_path(parent, name):
    if parent == "/":
        return normalize_path(name)
    return normalize_path(f"{parent}/{name}")


def read_tree_listing(file_path):
    encodings = ("utf-8-sig", "utf-16", "cp850", "cp437", "cp1252", "latin1")
    last_error = None

    for encoding in encodings:
        try:
            with open(file_path, "r", encoding=encoding) as handle:
                text = handle.read()
            entries = parse_tree_listing(text)
            return entries, encoding
        except Exception as exc:
            last_error = exc

    raise ValueError(f"Tree text could not be read: {last_error}")


def parse_tree_listing(text):
    lines = [line.rstrip("\r\n") for line in text.splitlines()]
    root_index = find_tree_root_index(lines)
    if root_index is None:
        raise ValueError("No tree root was found.")

    entries = []
    stack = ["/"]

    for line in lines[root_index + 1:]:
        if is_tree_skip_line(line):
            continue

        directory = split_tree_directory_line(line)
        if directory:
            depth, name = directory
            while len(stack) <= depth:
                stack.append("/")
            parent = stack[depth]
            path = child_tree_path(parent, name)
            entries.append(FileEntry(name=name, folder=path, full_path=path, metadata={}, is_folder=True))
            stack = stack[: depth + 1]
            stack.append(path)
            continue

        file_item = split_tree_file_line(line)
        if not file_item:
            continue

        depth, name = file_item
        parent = stack[depth] if depth < len(stack) else stack[-1]
        full_path = child_tree_path(parent, name)
        entries.append(FileEntry(name=name, folder=parent, full_path=full_path, metadata={}, is_folder=False))

    if not entries:
        raise ValueError("The tree text did not contain folders or files.")
    return entries


def find_tree_root_index(lines):
    for index, line in enumerate(lines):
        if is_tree_skip_line(line):
            continue
        if split_tree_directory_line(line) or split_tree_file_line(line):
            continue
        return index
    return None


def is_tree_skip_line(line):
    text = line.strip()
    lower = text.lower()
    if not text:
        return True
    if ">tree" in lower:
        return True
    if lower.startswith(("folder path listing", "volume serial number", "no subfolders exist")):
        return True
    return all(char in TREE_PREFIX_CHARS for char in line)


def split_generated_tree_line(line):
    for marker in ("\u251c\u2500\u2500\u2500", "\u2514\u2500\u2500\u2500", "+---", "\\---", "\u2523 ", "\u2517 ", "\u251c ", "\u2514 "):
        marker_index = line.find(marker)
        if marker_index < 0:
            continue
        name = clean_cell(line[marker_index + len(marker):])
        if name:
            return marker, marker_index // 4, name
    return None


def strip_tree_item_icon(name):
    text = clean_cell(name)
    for icon in ("\U0001f4c2", "\U0001f4c1", "\U0001f4dc", "\U0001f4c4"):
        if text.startswith(icon):
            return clean_cell(text[len(icon):])
    return text


def has_tree_folder_icon(name):
    return clean_cell(name).startswith(("\U0001f4c2", "\U0001f4c1"))


def has_tree_file_icon(name):
    return clean_cell(name).startswith(("\U0001f4dc", "\U0001f4c4"))


def split_tree_directory_line(line):
    branch = split_generated_tree_line(line)
    if not branch:
        return None

    marker, depth, name = branch
    if marker in ("\u2523 ", "\u2517 ", "\u251c ", "\u2514 "):
        if has_tree_file_icon(name):
            return None
        if not has_tree_folder_icon(name):
            return None

    name = strip_tree_item_icon(name)
    if name:
        return depth, name
    return None


def split_tree_file_line(line):
    if split_tree_directory_line(line):
        return None

    branch = split_generated_tree_line(line)
    if branch:
        marker, depth, name = branch
        if marker in ("\u2523 ", "\u2517 ", "\u251c ", "\u2514 ") and has_tree_file_icon(name):
            name = strip_tree_item_icon(name)
            if name:
                return depth, name

    prefix_len = 0
    while prefix_len + 4 <= len(line) and all(char in TREE_PREFIX_CHARS for char in line[prefix_len:prefix_len + 4]):
        prefix_len += 4

    if prefix_len == 0:
        return None

    name = clean_cell(line[prefix_len:])
    if not name or name in {".", ".."}:
        return None
    return max(0, (prefix_len // 4) - 1), name


