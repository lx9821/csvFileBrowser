# CSV File Browser

Ein kleines Tkinter-Tool zum Durchsuchen, Filtern und Vergleichen von CSV-basierten Dateilistings und Tree-Text-Exports. Es ist auf DFIR/eDiscovery-artige Dateilisten ausgelegt, kann aber auch normale CSV-Dateien mit frei gemappten Pfad- und Metadatenspalten laden.

## Funktionen

- CSV-Import mit automatischer Erkennung typischer FTK-Listings
- Manuelles Verwalten sichtbarer Spalten über **Manage columns**
- Import von Tree-Text-Dateien und selbst kopierten Tree-Exports
- Ordnernavigation mit Detailansicht, Suche, Filtern und Sortierung
- Properties-Fenster per Doppelklick auf Dateien
- Kopieren von Ordner-Trees wahlweise nur mit Ordnern oder mit Dateien
- Vergleich zweier Imports mit Hervorhebung neuer, fehlender oder geänderter Elemente
- Export der aktuellen Ansicht als CSV

## Projektstruktur

```text
CsvFileBrowser/
├─ file_browser.pyw              # Windows/Tk launcher
├─ CsvFileBrowser.spec           # PyInstaller build config
├─ csv_file_browser/
│  ├─ app.py                     # Hauptfenster und UI-Workflow
│  ├─ dialogs.py                 # Import-, Filter- und Compare-Dialoge
│  ├─ icons.py                   # Icon-Laden und kleine generierte Icons
│  ├─ models.py                  # Konstanten und Dataclasses
│  ├─ parsing.py                 # CSV-/Tree-Import und Erkennung
│  └─ utils.py                   # Pfad-, Größen- und Filter-Helfer
├─ icons/                        # UI-Icons
├─ README.md
├─ LICENSE
└─ requirements.txt
```

## Starten

```powershell
python file_browser.pyw
```

Alternativ als Modul:

```powershell
python -m csv_file_browser
```

## Abhängigkeiten

Die App nutzt Python/Tkinter. `Pillow` ist empfohlen, damit PNG-Icons sauber geladen und skaliert werden können.

```powershell
pip install -r requirements.txt
```

## Build

Für einen Windows-Build ist eine PyInstaller-Spec enthalten:

```powershell
pyinstaller CsvFileBrowser.spec
```

Das Icon-Verzeichnis wird über die Spec als Datenquelle eingebunden.
