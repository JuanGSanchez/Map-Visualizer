#!/usr/bin/env python3
"""PreToolUse hook — block a pyplot/Qt/Tk import landing in the HEADLESS render core.

Enforces CLAUDE.md invariant 1: map_visualizer/core.py and enums.py import ONLY the
Agg matplotlib set; never matplotlib.pyplot, never Qt/Tk/any interactive backend. A
single such import silently breaks the PyInstaller bundle and the headless server.

Fires on Edit|Write. Reads the harness PreToolUse JSON on stdin; inspects the new
content destined for a core file; exits 2 (blocking, message on stderr) if a forbidden
import would be written. Fast: pure-stdlib regex, no imports of the repo.
"""
import json
import re
import sys

# Files that MUST stay headless-pure (matched by suffix, OS-separator agnostic).
CORE_SUFFIXES = ("map_visualizer/core.py", "map_visualizer\\core.py",
                 "map_visualizer/enums.py", "map_visualizer\\enums.py")

# Forbidden imports in the core. backend_agg is the ALLOWED Agg backend, so the
# pattern targets pyplot, Qt/Tk bindings, and interactive matplotlib backends only.
FORBIDDEN = re.compile(
    r"(?m)^\s*(?:import\s+matplotlib\.pyplot"
    r"|from\s+matplotlib\s+import\s+pyplot"
    r"|import\s+matplotlib\.pyplot\s+as"
    r"|import\s+(?:PySide6|PySide2|PyQt5|PyQt6|tkinter)\b"
    r"|from\s+(?:PySide6|PySide2|PyQt5|PyQt6|tkinter)\b"
    r"|from\s+matplotlib\.backends\s+import\s+backend_(?:qt|tk)"
    r"|import\s+matplotlib\.backends\.backend_(?:qt|tk))"
)


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0  # malformed payload — do not block, fail open
    ti = data.get("tool_input", {}) or {}
    path = (ti.get("file_path") or "").replace("\\", "/")
    if not path.endswith(("map_visualizer/core.py", "map_visualizer/enums.py")):
        return 0
    # Content to be written: Write -> 'content'; Edit -> 'new_string'.
    content = ti.get("content") or ti.get("new_string") or ""
    m = FORBIDDEN.search(content)
    if m:
        sys.stderr.write(
            "BLOCKED (headless-core invariant): a forbidden import "
            f"`{m.group(0).strip()}` would be written to {path}. "
            "The render core is AGG-ONLY — never matplotlib.pyplot, never Qt/Tk. "
            "Use Figure.colorbar (not pyplot.colorbar), build norms via "
            "matplotlib.colors, export via FigureCanvasAgg/savefig. Put all Qt "
            "code under map_visualizer/gui/. See CLAUDE.md invariant 1.\n"
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
