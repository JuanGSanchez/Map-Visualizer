#!/usr/bin/env bash
# packaging/build_posix.sh
# ========================
# Build MapVisualizer on macOS or Linux using Python 3.13 + PyInstaller 6.20.
#
# Run from the REPO ROOT:
#   bash packaging/build_posix.sh [--clean]
#
# The script:
#   1. Generates Logo MVis.ico from Logo MVis.png (if absent) via Pillow.
#   2. Runs PyInstaller against packaging/MapVisualizer.spec.
#   3. Places the one-dir bundle in packaging/bin/MapVisualizer/.
#
# Requirements:
#   python3.13 -m pip install pyinstaller~=6.20.0 PySide6~=6.11.1 \
#       "matplotlib~=3.11.0" "numpy~=2.4" Pillow
#
# Note: on macOS, UPX is optional; remove --upx-dir or install it via Homebrew.
# Note: on Linux, PySide6 wheels require glibc >= 2.28 (Debian 10+ / Ubuntu 18.04+).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PACKAGING_DIR="$REPO_ROOT/packaging"
SPEC_FILE="$PACKAGING_DIR/MapVisualizer.spec"
DIST_DIR="$PACKAGING_DIR/bin"
WORK_DIR="$PACKAGING_DIR/work"
ICO_FILE="$REPO_ROOT/Logo MVis.ico"
PNG_FILE="$REPO_ROOT/Logo MVis.png"

# ---------------------------------------------------------------------------
# Optional --clean flag
# ---------------------------------------------------------------------------
if [[ "${1:-}" == "--clean" ]]; then
    echo "[build] Cleaning packaging/bin and packaging/work ..."
    rm -rf "$DIST_DIR" "$WORK_DIR"
fi

# ---------------------------------------------------------------------------
# Step 1 — Generate icon if absent
# ---------------------------------------------------------------------------
if [[ ! -f "$ICO_FILE" ]]; then
    echo "[build] Logo MVis.ico not found — generating from Logo MVis.png ..."
    python3.13 "$PACKAGING_DIR/scripts/png_to_ico.py" "$PNG_FILE" "$ICO_FILE"
fi

# ---------------------------------------------------------------------------
# Step 2 — Run PyInstaller
# ---------------------------------------------------------------------------
cd "$REPO_ROOT"
echo "[build] Running PyInstaller 6.20 with Python 3.13 ..."
python3.13 -m PyInstaller "$SPEC_FILE" \
    --noconfirm \
    --distpath "$DIST_DIR" \
    --workpath "$WORK_DIR" \
    --log-level WARN

# ---------------------------------------------------------------------------
# Step 3 — Report result
# ---------------------------------------------------------------------------
EXE_DIR="$DIST_DIR/MapVisualizer"
echo ""
echo "[build] SUCCESS"
echo "[build]   Bundle dir: $EXE_DIR"
if command -v du &>/dev/null; then
    SIZE=$(du -sh "$EXE_DIR" 2>/dev/null | cut -f1)
    echo "[build]   Size: $SIZE"
fi
