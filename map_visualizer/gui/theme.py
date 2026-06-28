"""
Juan García Sánchez, 2023-2026
Map-Visualizer — GUI theme + the single tooltip-styling point (SPEC-01).

This module owns the ONE ``QToolTip { ... }`` QSS rule for the whole app, themed
from the active :class:`Theme` (light/dark).  Changing ``Theme.tooltip_bg`` /
``Theme.tooltip_text`` restyles every tooltip in the app with no other edit —
the "single theming point" mandated by reference-widget-popup.md §2.3.

No Qt import is needed here: ``build_stylesheet`` returns a plain QSS string the
GUI applies via ``QApplication.setStyleSheet`` / ``QWidget.setStyleSheet``.  That
keeps this module cheap to import (and unit-testable without a display).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    """A GUI colour theme.

    Only the fields the centralized tooltip surface needs are modelled here;
    the dataclass can grow without touching call sites.
    """

    name: str
    tooltip_bg: str
    tooltip_text: str
    border: str


#: Default light theme.
LIGHT = Theme(
    name="light",
    tooltip_bg="#f7f7f7",
    tooltip_text="#1e1e1e",
    border="#9a9a9a",
)

#: Default dark theme.
DARK = Theme(
    name="dark",
    tooltip_bg="#2b2b2b",
    tooltip_text="#e8e8e8",
    border="#555555",
)

#: The active default theme used when the GUI starts.
DEFAULT_THEME = LIGHT


def build_stylesheet(theme: Theme) -> str:
    """Return the application QSS for *theme*.

    Emits EXACTLY ONE ``QToolTip { ... }`` rule (SPEC-01 acceptance): the whole
    app's tooltip surface is styled here and only here.  Word-wrapping/rich-text
    rendering is left to Qt's tooltip surface (reference gap 4).
    """
    return (
        "QToolTip {\n"
        f"    background-color: {theme.tooltip_bg};\n"
        f"    color: {theme.tooltip_text};\n"
        f"    border: 1px solid {theme.border};\n"
        "    padding: 3px 6px;\n"
        "}\n"
    )
