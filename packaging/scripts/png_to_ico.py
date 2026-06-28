"""
packaging/scripts/png_to_ico.py
================================
Convert a PNG image to a multi-resolution Windows ICO file using Pillow.

Usage (standalone):
    py -3.13 packaging/scripts/png_to_ico.py [SRC_PNG] [DST_ICO]

Defaults:
    SRC_PNG  = <repo root>/Logo MVis.png
    DST_ICO  = <repo root>/Logo MVis.ico

The build scripts (build_windows.bat / build.py) invoke this script
automatically when Logo MVis.ico is absent.

Sizes bundled into the ICO (standard Windows set):
    16x16, 24x24, 32x32, 48x48, 64x64, 128x128, 256x256
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow is required.  Install with:  py -3.13 -m pip install Pillow")
    sys.exit(1)

# Standard multi-resolution sizes for a Windows .ico
ICO_SIZES = [
    (16, 16),
    (24, 24),
    (32, 32),
    (48, 48),
    (64, 64),
    (128, 128),
    (256, 256),
]

# Repo root is two levels up from this script (packaging/scripts/ -> repo root)
_SCRIPT_DIR = Path(__file__).parent
_REPO_ROOT = _SCRIPT_DIR.parent.parent

_DEFAULT_SRC = _REPO_ROOT / "Logo MVis.png"
_DEFAULT_DST = _REPO_ROOT / "Logo MVis.ico"


def png_to_ico(src: Path, dst: Path) -> None:
    """Convert *src* PNG to a multi-resolution ICO at *dst*."""
    if not src.exists():
        print(f"ERROR: source PNG not found: {src}")
        sys.exit(1)

    img = Image.open(src).convert("RGBA")

    # Build resized copies for each size
    frames: list[Image.Image] = []
    for size in ICO_SIZES:
        frames.append(img.resize(size, Image.LANCZOS))

    # Save the smallest frame as the primary image; sizes= embeds all
    frames[0].save(
        dst,
        format="ICO",
        sizes=ICO_SIZES,
        append_images=frames[1:],
    )
    print(f"ICO written: {dst}  ({len(frames)} sizes: {', '.join(f'{w}x{h}' for w, h in ICO_SIZES)})")


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else _DEFAULT_SRC
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else _DEFAULT_DST
    png_to_ico(src, dst)


if __name__ == "__main__":
    main()
