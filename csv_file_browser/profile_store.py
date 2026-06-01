import hashlib
import json
import os

from .models import ImportProfile, PATH_STYLE_AUTO


STORE_VERSION = 1


def config_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "CsvFileBrowser")


def profiles_path():
    return os.path.join(config_dir(), "import_profiles.json")


def header_signature(headers):
    payload = json.dumps([str(header) for header in headers], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def load_store():
    path = profiles_path()
    if not os.path.exists(path):
        return {"version": STORE_VERSION, "profiles": {}}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {"version": STORE_VERSION, "profiles": {}}
    if not isinstance(data, dict):
        return {"version": STORE_VERSION, "profiles": {}}
    data.setdefault("version", STORE_VERSION)
    data.setdefault("profiles", {})
    if not isinstance(data["profiles"], dict):
        data["profiles"] = {}
    return data


def save_store(data):
    os.makedirs(config_dir(), exist_ok=True)
    with open(profiles_path(), "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)


def profile_to_dict(profile, headers, name=""):
    return {
        "name": name or "Saved import profile",
        "headers": list(headers),
        "full_path_column": profile.full_path_column,
        "folder_column": profile.folder_column,
        "filename_column": profile.filename_column,
        "metadata_columns": list(profile.metadata_columns),
        "size_units": dict(profile.size_units or {}),
        "path_style": profile.path_style or PATH_STYLE_AUTO,
    }


def profile_from_dict(data, headers):
    if not isinstance(data, dict):
        return None
    header_set = set(headers)
    full_path = data.get("full_path_column", "")
    folder = data.get("folder_column", "")
    filename = data.get("filename_column", "")
    metadata = [column for column in data.get("metadata_columns", []) if column in header_set]
    size_units = {
        column: unit
        for column, unit in (data.get("size_units") or {}).items()
        if column in header_set
    }
    for column in (full_path, folder, filename):
        if column and column not in header_set:
            return None
    return ImportProfile(
        full_path_column=full_path,
        folder_column=folder,
        filename_column=filename,
        metadata_columns=tuple(metadata),
        size_units=size_units,
        path_style=data.get("path_style") or PATH_STYLE_AUTO,
    )


def load_import_profile(headers):
    store = load_store()
    signature = header_signature(headers)
    data = store["profiles"].get(signature)
    profile = profile_from_dict(data, headers)
    if not profile:
        return None, None
    return profile, data


def save_import_profile(headers, profile, name=""):
    store = load_store()
    signature = header_signature(headers)
    store["profiles"][signature] = profile_to_dict(profile, headers, name=name)
    save_store(store)
    return profiles_path()
