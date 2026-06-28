"""
Tests for the Map-Visualizer PySide6 GUI — the centralized widget-info popup
(SPEC-01), keyboard/accessibility affordance (SPEC-02), and accessibility
(SPEC-23).

The GUI layer is omitted from the coverage gate (display boundary), but these
tests assert the *acceptance criteria* that make the centralized-info pattern
correct:

* exactly ONE info surface + ONE registry + ONE theming point (no bespoke
  popup class, no inline tooltip literals),
* every registered widget's tooltip / accessible description / What's-This all
  resolve to the single registry,
* every interactive widget carries a non-empty registry-backed info key and a
  non-empty accessible name.

GUI widget tests run under the Qt ``offscreen`` platform so they need no display.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import numpy as np
import pytest

# Force a headless Qt platform BEFORE importing any Qt module.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from map_visualizer.gui import info, theme

_GUI_DIR = Path(__file__).resolve().parent.parent / "map_visualizer" / "gui"


# ===========================================================================
# SPEC-01 — single registry (no inline literals, no bespoke popup class)
# ===========================================================================

class TestRegistry:
    def test_registry_nonempty(self):
        assert len(info.HELP) > 0

    def test_all_registry_values_nonempty(self):
        for key, text in info.HELP.items():
            assert isinstance(text, str) and text.strip(), key

    def test_info_text_raises_on_missing_key(self):
        with pytest.raises(KeyError):
            info.info_text("no_such_key")

    def test_mode_info_text_appends_state_detail(self):
        base = info.info_text("mode")
        for mode, detail in info.MODE_DETAIL.items():
            assert info.mode_info_text(mode) == base + detail


class TestSourceHygiene:
    """Static guarantees scanned from the GUI source (SPEC-01 acceptance)."""

    def _gui_sources(self):
        return list(_GUI_DIR.glob("*.py"))

    def test_no_bespoke_popup_or_tooltip_class(self):
        pat = re.compile(r"class\s+\w*(Popup|Tooltip|ToolTip|Info)\b")
        for path in self._gui_sources():
            src = path.read_text(encoding="utf-8")
            assert not pat.search(src), f"bespoke info class in {path.name}"

    def test_no_tooltip_event_overrides(self):
        # No eventFilter / event() tooltip-handling overrides — Qt handles the
        # surface.  (Matches real defs, not docstring mentions.)
        bad = re.compile(r"def\s+(eventFilter|event)\s*\(")
        for path in self._gui_sources():
            src = path.read_text(encoding="utf-8")
            assert not bad.search(src), f"tooltip event override in {path.name}"

    def test_no_inline_settooltip_string_literal(self):
        # Every setToolTip call must go through register_info/update_info, never
        # an inline string literal (the one registry is the only source).
        literal = re.compile(r"\.setToolTip\(\s*[\"']")
        for path in self._gui_sources():
            src = path.read_text(encoding="utf-8")
            assert not literal.search(src), (
                f"inline setToolTip literal in {path.name}"
            )

    def test_single_qtooltip_qss_rule(self):
        # Exactly one QToolTip { ... } rule, emitted by the theme module; the
        # main window contains no scattered tooltip styling of its own.
        qss = theme.build_stylesheet(theme.LIGHT)
        assert qss.count("QToolTip {") == 1
        mw = (_GUI_DIR / "main_window.py").read_text(encoding="utf-8")
        assert "QToolTip {" not in mw


class TestThemeRestyle:
    def test_changing_theme_changes_every_tooltip_color(self):
        light = theme.build_stylesheet(theme.LIGHT)
        dark = theme.build_stylesheet(theme.DARK)
        assert theme.LIGHT.tooltip_bg in light
        assert theme.DARK.tooltip_bg in dark
        assert light != dark


# ===========================================================================
# Qt widget tests (offscreen) — registration, accessibility, dynamic text
# ===========================================================================

@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def window(qapp):
    # Each test gets a fresh window; reset the registration log first.
    info._REGISTERED.clear()
    from map_visualizer.gui.main_window import MainWindow
    w = MainWindow()
    yield w
    w.close()


class TestRegisterInfoHelper:
    def test_sets_tooltip_description_whatsthis_from_registry(self, qapp):
        from PySide6.QtWidgets import QPushButton
        btn = QPushButton()
        info.register_info(btn, "open_file")
        expected = info.info_text("open_file")
        assert btn.toolTip() == expected
        assert btn.accessibleDescription() == expected  # SPEC-02
        assert btn.whatsThis() == expected              # SPEC-02
        assert btn.accessibleName()                     # SPEC-23 (non-empty)

    def test_unknown_key_raises(self, qapp):
        from PySide6.QtWidgets import QPushButton
        with pytest.raises(KeyError):
            info.register_info(QPushButton(), "nope")


class TestWindowCoverage:
    """SPEC-01 coverage helper + SPEC-23 accessibility on the real window."""

    def _interactive(self, w):
        return [
            w._btn_open, w._btn_export, w._cb_mode, w._cb_cmap, w._cb_interp,
            w._ed_val_min, w._ed_val_max, w._ed_col_min, w._ed_col_max,
            w._cb_profile_axis, w._ed_profile_index,
        ]

    def test_every_interactive_widget_has_info(self, window):
        for wdg in self._interactive(window):
            assert wdg.accessibleDescription().strip(), wdg
            assert wdg.toolTip().strip(), wdg

    def test_every_interactive_widget_has_accessible_name(self, window):
        for wdg in self._interactive(window):
            assert wdg.accessibleName().strip(), wdg

    def test_registration_log_records_widgets(self, window):
        # register_info was used uniformly (coverage gap 3).
        assert len(info.registered_keys()) >= len(self._interactive(window))


class TestModeDispatch:
    @pytest.mark.parametrize(
        "mode_value",
        ["heatmap", "contour", "contourf", "surface3d", "histogram", "profile"],
    )
    def test_all_modes_redraw(self, window, mode_value):
        window._array = np.arange(1.0, 21.0).reshape(5, 4)
        from map_visualizer import array_stats
        window._stats = array_stats(window._array)
        window._reset_ranges_to_data()
        idx = window._cb_mode.findData(mode_value)
        assert idx >= 0
        window._cb_mode.setCurrentIndex(idx)
        window._redraw()  # must not raise

    def test_mode_change_updates_dynamic_info(self, window):
        idx = window._cb_mode.findData("histogram")
        window._cb_mode.setCurrentIndex(idx)
        assert "histogram" in window._cb_mode.toolTip().lower()


class TestExport:
    def test_export_writes_png(self, window, tmp_path, monkeypatch):
        window._array = np.arange(1.0, 13.0).reshape(3, 4)
        from map_visualizer import array_stats
        window._stats = array_stats(window._array)
        window._reset_ranges_to_data()

        out = tmp_path / "out.png"
        from PySide6.QtWidgets import QFileDialog
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName",
            staticmethod(lambda *a, **k: (str(out), "")),
        )
        window._export_image()
        assert out.exists()
        assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"

    def test_export_writes_svg(self, window, tmp_path, monkeypatch):
        window._array = np.arange(1.0, 13.0).reshape(3, 4)
        from map_visualizer import array_stats
        window._stats = array_stats(window._array)
        window._reset_ranges_to_data()

        out = tmp_path / "out.svg"
        from PySide6.QtWidgets import QFileDialog
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName",
            staticmethod(lambda *a, **k: (str(out), "")),
        )
        window._export_image()
        assert out.exists()
        assert out.read_bytes()[:5] == b"<?xml"
