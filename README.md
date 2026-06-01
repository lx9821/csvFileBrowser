# CSV File Browser

A small Tkinter desktop tool for browsing, filtering, and comparing CSV-based file listings and tree-text exports. It is designed for DFIR/eDiscovery-style file inventories, but it can also load regular CSV files with custom path and metadata column mappings.

## Features

- CSV import with automatic detection for typical FTK listings
- Manual visible-column management via **Manage columns**
- Import for tree-text files and tree exports copied from the app
- Folder navigation with detail view, search, filters, and sorting
- File properties window on double-click
- Folder tree copy actions for folders-only or folders-plus-files output
- Comparison of two imports with highlights for new, missing, and changed items
- Export of the current view to CSV

## Project Structure

```text
CsvFileBrowser/
|-- file_browser.pyw              # Windows/Tk launcher
|-- CsvFileBrowser.spec           # PyInstaller build config
|-- csv_file_browser/
|   |-- app.py                    # Main window and UI workflow
|   |-- dialogs.py                # Import, filter, and compare dialogs
|   |-- icons.py                  # Icon loading and generated UI icons
|   |-- models.py                 # Constants and dataclasses
|   |-- parsing.py                # CSV/tree import and detection
|   `-- utils.py                  # Path, size, and filter helpers
|-- icons/                        # UI icons
|-- README.md
|-- LICENSE
`-- requirements.txt
```

## Run

```powershell
python file_browser.pyw
```

Or run it as a module:

```powershell
python -m csv_file_browser
```

## Dependencies

The app uses Python/Tkinter. `Pillow` is recommended so PNG icons can be loaded and scaled cleanly.

```powershell
pip install -r requirements.txt
```

## Build

A PyInstaller spec is included for Windows builds:

```powershell
pyinstaller CsvFileBrowser.spec
```

The `icons/` directory is included as application data by the spec file.
