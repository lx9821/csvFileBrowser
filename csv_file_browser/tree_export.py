"""Helpers that render a folder structure as tree text or interactive HTML.

All functions operate on the app's plain data structures:
- tree_data: {folder_path: set(child_folder_paths)}
- folder_entries: {folder_path: [FileEntry, ...]} (direct files only)
"""

import html

from .utils import display_name, format_size_bytes

TREE_MORE_MARKER = "[…]"


def compute_tree_stats(root, tree_data, folder_entries, entry_size):
    """Return {folder: (recursive file count, recursive folder count, recursive size)}."""
    stats = {}

    def walk(folder):
        files = folder_entries.get(folder, [])
        file_count = len(files)
        size = sum(entry_size(entry) for entry in files)
        folder_count = 0
        for child in tree_data.get(folder, ()):
            child_files, child_folders, child_size = walk(child)
            file_count += child_files
            folder_count += child_folders + 1
            size += child_size
        stats[folder] = (file_count, folder_count, size)
        return file_count, folder_count, size

    walk(root)
    return stats


def count_label(count, singular, plural):
    return f"{count:,} {singular if count == 1 else plural}"


def hidden_summary(stats_entry, include_files, show_sizes):
    file_count, folder_count, size = stats_entry
    parts = []
    if folder_count:
        parts.append(count_label(folder_count, "folder", "folders"))
    if file_count:
        parts.append(count_label(file_count, "file", "files"))
    text = ", ".join(parts)
    if show_sizes and size:
        text += f" ({format_size_bytes(size)})"
    return text


def has_hidden_content(stats_entry, include_files):
    file_count, folder_count, _size = stats_entry
    return bool(folder_count or (include_files and file_count))


def folder_annotation(stats_entry, show_sizes):
    file_count, _folder_count, size = stats_entry
    parts = [count_label(file_count, "file", "files")]
    if show_sizes:
        parts.append(format_size_bytes(size))
    return f" ({', '.join(parts)})"


def sorted_child_folders(tree_data, folder):
    return sorted(tree_data.get(folder, set()), key=lambda path: display_name(path).lower())


def sorted_child_files(folder_entries, folder):
    return sorted(folder_entries.get(folder, []), key=lambda entry: entry.name.lower())


