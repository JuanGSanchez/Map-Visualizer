@echo off
:: packaging\build_windows.bat
:: ===========================
:: Build MapVisualizer.exe on Windows using Python 3.13 + PyInstaller 6.20.
::
:: Run from the REPO ROOT:
::   packaging\build_windows.bat
::
:: The script:
::   1. Generates Logo MVis.ico from Logo MVis.png (if absent) via Pillow.
::   2. Runs PyInstaller against packaging/MapVisualizer.spec.
::   3. Places the one-dir bundle in packaging/bin/MapVisualizer/.
::
:: Requirements (install into Python 3.13):
::   py -3.13 -m pip install pyinstaller~=6.20.0 PySide6~=6.11.1 ^
::       matplotlib~=3.11.0 "numpy~=2.4" Pillow
::
:: Use the "py" launcher so this targets 3.13 regardless of PATH order.

setlocal EnableDelayedExpansion

:: ---------------------------------------------------------------------------
:: Step 1 — Generate icon if absent
:: ---------------------------------------------------------------------------
if not exist "Logo MVis.ico" (
    echo [build] Logo MVis.ico not found -- generating from Logo MVis.png ...
    py -3.13 packaging\scripts\png_to_ico.py
    if !errorlevel! neq 0 (
        echo [build] ERROR: png_to_ico.py failed.
        exit /b 1
    )
)

:: ---------------------------------------------------------------------------
:: Step 2 — Run PyInstaller (forward-slash paths; --noconfirm avoids prompts)
:: ---------------------------------------------------------------------------
echo [build] Running PyInstaller 6.20 with Python 3.13 ...
py -3.13 -m PyInstaller packaging/MapVisualizer.spec ^
    --noconfirm ^
    --distpath packaging/bin ^
    --workpath packaging/work ^
    --log-level WARN

if !errorlevel! neq 0 (
    echo [build] FAILED: PyInstaller exited with error !errorlevel!
    exit /b !errorlevel!
)

:: ---------------------------------------------------------------------------
:: Step 3 — Report result
:: ---------------------------------------------------------------------------
echo.
echo [build] SUCCESS
echo [build]   Executable: packaging\bin\MapVisualizer\MapVisualizer.exe
echo [build]   Bundle dir: packaging\bin\MapVisualizer\

endlocal
exit /b 0
