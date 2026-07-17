"""Persist per-file browsing sessions (checked items, plates, filters).

Sessions are keyed by the imported file's MD5 and stored in the user's
config directory (never next to the imported file).
"""

import json
import os

from .profile_store import config_dir

SESSION_STORE_VERSION = 1
MAX_SESSIONS = 50


def sessions_path():
    return os.path.join(config_dir(), "sessions.json")


def load_session_store():
    path = sessions_path()
    if not os.path.exists(path):
        return {"version": SESSION_STORE_VERSION, "sessions": {}}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {"version": SESSION_STORE_VERSION, "sessions": {}}
    if not isinstance(data, dict):
        return {"version": SESSION_STORE_VERSION, "sessions": {}}
    data.setdefault("version", SESSION_STORE_VERSION)
    data.setdefault("sessions", {})
    if not isinstance(data["sessions"], dict):
        data["sessions"] = {}
    return data


def save_session_store(data):
    os.makedirs(config_dir(), exist_ok=True)
    with open(sessions_path(), "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)


def session_has_content(data):
    if not isinstance(data, dict):
        return False
    return bool(
        data.get("checked_folders")
        or data.get("checked_files")
        or data.get("plated_folders")
        or data.get("filters")
        or data.get("search")
    )


def load_saved_session(file_md5):
    if not file_md5:
        return None
    store = load_session_store()
    data = store["sessions"].get(file_md5)
    return data if session_has_content(data) else None


def save_saved_session(file_md5, data):
    if not file_md5:
        return
    store = load_session_store()
    if session_has_content(data):
        store["sessions"][file_md5] = data
        sessions = store["sessions"]
        if len(sessions) > MAX_SESSIONS:
            # Drop the oldest sessions (by saved_at, missing timestamps first).
            ordered = sorted(sessions.items(), key=lambda item: item[1].get("saved_at", ""))
            for key, _value in ordered[: len(sessions) - MAX_SESSIONS]:
                del sessions[key]
    else:
        store["sessions"].pop(file_md5, None)
    try:
        save_session_store(store)
    except OSError:
        pass


def delete_saved_session(file_md5):
    if not file_md5:
        return
    store = load_session_store()
    if file_md5 in store["sessions"]:
        del store["sessions"][file_md5]
        try:
            save_session_store(store)
        except OSError:
            pass
