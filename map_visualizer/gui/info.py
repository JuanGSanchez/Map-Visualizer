"""
Juan García Sánchez, 2023-2026
Map-Visualizer — the ONE centralized widget-info component (SPEC-01 / SPEC-02).

Design (reference-widget-popup.md, FF-Explorer pattern, with the mandated gap
fixes applied)
---------------------------------------------------------------------------
* **One info surface.**  Qt's framework-managed ``QToolTip`` singleton is the
  single info surface for the whole app.  No bespoke popup/tooltip/info class is
  authored anywhere (acceptance: grep finds zero ``class *Popup/*Tooltip/*Info``
  and zero tooltip ``eventFilter``/``QHelpEvent`` overrides).

* **One registry (gap 1 fixed).**  ALL info text lives in the module-level
  :data:`HELP` dict keyed by a stable widget id — there are NO inline string
  literals passed to ``setToolTip(...)`` in the GUI.  State-dependent text
  (e.g. per-mode help) is looked up from :data:`MODE_DETAIL`, mirroring the
  reference's ``_update_action_tooltip`` pattern.

* **One registration helper (gap 2 + 3 fixed).**  :func:`register_info` is the
  single call every interactive widget uses.  It sets the tooltip AND the
  accessible description AND What's-This from the same registry entry, so the
  info is reachable by hover, by keyboard focus / screen reader, and via the
  ``?`` / Shift+F1 What's-This affordance — not hover-only.

* **One theming point (gap 5 fixed).**  Styling lives only in
  :mod:`map_visualizer.gui.theme` (one ``QToolTip {}`` QSS rule); no per-widget
  ``setStyleSheet`` fights it.

* **Coverage (gap 3).**  :func:`registered_keys` records every registration so a
  test can assert every interactive widget carries a non-empty registry entry.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# THE registry — stable widget id -> info text.  No info text lives anywhere
# else in the GUI.  Rich text / word-wrap is left to Qt's tooltip surface
# (no manual "\n" carryover — reference gap 4).
# ---------------------------------------------------------------------------
HELP: dict[str, str] = {
    "open_file": (
        "Open a 2-D numeric grid file (.txt, .dat, or .csv). The column "
        "delimiter — whitespace, comma, or semicolon — is auto-detected."
    ),
    "export": (
        "Export the current view to an image file. The format (PNG, SVG, or "
        "PDF) is chosen from the file extension you pick."
    ),
    "mode": (
        "Visualization mode applied to the loaded grid. Heatmap, contour, "
        "filled contour, 3-D surface, histogram, or a row/column profile."
    ),
    "colormap": "Matplotlib colormap mapping data values to colours.",
    "interpolation": (
        "imshow interpolation between cells. Used in heatmap mode only."
    ),
    "value_min": "Lower data-value clamp. Values below it are pinned to it.",
    "value_max": "Upper data-value clamp. Values above it are pinned to it.",
    "value_reset": "Reset the value clamp to the full data range.",
    "color_min": "Lower colormap limit, independent of the data clamp.",
    "color_max": "Upper colormap limit, independent of the data clamp.",
    "color_reset": "Reset the colormap limits to the full data range.",
    "profile_axis": (
        "Plot a horizontal row slice or a vertical column slice of the grid."
    ),
    "profile_index": "0-based row or column index for the profile slice.",
    "fullscreen": "Toggle fullscreen display of the window (F11).",
    "whatsthis": (
        "Enter What's-This mode (Shift+F1), then click any control to read its "
        "help. The same help is available by hovering or by keyboard focus."
    ),
}

# ---------------------------------------------------------------------------
# State-driven supplementary text (looked up by widget state, not a constant) —
# mirrors the reference _update_action_tooltip / _HELP_ACTION_DETAIL pattern.
# ---------------------------------------------------------------------------
MODE_DETAIL: dict[str, str] = {
    "heatmap": " Current: 2-D imshow grid with a colorbar.",
    "contour": " Current: filled contour with a line overlay.",
    "contourf": " Current: filled contour (no line overlay).",
    "surface3d": " Current: 3-D surface plot.",
    "histogram": " Current: distribution histogram of all cell values.",
    "profile": " Current: 1-D line plot of a single row/column slice.",
    "profile_row": " Current: 1-D line plot of a single row slice.",
    "profile_col": " Current: 1-D line plot of a single column slice.",
}


def info_text(key: str) -> str:
    """Return the registry text for *key*, raising ``KeyError`` if missing."""
    text = HELP.get(key)
    if not text:
        raise KeyError(f"No info text registered for widget key {key!r}.")
    return text


def mode_info_text(mode: str) -> str:
    """Return the mode-selector help with the state-driven detail appended."""
    return info_text("mode") + MODE_DETAIL.get(mode, "")


# ---------------------------------------------------------------------------
# Registration — the ONE helper every interactive widget uses.
# ---------------------------------------------------------------------------

#: Records (widget_key) for every registration so a coverage test can assert
#: every interactive widget carries info.  Holds keys only (no widget refs) to
#: avoid keeping widgets alive.
_REGISTERED: list[str] = []


def register_info(widget, key: str) -> None:
    """Attach the single registry entry for *key* to *widget*.

    Sets, from the one registry entry:

    * the tooltip (hover surface — Qt's ``QToolTip`` singleton),
    * the accessible description (keyboard focus / screen readers — SPEC-02),
    * What's-This (the ``?`` / Shift+F1 affordance — SPEC-02).

    This is the only place ``setToolTip`` is called in the GUI; no inline string
    literal is ever passed to ``setToolTip`` (SPEC-01 acceptance).
    """
    text = info_text(key)
    widget.setToolTip(text)
    widget.setAccessibleDescription(text)
    widget.setWhatsThis(text)
    # SPEC-23: every interactive widget also exposes a non-empty accessible
    # NAME (a short label, distinct from the description) unless one is set.
    if not widget.accessibleName():
        widget.setAccessibleName(key.replace("_", " ").title())
    _REGISTERED.append(key)


def update_info(widget, text: str) -> None:
    """Update the live info text on *widget* (state-driven case, e.g. mode help).

    Sets tooltip + accessible description + What's-This to *text*, which the
    caller derives from the registry (e.g. via :func:`mode_info_text`).  Keeps
    the "one surface, registry-fed" contract for dynamic text.
    """
    widget.setToolTip(text)
    widget.setAccessibleDescription(text)
    widget.setWhatsThis(text)


def registered_keys() -> list[str]:
    """Return the list of widget keys registered so far (coverage helper)."""
    return list(_REGISTERED)
