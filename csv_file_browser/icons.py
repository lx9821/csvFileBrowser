import os
import sys
import tkinter as tk

try:
    from PIL import Image, ImageOps, ImageTk
except Exception:
    Image = ImageOps = ImageTk = None

from .models import COLORS, ICON_SIZE, TREE_COMBINED_ICON_WIDTH, TREE_ICON_GAP


def resource_root():
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def app_icon_path():
    return os.path.join(resource_root(), "icons", "app_icon.ico")


def set_window_icon(window):
    icon_path = app_icon_path()
    if not os.path.exists(icon_path):
        return
    try:
        window.iconbitmap(icon_path)
    except (OSError, tk.TclError):
        pass

def load_icons():
    icon_dir = os.path.join(resource_root(), "icons")
    icons = {}

    def load(name):
        path = os.path.join(icon_dir, name)
        if not os.path.exists(path):
            return None
        if Image and ImageOps and ImageTk:
            try:
                with Image.open(path) as image:
                    image = image.convert("RGBA")
                    image = ImageOps.contain(image, ICON_SIZE, Image.LANCZOS)
                    canvas = Image.new("RGBA", ICON_SIZE, (0, 0, 0, 0))
                    offset = ((ICON_SIZE[0] - image.width) // 2, (ICON_SIZE[1] - image.height) // 2)
                    canvas.alpha_composite(image, offset)
                    return ImageTk.PhotoImage(canvas)
            except Exception:
                pass
        try:
            image = tk.PhotoImage(file=path)
            width_factor = max(1, (image.width() + ICON_SIZE[0] - 1) // ICON_SIZE[0])
            height_factor = max(1, (image.height() + ICON_SIZE[1] - 1) // ICON_SIZE[1])
            factor = max(width_factor, height_factor)
            return image.subsample(factor, factor) if factor > 1 else image
        except tk.TclError:
            return None

    def compose_tree_icon(plate, folder):
        if not plate and not folder:
            return None
        try:
            image = tk.PhotoImage(width=TREE_COMBINED_ICON_WIDTH, height=ICON_SIZE[1])

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

            copy_part(plate, 0)
            copy_part(folder, ICON_SIZE[0] + TREE_ICON_GAP)
            return image
        except tk.TclError:
            return plate or folder

    def create_sort_icon(direction):
        image = tk.PhotoImage(width=9, height=9)
        color = COLORS["accent"]
        rows = (
            (4,),
            (3, 4, 5),
            (2, 3, 4, 5, 6),
            (1, 2, 3, 4, 5, 6, 7),
        )
        if direction == "desc":
            rows = tuple(reversed(rows))
        for y, xs in enumerate(rows, start=2):
            for x in xs:
                image.put(color, (x, y))
        return image

    def create_info_icon():
        image = tk.PhotoImage(width=ICON_SIZE[0], height=ICON_SIZE[1])
        border = "#1d4ed8"
        fill = "#dbeafe"
        text = "#1e3a8a"
        cx = ICON_SIZE[0] // 2
        cy = ICON_SIZE[1] // 2
        radius = 7
        for y in range(ICON_SIZE[1]):
            for x in range(ICON_SIZE[0]):
                distance = (x - cx) ** 2 + (y - cy) ** 2
                if distance <= radius ** 2:
                    image.put(fill, (x, y))
                if radius ** 2 - 10 <= distance <= radius ** 2 + 4:
                    image.put(border, (x, y))
        for y in range(7, 14):
            image.put(text, (cx, y))
        image.put(text, (cx, 4))
        return image

    def create_edit_icon():
        image = tk.PhotoImage(width=ICON_SIZE[0], height=ICON_SIZE[1])
        color = COLORS["accent"]
        shadow = "#99f6e4"
        coords = (
            (12, 3), (13, 3),
            (11, 4), (12, 4), (13, 4), (14, 4),
            (10, 5), (11, 5), (12, 5), (13, 5),
            (9, 6), (10, 6), (11, 6),
            (8, 7), (9, 7), (10, 7),
            (7, 8), (8, 8), (9, 8),
            (6, 9), (7, 9), (8, 9),
            (5, 10), (6, 10), (7, 10),
            (4, 11), (5, 11), (6, 11),
            (3, 12), (4, 12), (5, 12),
        )
        for x, y in coords:
            image.put(color, (x, y))
        for point in ((3, 13), (4, 13), (3, 14)):
            image.put(shadow, point)
        return image

    icons["folder"] = load("folder.png")
    icons["default"] = load("files.png")
    icons["filter"] = load("filter.png")
    icons["load"] = load("load.png")
    icons["columns"] = load("columns.png")
    icons["plate_empty"] = load("plate_icon_empty_no_bg.png")
    icons["plate_filled"] = load("plate_icon_filled_no_bg.png")
    icons["folder_plate_empty"] = compose_tree_icon(icons["plate_empty"], icons["folder"])
    icons["folder_plate_filled"] = compose_tree_icon(icons["plate_filled"], icons["folder"])
    icons["sort_asc"] = create_sort_icon("asc")
    icons["sort_desc"] = create_sort_icon("desc")
    icons["info"] = create_info_icon()
    icons["edit"] = create_edit_icon()

    mapping = {
        ".pdf": "pdf.png",
        ".doc": "word.png",
        ".docx": "word.png",
        ".docm": "word.png",
        ".xls": "excel.png",
        ".xlsx": "excel.png",
        ".xlsm": "excel.png",
        ".xlsb": "excel.png",
        ".csv": "excel.png",
        ".ppt": "powerpoint.png",
        ".pptx": "powerpoint.png",
        ".pptm": "powerpoint.png",
        ".txt": "txt.png",
        ".log": "txt.png",
        ".zip": "zip.png",
        ".7z": "zip.png",
        ".rar": "zip.png",
        ".png": "images.png",
        ".jpg": "images.png",
        ".jpeg": "images.png",
        ".gif": "images.png",
        ".mp4": "video.png",
        ".avi": "video.png",
        ".mov": "video.png",
        ".mp3": "audio.png",
        ".wav": "audio.png",
        ".eml": "email.png",
        ".msg": "outlook.png",
    }

    for ext, filename in mapping.items():
        icons[ext] = load(filename)

    return icons


