# -*- mode: python ; coding: utf-8 -*-
# =============================================================================
# MapVisualizer.spec  —  PyInstaller 6.20 build spec
# =============================================================================
#
# One-directory (onedir) mode.  Entry point: map_visualizer.gui.app:main
# App name: MapVisualizer
# Toolkit: PySide6 6.11.x + matplotlib 3.11 (Qt/Agg backends) + numpy 2.4
#
# Build command (Windows, from the REPO ROOT):
#   py -3.13 -m PyInstaller packaging/MapVisualizer.spec --noconfirm \
#       --distpath packaging/bin --workpath packaging/work --log-level WARN
#
# SPECPATH is set by PyInstaller to the directory containing this spec file
# (i.e. <repo>/packaging/).  All paths are resolved from REPO_ROOT.
#
# Built-in hooks used (PyInstaller 6.20):
#   - matplotlib  : auto-collects mpl-data (fonts, colormaps, stylelib, etc.)
#   - numpy       : collects native extensions
#   - PySide6     : collects Qt plugins, translations, and Qt libraries
# No manual collect_data_files() calls are needed for these three packages.
# =============================================================================

from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve paths relative to the repo root (parent of the spec dir).
# ---------------------------------------------------------------------------
REPO_ROOT = str(Path(SPECPATH).parent)

# ---------------------------------------------------------------------------
# Datas: bundle the app icon (resolved at runtime via resources.resource_path).
# The example .txt/.dat demo grids are NOT bundled — runtime-only input files.
# ---------------------------------------------------------------------------
added_datas = [
    # (source, dest-in-bundle)  —  forward-slash paths required on all platforms
    (REPO_ROOT + "/Logo MVis.png", "."),
]

# ---------------------------------------------------------------------------
# Excludes: trim unused GUI toolkits / backends to keep the bundle lean.
# We use PySide6 + backend_qtagg exclusively; strip Tk, wx, GTK, and old Qt.
# Do NOT exclude backend_qtagg or any PySide6 module.
# ---------------------------------------------------------------------------
excluded_modules = [
    "tkinter",
    "matplotlib.backends.backend_tkagg",
    "matplotlib.backends.backend_wx",
    "matplotlib.backends.backend_gtk3agg",
    "matplotlib.backends.backend_gtk3cairo",
    "matplotlib.backends.backend_gtk4agg",
    "matplotlib.backends.backend_gtk4cairo",
    "wx",
    "gtk",
    "PyQt5",
    "PyQt6",
    "PySide2",
]

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    # Entry-point shim: PyInstaller needs a __main__ module.
    # We target the package entry point directly.
    [REPO_ROOT + "/map_visualizer/gui/app.py"],
    pathex=[REPO_ROOT],
    binaries=[],
    datas=added_datas,
    hiddenimports=[
        # Ensure the Qt AGG backend is always collected even if auto-detection
        # misses it on some platforms.
        "matplotlib.backends.backend_qtagg",
        # map_visualizer sub-packages (discovered at runtime via __init__ imports,
        # but listed explicitly for safety).
        "map_visualizer",
        "map_visualizer.core",
        "map_visualizer.enums",
        "map_visualizer.exceptions",
        "map_visualizer.resources",
        "map_visualizer.gui",
        "map_visualizer.gui.app",
        "map_visualizer.gui.main_window",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excluded_modules,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,     # onedir mode: binaries stay beside the exe
    name="MapVisualizer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,             # no console window (GUI app)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Windows application icon (.ico required on Windows)
    icon=REPO_ROOT + "/Logo MVis.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="MapVisualizer",
)
