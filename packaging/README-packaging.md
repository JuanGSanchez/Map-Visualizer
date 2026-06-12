# MapVisualizer — Packaging Guide

This directory contains the build configuration to produce a self-contained, single-directory
Windows (and optionally macOS/Linux) executable of the MapVisualizer GUI application.

---

## Quick start

### Windows (recommended)

```bat
:: From the repo root:
packaging\build_windows.bat
```

Or, using the Python driver directly (cross-platform):

```bash
# From the repo root:
py -3.13 packaging/build.py
```

### macOS / Linux

```bash
# From the repo root:
bash packaging/build_posix.sh
```

---

## Requirements

Install into Python **3.13** before building:

```bash
py -3.13 -m pip install pyinstaller~=6.20.0 PySide6~=6.11.1 \
    "matplotlib~=3.11.0" "numpy~=2.4" Pillow
```

> **Why Python 3.13?**  The build scripts all use `py -3.13` / `python3.13` explicitly.  Bare
> `python` on this machine may resolve to 3.12.  Always use the versioned launcher so the
> interpreter and the installed packages match.

---

## Output layout

After a successful build:

```
packaging/
  bin/
    MapVisualizer/          <- one-dir bundle (distribute this folder)
      MapVisualizer.exe     <- main executable (Windows)
      _internal/            <- Python runtime, Qt libs, matplotlib data, etc.
        mpl-data/           <- matplotlib fonts, colormaps, stylelib (auto-collected)
        PySide6/            <- Qt plugins, translations, platform drivers
        ...
  work/                     <- PyInstaller build cache (safe to delete; gitignored)
```

Total bundle size is typically 200–350 MB (PySide6 + matplotlib + numpy dominate).

---

## Entry point

| Script | Python entry point | Windowed? |
|--------|--------------------|-----------|
| `MapVisualizer.exe` | `map_visualizer.gui.app:main` | Yes (no console window) |

The GUI entry point (`map-visualizer-gui`) is also declared in `pyproject.toml` as a
`[project.gui-scripts]` endpoint so the app can be launched via `map-visualizer-gui` when
installed from source.

The access-layer stack (`map-visualizer-api`, `map-visualizer-mcp`) is **not** bundled here
— it is intended to be run from a Python environment, not as a frozen executable.

---

## Bundling notes: matplotlib, numpy, PySide6

### PyInstaller 6.20 built-in hooks

PyInstaller 6.20 ships built-in hooks for all three major dependencies:

- **matplotlib**: the hook auto-collects `mpl-data` (fonts, colormaps, style sheets).
  No manual `collect_data_files('matplotlib')` call is needed.
- **numpy**: the hook collects the native C extensions and DLLs automatically.
- **PySide6**: the hook collects Qt plugins (platforms, imageformats, styles),
  translations, and the Qt shared libraries.

### Qt backend used

The GUI uses `FigureCanvasQTAgg` (matplotlib's Qt/Agg backend) bound to PySide6.
`QT_API=PySide6` is set in `map_visualizer/gui/app.py` before any matplotlib import so
auto-detection always picks PySide6.  `backend_qtagg` is listed as a hidden import in the
spec to ensure it is always collected.

### Excluded backends / toolkits

The following are explicitly excluded to keep the bundle lean:

- `tkinter`, `matplotlib.backends.backend_tkagg` — the old Tkinter UI is replaced by PySide6.
- `wx`, `gtk`, `PyQt5`, `PyQt6`, `PySide2` — unused toolkits.

The PySide6 / `backend_qtagg` path is **not** excluded.

### Resource paths

All asset lookups inside the app go through `map_visualizer.resources.resource_path`, which
uses `sys._MEIPASS` when running from a frozen bundle (fixes defect R-1 from the original
`os.getcwd()` approach).  `Logo MVis.png` is bundled into the one-dir root via the `datas`
entry in the spec.

### Icon

`Logo MVis.ico` is generated from `Logo MVis.png` by `packaging/scripts/png_to_ico.py`
(requires Pillow).  The build scripts run this automatically if the `.ico` is absent.
The `.ico` is **gitignored** — regenerate it at any time by running:

```bash
py -3.13 packaging/scripts/png_to_ico.py
```

---

## License notices (distribution requirements)

| Component | License | Requirement |
|-----------|---------|-------------|
| **PySide6** | LGPLv3 | You must allow end-users to relink against a modified version of Qt.  In practice: include the PySide6/Qt DLLs (already in the bundle) and note the LGPL in your distribution. |
| **matplotlib** | PSF / matplotlib License (BSD-compatible) | Retain the copyright notice. |
| **numpy** | BSD 3-Clause | Retain the copyright notice. |
| **MapVisualizer** | GPL-3.0-or-later | Source code must be made available to recipients. |

Full license texts are in the respective packages' `dist-info` directories inside the bundle
and in the upstream repositories.

---

## Spec file details

`packaging/MapVisualizer.spec`:

- **Mode**: one-directory (`COLLECT`; not `--onefile`).
- **SPECPATH**: PyInstaller sets this to `packaging/`.  `REPO_ROOT = Path(SPECPATH).parent`
  resolves all paths from the repository root — no hardcoded absolute paths.
- **`console=False`**: no console window on Windows (equivalent to `.pyw` launch).
- **`icon`**: `Logo MVis.ico` (Windows; on macOS pass a `.icns` manually if needed).

---

## Rebuilding / cleaning

```bash
# Python cross-platform driver with optional clean:
py -3.13 packaging/build.py --clean

# Or manually delete artefacts:
# Windows:  rmdir /s /q packaging\bin packaging\work
# POSIX:    rm -rf packaging/bin packaging/work
```