def generate_tree_text(
    root,
    root_label,
    tree_data,
    folder_entries,
    *,
    include_files=True,
    max_depth=0,
    annotate=False,
    show_sizes=False,
    entry_size=None,
    stats=None,
):
    """Render the structure below ``root`` as tree text.

    ``max_depth`` limits how many levels below the root are rendered
    (0 = unlimited). Hidden levels are marked with ``[…]`` plus the number
    of hidden folders/files (and their total size when available).
    """
    entry_size = entry_size or (lambda entry: 0)
    if stats is None:
        stats = compute_tree_stats(root, tree_data, folder_entries, entry_size)

    root_suffix = folder_annotation(stats.get(root, (0, 0, 0)), show_sizes) if annotate else ""
    lines = [f"{root_label}{root_suffix}"]

    def append_children(folder, prefix, depth):
        if max_depth and depth > max_depth:
            entry_stats = stats.get(folder, (0, 0, 0))
            if has_hidden_content(entry_stats, include_files):
                summary = hidden_summary(entry_stats, include_files, show_sizes)
                lines.append(f"{prefix}┗ {TREE_MORE_MARKER} {summary}")
            return

        folders = sorted_child_folders(tree_data, folder)
        files = sorted_child_files(folder_entries, folder) if include_files else []
        children = [("folder", child) for child in folders] + [("file", entry) for entry in files]

        for index, (kind, payload) in enumerate(children):
            is_last = index == len(children) - 1
            branch = "┗ " if is_last else "┣ "
            child_prefix = prefix + ("    " if is_last else "┃   ")

            if kind == "folder":
                suffix = folder_annotation(stats.get(payload, (0, 0, 0)), show_sizes) if annotate else ""
                lines.append(f"{prefix}{branch}\U0001f4c2 {display_name(payload)}{suffix}")
                append_children(payload, child_prefix, depth + 1)
            else:
                lines.append(f"{prefix}{branch}\U0001f4dc {payload.name}")

    append_children(root, "", 1)
    return "\n".join(lines)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root { --accent:#0f766e; --muted:#667085; --border:#dce3ec; --bg:#f4f6f8; --panel:#ffffff; --text:#172033; }
* { box-sizing:border-box; }
body { margin:0; font-family:'Segoe UI',system-ui,-apple-system,sans-serif; background:var(--bg); color:var(--text); }
header { background:var(--panel); border-bottom:1px solid var(--border); padding:16px 24px; position:sticky; top:0; z-index:2; }
h1 { margin:0 0 4px; font-size:18px; }
.sub { color:var(--muted); font-size:12px; }
.controls { margin-top:12px; display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
.controls input { flex:1 1 240px; max-width:360px; padding:7px 10px; border:1px solid var(--border); border-radius:6px; font-size:13px; }
.controls button { padding:7px 12px; border:1px solid var(--border); border-radius:6px; background:var(--panel); color:var(--text); cursor:pointer; font-size:13px; }
.controls button:hover { background:#eef2f7; }
main { padding:16px 24px 40px; }
#tree { background:var(--panel); border:1px solid var(--border); border-radius:8px; padding:12px 16px; font-size:14px; line-height:1.7; overflow-x:auto; }
details details, .children > .file, .children > .more { margin-left:22px; }
summary { cursor:pointer; user-select:none; border-radius:4px; padding:1px 4px; white-space:nowrap; }
summary:hover { background:#eef2f7; }
.icon { margin-right:6px; }
.file { padding:1px 4px; white-space:nowrap; }
.meta { color:var(--muted); font-size:12px; margin-left:8px; }
.more { color:var(--muted); font-style:italic; padding:1px 4px; }
.hidden { display:none; }
</style>
</head>
<body>
<header>
<h1>__TITLE__</h1>
<div class="sub">__SUBTITLE__</div>
<div class="controls">
<input id="filter" type="search" placeholder="Filter by name...">
<button type="button" onclick="setAll(true)">Expand all</button>
<button type="button" onclick="setAll(false)">Collapse all</button>
</div>
</header>
<main><div id="tree">
__BODY__
</div></main>
<script>
const treeRoot = document.getElementById('tree');
function setAll(open) {
  treeRoot.querySelectorAll('details').forEach((d) => { d.open = open; });
  if (!open) {
    const first = treeRoot.querySelector(':scope > details');
    if (first) first.open = true;
  }
}
function walk(container, query) {
  let visible = false;
  for (const child of container.children) {
    if (child.tagName === 'DETAILS') {
      const name = child.dataset.name || '';
      const selfMatch = !query || name.includes(query);
      const childrenBox = child.querySelector(':scope > .children');
      const childVisible = childrenBox ? walk(childrenBox, query) : false;
      const show = selfMatch || childVisible;
      child.classList.toggle('hidden', !show);
      if (query && childVisible) child.open = true;
      if (query && selfMatch && childrenBox) {
        childrenBox.querySelectorAll('.hidden').forEach((node) => node.classList.remove('hidden'));
      }
      visible = visible || show;
    } else {
      const name = child.dataset.name || '';
      const match = !query || name.includes(query);
      child.classList.toggle('hidden', Boolean(query) && !match);
      visible = visible || match;
    }
  }
  return visible;
}
document.getElementById('filter').addEventListener('input', (event) => {
  const query = event.target.value.trim().toLowerCase();
  walk(treeRoot, query);
  if (!query) treeRoot.querySelectorAll('.hidden').forEach((node) => node.classList.remove('hidden'));
});
</script>
</body>
</html>
"""


def generate_tree_html(
    root,
    root_label,
    tree_data,
    folder_entries,
    *,
    include_files=True,
    max_depth=0,
    annotate=False,
    show_sizes=False,
    entry_size=None,
    stats=None,
    source_name="",
):
    """Render the structure below ``root`` as a standalone interactive HTML page."""
    entry_size = entry_size or (lambda entry: 0)
    if stats is None:
        stats = compute_tree_stats(root, tree_data, folder_entries, entry_size)

    parts = []

    def folder_meta(folder):
        file_count, folder_count, size = stats.get(folder, (0, 0, 0))
        pieces = [count_label(folder_count, "folder", "folders"), count_label(file_count, "file", "files")]
        if show_sizes:
            pieces.append(format_size_bytes(size))
        return ", ".join(pieces)

    def append_folder(folder, depth):
        name = root_label if folder == root else display_name(folder)
        open_attr = " open" if depth <= 1 else ""
        meta = ""
        if annotate or folder == root:
            meta = f'<span class="meta">{html.escape(folder_meta(folder))}</span>'
        parts.append(f'<details class="folder"{open_attr} data-name="{html.escape(name.lower(), quote=True)}">')
        parts.append(f'<summary><span class="icon">\U0001f4c2</span>{html.escape(name)}{meta}</summary>')
        parts.append('<div class="children">')
        if max_depth and depth >= max_depth:
            entry_stats = stats.get(folder, (0, 0, 0))
            if has_hidden_content(entry_stats, include_files):
                summary = hidden_summary(entry_stats, include_files, show_sizes)
                parts.append(f'<div class="more" data-name="">{TREE_MORE_MARKER} {html.escape(summary)}</div>')
        else:
            for child in sorted_child_folders(tree_data, folder):
                append_folder(child, depth + 1)
            if include_files:
                for entry in sorted_child_files(folder_entries, folder):
                    size = entry_size(entry)
                    meta_span = f'<span class="meta">{format_size_bytes(size)}</span>' if show_sizes and size else ""
                    parts.append(
                        f'<div class="file" data-name="{html.escape(entry.name.lower(), quote=True)}">'
                        f'<span class="icon">\U0001f4dc</span>{html.escape(entry.name)}{meta_span}</div>'
                    )
        parts.append("</div></details>")

    append_folder(root, 0)

    title = f"Tree - {root_label}"
    subtitle_parts = []
    if source_name:
        subtitle_parts.append(f"Exported from {source_name}")
    subtitle_parts.append(folder_meta(root))
    if max_depth:
        subtitle_parts.append(f"limited to {count_label(max_depth, 'level', 'levels')}")
    if not include_files:
        subtitle_parts.append("folders only")

    return (
        HTML_TEMPLATE
        .replace("__TITLE__", html.escape(title))
        .replace("__SUBTITLE__", html.escape(" · ".join(subtitle_parts)))
        .replace("__BODY__", "\n".join(parts))
    )
