# CSV File Browser

A small Tkinter desktop tool for browsing, filtering, and comparing CSV-based file listings and tree-text exports. It is designed for DFIR/eDiscovery-style file inventories, but it can also load regular CSV files with custom path and metadata column mappings.

---

## Features

- CSV import with automatic detection for typical FTK listings  
- Manual visible-column management via **Manage columns**  
- Saved import profiles for recurring CSV column mappings  
- Automatic path-style detection for Windows and Linux/macOS listings  
- Import warnings for ambiguous or mixed path separators  
- Import for tree-text files and tree exports copied from the app  
- Folder navigation with detail view, search, filters, and sorting  
- File properties window on double-click  
- Folder tree export via **Copy tree...** with folders-only or folders-plus-files output, a depth limit (`[…]` markers show hidden folder/file counts and sizes), optional per-folder counts, and clipboard, text-file, or interactive HTML output  
- Multi-select in the detail view with tree copy, full-path copy, and CSV export for the selection  
- Comparison of two imports with highlights for new, missing, and changed items  
- Export of the current view to CSV  

---

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
|   |-- profile_store.py          # Saved import profile persistence
|   `-- utils.py                  # Path, size, and filter helpers
|-- examples/                     # Synthetic demo data for screenshots/testing
|-- icons/                        # UI icons
|-- README.md
|-- LICENSE
`-- requirements.txt
```

---

## Supported Input Formats

- CSV file listings with a full-path column (e.g. `Full Path`, `Path`, `Pfad`, `Dateipfad`)  
- CSV file listings with separate folder and filename columns  
- Typical FTK-style CSV listings (auto-detected)  
- Custom CSV exports configured via **Manage columns**  
- Tree text files from Windows `tree` output  
- Tree text copied from this app  

Paths are normalized internally for navigation. The importer detects:

- Windows paths (`C:\Users\...`)  
- POSIX paths (`/home/...`)  
- Mixed separators (with warning + manual selection)

Import profiles are saved locally for reuse with matching CSV header sets.

---

## Example Data

The `examples/` folder contains synthetic demo data for screenshots and local testing. It does not contain real case data.

- `examples/ftk_sample_file_listing.csv` – FTK-style file listing with fictional data

### Main View

![ExampleMainView](https://github.com/lx9821/csvFileBrowser/blob/4cf22e3e3ee4b5d38e47c3e6e3e5bc5d904c11ec/examples/ExampleScreenshot.png)

### Filter View Example

![ExampleFilterView](https://github.com/lx9821/csvFileBrowser/blob/7c963332c22fcb0bb92208de663561b2b5b43cc5/examples/ExampleScreenshotFilterView.png)

### Column Management Example

![ExampleColumnView](https://github.com/lx9821/csvFileBrowser/blob/7c963332c22fcb0bb92208de663561b2b5b43cc5/examples/ExampleScreenshotColumnView.png)

---

## Run

```powershell
python file_browser.pyw
```

Or run as a module:

```powershell
python -m csv_file_browser
```

---

## Dependencies

The app uses Python/Tkinter. `Pillow` is recommended for proper icon scaling.

```powershell
pip install -r requirements.txt
```

---

## Build

A PyInstaller spec is included for Windows builds:

```powershell
pyinstaller CsvFileBrowser.spec
```

The `icons/` directory is included as application data by the spec file.
