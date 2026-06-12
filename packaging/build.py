"""
packaging/build.py
==================
Cross-platform Python build driver for MapVisualizer.

Runs from the REPO ROOT:
    py -3.13 packaging/build.py [--clean]

Steps:
  1. If ``Logo MVis.ico`` is absent, generate it via packaging/scripts/png_to_ico.py.
  2. Run PyInstaller with the spec, distpath, and workpath set to the
     packaging/ sub-directories so the output never pollutes the repo root.
  3. Report the produced exe and total bundle size.

Requirements:
  py -3.13 -m pip install pyinstaller~=6.20.0 PySide6~=6.11.1 \
      matplotlib~=3.11.0 numpy~=2.4 Pillow
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths (all resolved relative to this script's parent = packaging/)
# ---------------------------------------------------------------------------
PACKAGING_DIR = Path(__file__).parent
REPO_ROOT = PACKAGING_DIR.parent

SPEC_FILE = PACKAGING_DIR / "MapVisualizer.spec"
DIST_DIR = PACKAGING_DIR / "bin"
WORK_DIR = PACKAGING_DIR / "work"

PNG_ICON = REPO_ROOT / "Logo MVis.png"
ICO_ICON = REPO_ROOT / "Logo MVis.ico"
PNG_TO_ICO_SCRIPT = PACKAGING_DIR / "scripts" / "png_to_ico.py"


def _ensure_ico() -> None:
    """Generate the .ico from the .png if it is absent."""
    if ICO_ICON.exists():
        return
    print(f"[build] Logo MVis.ico not found — generating from {PNG_ICON.name} ...")
    result = subprocess.run(
        [sys.executable, str(PNG_TO_ICO_SCRIPT), str(PNG_ICON), str(ICO_ICON)],
        check=False,
    )
    if result.returncode != 0:
        print("[build] ERROR: png_to_ico.py failed; cannot continue without icon.")
        sys.exit(1)


def _clean() -> None:
    """Remove prior build artefacts (bin/ and work/)."""
    for d in (DIST_DIR, WORK_DIR):
        if d.exists():
            print(f"[build] Removing {d} ...")
            shutil.rmtree(d)


def _dir_size_mb(path: Path) -> float:
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return total / (1024 * 1024)


def build(clean: bool = False) -> int:
    """Run the full build sequence.  Returns PyInstaller exit code."""
    if clean:
        _clean()

    _ensure_ico()

    # Change to repo root so relative imports in the spec resolve correctly.
    os.chdir(REPO_ROOT)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        str(SPEC_FILE),
        "--noconfirm",
        "--distpath", str(DIST_DIR),
        "--workpath", str(WORK_DIR),
        "--log-level", "WARN",
    ]

    print("[build] Running PyInstaller ...")
    print("[build]   " + " ".join(cmd))
    result = subprocess.run(cmd, check=False)

    if result.returncode == 0:
        exe_dir = DIST_DIR / "MapVisualizer"
        exe_path = exe_dir / "MapVisualizer.exe"
        if exe_path.exists():
            size_mb = _dir_size_mb(exe_dir)
            print(f"\n[build] SUCCESS")
            print(f"[build]   exe  : {exe_path}")
            print(f"[build]   size : {size_mb:.1f} MB (one-dir bundle)")
        else:
            print(f"\n[build] WARNING: PyInstaller exited 0 but exe not found at {exe_path}")
    else:
        print(f"\n[build] FAILED: PyInstaller exited {result.returncode}")

    return result.returncode


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build MapVisualizer Windows/macOS/Linux executable."
    )
    parser.add_argument(
        "--clean", action="store_true",
        help="Remove packaging/bin and packaging/work before building."
    )
    args = parser.parse_args()
    sys.exit(build(clean=args.clean))


if __name__ == "__main__":
    main()
