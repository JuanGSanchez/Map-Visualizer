#!/usr/bin/env python3
"""PreToolUse hook -- guard against a Tkinter / legacy-UI regression.

Enforces the no-Tkinter-regression invariant (CLAUDE.md / MV-B09): the legacy flat
Tkinter app (MVis_UI.pyw, MVis_utils.py) is dead and superseded by the PySide6 package;
it must not be re-created or re-imported, and the PyInstaller excludes for Tk stay.

Fires on Edit|Write. Reads the PreToolUse JSON on stdin; blocks (exit 2) when a write
would (re)create a legacy file, import the legacy modules, import tkinter into the
package, or remove a Tk exclude line from the PyInstaller spec. Fast: pure-stdlib.

## Principles Applied
P2 Full Determinism -- regex/path checks are deterministic; identical input -> identical exit.
P4 Consistency -- ensures the no-Tkinter/legacy-UI rule is consistently enforced across all
  edits; the PyInstaller excludes list stays intact and the UI is always the PySide6 package.
P8 Principles Inheritance -- harness-level enforcement of the repo's no-Tkinter-regression
  canonical rule (CLAUDE.md invariant 7 / python-repo-conventions.md D8).
P11 Programmatic Determinism -- this hook IS the deterministic harness; Tkinter regression
  is blocked by PreToolUse before any write, not left to LLM judgement.
"""
import json
import re
import sys

LEGACY_FILES = ("mvis_ui.pyw", "mvis_utils.py")
LEGACY_IMPORT = re.compile(r"(?m)^\s*(?:import|from)\s+MVis_(?:UI|utils)\b")
TK_IMPORT = re.compile(
    r"(?m)^\s*(?:import\s+tkinter\b|from\s+tkinter\b"
    r"|import\s+matplotlib\.backends\.backend_tkagg\b)"
)


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    ti = data.get("tool_input", {}) or {}
    path = (ti.get("file_path") or "").replace("\\", "/")
    name = path.lower().rsplit("/", 1)[-1]
    content = ti.get("content") or ti.get("new_string") or ""

    if name in LEGACY_FILES:
        sys.stderr.write(
            f"BLOCKED (Tkinter regression): {path} re-creates a retired legacy "
            "Tkinter file. The sole desktop entry point is map_visualizer.gui.app "
            "(PySide6); the legacy MVis_UI.pyw / MVis_utils.py are removed (MV-B09).\n"
        )
        return 2

    is_pkg = "/map_visualizer/" in path or path.endswith("map_visualizer.py") \
        or "/tests/" in path
    if (LEGACY_IMPORT.search(content) or TK_IMPORT.search(content)) and is_pkg:
        sys.stderr.write(
            f"BLOCKED (Tkinter regression): {path} would import a retired Tkinter "
            "module (MVis_UI/MVis_utils or tkinter/backend_tkagg). The UI is PySide6 "
            "under map_visualizer/gui/; no Tk in the package. See CLAUDE.md.\n"
        )
        return 2

    # Removing a Tk exclude from the PyInstaller spec (Edit replacing it with nothing).
    if path.endswith("packaging/MapVisualizer.spec"):
        old = ti.get("old_string") or ""
        new = ti.get("new_string") or ""
        for tok in ('"tkinter"', '"matplotlib.backends.backend_tkagg"'):
            if tok in old and tok not in new:
                sys.stderr.write(
                    f"BLOCKED (Tkinter regression): this edit removes the {tok} "
                    "exclude from the PyInstaller spec. Tk excludes stay effective "
                    "(CLAUDE.md invariant 7); add missing excludes, never drop one.\n"
                )
                return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
