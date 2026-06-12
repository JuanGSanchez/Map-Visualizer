"""
Juan García Sánchez, 2023-2026
Map-Visualizer — PySide6 main window (workstream b).

Layout overview
---------------
QMainWindow
  central widget: QSplitter (Horizontal)
    left pane: PlotPane  (canvas + matplotlib toolbar, QVBoxLayout)
    right pane: QScrollArea  ->  controls widget  (QFormLayout sections)
  status bar: pixel readout  (X / Y / value labels)

The splitter gives the user free control over the canvas/controls balance and
resizes cleanly without any pixel-arithmetic or magic offset constants.

Design notes
------------
* matplotlib is embedded interactively via ``FigureCanvasQTAgg`` — the canvas
  IS a QWidget and is placed directly inside a Qt layout.
* The same drawing helpers (``draw_heatmap``, ``draw_contour``, etc.) that the
  headless ``render()`` call uses are called here on the live QTAgg figure —
  single source of truth for drawing logic.
* No ``matplotlib.pyplot`` import anywhere in this module.
* All asset paths go through ``map_visualizer.resources.resource_path`` — no
  ``os.getcwd()``.
* Core exceptions (``GridLoadError``, ``GridValidationError``, ``RenderError``,
  ``InvalidParameterError``) are caught and shown via ``QMessageBox`` — no bare
  ``except: pass``.
"""

from __future__ import annotations

import logging
import os

# ---------------------------------------------------------------------------
# Bind matplotlib's Qt backend to PySide6 BEFORE any matplotlib import.
# Must be set before matplotlib.backends is imported.
# ---------------------------------------------------------------------------
os.environ.setdefault("QT_API", "PySide6")

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT
from matplotlib.figure import Figure

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QDoubleValidator, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from map_visualizer.core import (
    apply_value_range,
    array_stats,
    draw_contour,
    draw_heatmap,
    draw_histogram,
    draw_profile,
    list_colormaps,
    list_interpolations,
)
from map_visualizer.enums import RenderMode
from map_visualizer.exceptions import (
    GridLoadError,
    GridValidationError,
    InvalidParameterError,
    RenderError,
)
from map_visualizer.resources import resource_path

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_APP_TITLE = "Map-Visualizer"
_VERSION = "2.0"
_AUTHOR = "Juan García Sánchez"
_LICENSE = "GPLv3"

_SLIDER_STEPS = 1000  # resolution of the value/color-range sliders
_DEFAULT_CMAP = "viridis"
_DEFAULT_INTERP = "nearest"


# ---------------------------------------------------------------------------
# Helper: matplotlib canvas widget
# ---------------------------------------------------------------------------

class _MplCanvas(FigureCanvasQTAgg):
    """A ``FigureCanvasQTAgg`` pre-configured with one subplot.

    ``FigureCanvasQTAgg`` is itself a ``QWidget``.  Embed it directly in any
    Qt layout.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        self.fig = Figure(facecolor="white", tight_layout=True)
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.updateGeometry()

    def clear_axes(self) -> None:
        """Remove all axes artists and re-create a fresh subplot."""
        self.fig.clear()
        self.ax = self.fig.add_subplot(111)


# ---------------------------------------------------------------------------
# Helper: double-precision line-edit with validator
# ---------------------------------------------------------------------------

class _FloatEdit(QLineEdit):
    """A ``QLineEdit`` that accepts only finite doubles."""

    def __init__(self, value: float = 0.0, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        validator = QDoubleValidator()
        validator.setNotation(QDoubleValidator.Notation.ScientificNotation)
        self.setValidator(validator)
        self.setText(f"{value:.6g}")
        self.setMinimumWidth(90)

    def float_value(self) -> float | None:
        """Return the current value as float, or ``None`` if the text is invalid."""
        try:
            return float(self.text())
        except ValueError:
            return None


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    """Map-Visualizer PySide6 main window.

    Structured as:
    - A ``QSplitter`` splits the canvas pane from the scrollable controls
      panel, so the user can resize freely.
    - Controls are grouped in ``QFormLayout`` sections inside a ``QScrollArea``
      so the panel is usable at any window height.
    - Mode changes, parameter changes all redraw via ``_redraw()``, which calls
      the appropriate core drawing helper directly on the live ``_MplCanvas``.
    """

    def __init__(self) -> None:
        super().__init__()

        # ------------------------------------------------------------------
        # Application state
        # ------------------------------------------------------------------
        self._array: np.ndarray | None = None
        self._stats: dict | None = None
        # Value-range and color-range are stored as real-data coordinates
        # (NOT scaled by ref_exp).  They are updated when an array is loaded.
        self._val_min: float = 0.0
        self._val_max: float = 1.0
        self._col_min: float = 0.0
        self._col_max: float = 1.0
        self._data_min: float = 0.0   # array nanmin (reference limits)
        self._data_max: float = 1.0   # array nanmax

        self._is_fullscreen: bool = False

        # ------------------------------------------------------------------
        # Window chrome
        # ------------------------------------------------------------------
        self.setWindowTitle(_APP_TITLE)
        self.resize(1100, 700)

        icon_path = resource_path("Logo MVis.png")
        if os.path.isfile(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # ------------------------------------------------------------------
        # Central layout: splitter (canvas | controls)
        # ------------------------------------------------------------------
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(self._splitter)

        # Left pane — plot area
        self._plot_pane = self._build_plot_pane()
        self._splitter.addWidget(self._plot_pane)

        # Right pane — scrollable controls
        self._controls_scroll = self._build_controls_panel()
        self._splitter.addWidget(self._controls_scroll)

        # Give the canvas the majority of the space initially
        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([800, 300])

        # ------------------------------------------------------------------
        # Status bar — pixel readout
        # ------------------------------------------------------------------
        self._sb_x = QLabel("X: —")
        self._sb_y = QLabel("Y: —")
        self._sb_val = QLabel("val: —")
        self._sb_file = QLabel("No file loaded")

        sb = QStatusBar()
        sb.addWidget(self._sb_file, stretch=1)
        sb.addPermanentWidget(self._sb_x)
        sb.addPermanentWidget(self._sb_y)
        sb.addPermanentWidget(self._sb_val)
        self.setStatusBar(sb)

        # ------------------------------------------------------------------
        # Menu bar
        # ------------------------------------------------------------------
        self._build_menu()

        # ------------------------------------------------------------------
        # Connect matplotlib hover event
        # ------------------------------------------------------------------
        self._canvas.mpl_connect("motion_notify_event", self._on_mouse_move)

        # ------------------------------------------------------------------
        # Show welcome state
        # ------------------------------------------------------------------
        self._show_welcome()

    # ======================================================================
    # UI builders
    # ======================================================================

    def _build_plot_pane(self) -> QWidget:
        """Return the left pane: matplotlib canvas + navigation toolbar."""
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._canvas = _MplCanvas(pane)
        self._toolbar = NavigationToolbar2QT(self._canvas, pane)

        layout.addWidget(self._toolbar)
        layout.addWidget(self._canvas)
        return pane

    def _build_controls_panel(self) -> QScrollArea:
        """Return a ``QScrollArea`` containing the full controls form."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(260)
        scroll.setMaximumWidth(400)

        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        # -- File open button --
        self._btn_open = QPushButton("Open map file...")
        self._btn_open.setToolTip("Open a whitespace-delimited .txt or .dat grid file")
        self._btn_open.clicked.connect(self._open_file)
        outer.addWidget(self._btn_open)

        # -- Stats display --
        self._stats_box = QGroupBox("Array statistics")
        stats_layout = QFormLayout(self._stats_box)
        self._lbl_shape = QLabel("—")
        self._lbl_minmax = QLabel("—")
        self._lbl_mean = QLabel("—")
        self._lbl_std = QLabel("—")
        self._lbl_nan = QLabel("—")
        stats_layout.addRow("Shape:", self._lbl_shape)
        stats_layout.addRow("Min / Max:", self._lbl_minmax)
        stats_layout.addRow("Mean:", self._lbl_mean)
        stats_layout.addRow("Std dev:", self._lbl_std)
        stats_layout.addRow("NaN cells:", self._lbl_nan)
        outer.addWidget(self._stats_box)

        # -- Mode selector (headline feature R2.b-i) --
        mode_box = QGroupBox("Visualization mode")
        mode_layout = QFormLayout(mode_box)
        self._cb_mode = QComboBox()
        for m in RenderMode:
            self._cb_mode.addItem(m.value.capitalize(), userData=m.value)
        self._cb_mode.setCurrentText(RenderMode.HEATMAP.value.capitalize())
        self._cb_mode.setToolTip(
            "Select the visualization mode.\n"
            "Heatmap: 2D imshow grid\n"
            "Contour: filled contour plot\n"
            "Histogram: value distribution\n"
            "Profile: row or column line plot"
        )
        self._cb_mode.currentIndexChanged.connect(self._on_mode_changed)
        mode_layout.addRow("Mode:", self._cb_mode)
        outer.addWidget(mode_box)

        # -- Colormap and interpolation --
        cmap_box = QGroupBox("Map settings")
        cmap_layout = QFormLayout(cmap_box)

        self._cb_cmap = QComboBox()
        self._cb_cmap.addItems(list_colormaps())
        self._cb_cmap.setCurrentText(_DEFAULT_CMAP)
        self._cb_cmap.setToolTip("Select the matplotlib colormap")
        self._cb_cmap.currentTextChanged.connect(self._on_param_changed)

        self._cb_interp = QComboBox()
        self._cb_interp.addItems(list_interpolations())
        self._cb_interp.setCurrentText(_DEFAULT_INTERP)
        self._cb_interp.setToolTip(
            "Select the imshow interpolation (heatmap mode only)"
        )
        self._cb_interp.currentTextChanged.connect(self._on_param_changed)

        cmap_layout.addRow("Colormap:", self._cb_cmap)
        cmap_layout.addRow("Interpolation:", self._cb_interp)
        outer.addWidget(cmap_box)

        # -- Value range (data clamp) --
        vr_box = QGroupBox("Value range (data clamp)")
        vr_layout = QFormLayout(vr_box)

        self._sl_val_min = self._make_slider()
        self._ed_val_min = _FloatEdit()
        self._sl_val_max = self._make_slider()
        self._ed_val_max = _FloatEdit()

        self._sl_val_min.valueChanged.connect(
            lambda v: self._on_slider_moved(v, "val_min"))
        self._ed_val_min.editingFinished.connect(
            lambda: self._on_edit_finished("val_min"))

        self._sl_val_max.valueChanged.connect(
            lambda v: self._on_slider_moved(v, "val_max"))
        self._ed_val_max.editingFinished.connect(
            lambda: self._on_edit_finished("val_max"))

        vr_layout.addRow("Min:", self._ed_val_min)
        vr_layout.addRow("", self._sl_val_min)
        vr_layout.addRow("Max:", self._ed_val_max)
        vr_layout.addRow("", self._sl_val_max)

        btn_vr_reset = QPushButton("Reset to data range")
        btn_vr_reset.clicked.connect(self._reset_value_range)
        vr_layout.addRow(btn_vr_reset)
        outer.addWidget(vr_box)

        # -- Color range (colormap clim, independent of data clamp) --
        cr_box = QGroupBox("Color range (colormap limits)")
        cr_layout = QFormLayout(cr_box)

        self._sl_col_min = self._make_slider()
        self._ed_col_min = _FloatEdit()
        self._sl_col_max = self._make_slider()
        self._ed_col_max = _FloatEdit()

        self._sl_col_min.valueChanged.connect(
            lambda v: self._on_slider_moved(v, "col_min"))
        self._ed_col_min.editingFinished.connect(
            lambda: self._on_edit_finished("col_min"))

        self._sl_col_max.valueChanged.connect(
            lambda v: self._on_slider_moved(v, "col_max"))
        self._ed_col_max.editingFinished.connect(
            lambda: self._on_edit_finished("col_max"))

        cr_layout.addRow("Min:", self._ed_col_min)
        cr_layout.addRow("", self._sl_col_min)
        cr_layout.addRow("Max:", self._ed_col_max)
        cr_layout.addRow("", self._sl_col_max)

        btn_cr_reset = QPushButton("Reset to data range")
        btn_cr_reset.clicked.connect(self._reset_color_range)
        cr_layout.addRow(btn_cr_reset)
        outer.addWidget(cr_box)

        # -- Profile options (shown only in profile mode) --
        self._profile_box = QGroupBox("Profile options")
        pr_layout = QFormLayout(self._profile_box)

        self._cb_profile_axis = QComboBox()
        self._cb_profile_axis.addItems(["row", "col"])
        self._cb_profile_axis.setToolTip("Plot a horizontal row or vertical column slice")
        self._cb_profile_axis.currentIndexChanged.connect(self._on_profile_changed)

        self._ed_profile_index = QLineEdit("0")
        from PySide6.QtGui import QIntValidator
        self._ed_profile_index.setValidator(QIntValidator(0, 999999))
        self._ed_profile_index.setToolTip("Row or column index (0-based)")
        self._ed_profile_index.editingFinished.connect(self._on_profile_changed)

        pr_layout.addRow("Axis:", self._cb_profile_axis)
        pr_layout.addRow("Index:", self._ed_profile_index)
        self._profile_box.setVisible(False)
        outer.addWidget(self._profile_box)

        # -- Stretch filler --
        outer.addStretch(1)

        scroll.setWidget(container)
        return scroll

    @staticmethod
    def _make_slider() -> QSlider:
        sl = QSlider(Qt.Orientation.Horizontal)
        sl.setRange(0, _SLIDER_STEPS)
        sl.setValue(0)
        return sl

    def _build_menu(self) -> None:
        """Build the menu bar (File / View / Help)."""
        menubar = self.menuBar()

        # File
        file_menu = menubar.addMenu("&File")
        act_open = QAction("&Open map file...", self)
        act_open.setShortcut(QKeySequence.StandardKey.Open)
        act_open.triggered.connect(self._open_file)
        act_exit = QAction("E&xit", self)
        act_exit.setShortcut(QKeySequence.StandardKey.Quit)
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_open)
        file_menu.addSeparator()
        file_menu.addAction(act_exit)

        # View
        view_menu = menubar.addMenu("&View")
        self._act_fullscreen = QAction("&Fullscreen", self)
        self._act_fullscreen.setCheckable(True)
        self._act_fullscreen.setShortcut(QKeySequence("F11"))
        self._act_fullscreen.triggered.connect(self._toggle_fullscreen)
        view_menu.addAction(self._act_fullscreen)

        # Help
        help_menu = menubar.addMenu("&Help")
        act_about = QAction("&About Map-Visualizer...", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

    # ======================================================================
    # Welcome / empty-state display
    # ======================================================================

    def _show_welcome(self) -> None:
        """Show a prompt to open a file on the canvas."""
        ax = self._canvas.ax
        ax.text(
            0.5, 0.5,
            "Open a .txt or .dat grid file\nto start visualizing",
            transform=ax.transAxes,
            ha="center", va="center",
            fontsize=14, color="#666666",
        )
        ax.set_axis_off()
        self._canvas.draw_idle()

    # ======================================================================
    # File I/O
    # ======================================================================

    def _open_file(self) -> None:
        """Show a file-open dialog and load the selected grid file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Map-Visualizer — Open grid file",
            "",
            "Grid files (*.txt *.dat);;All files (*)",
        )
        if not path:
            return

        from map_visualizer.core import load_array
        try:
            array = load_array(path)
        except (GridLoadError, GridValidationError) as exc:
            QMessageBox.critical(
                self,
                "Map-Visualizer — File load error",
                f"Could not load '{path}':\n\n{exc}",
            )
            log.error("load_array failed for %r: %s", path, exc)
            return

        self._array = array
        self._stats = array_stats(array)
        self._update_stats_display()
        self._reset_ranges_to_data()
        self._sb_file.setText(f"File: {os.path.basename(path)}")
        log.info("Loaded %s array from %r", array.shape, path)
        self._redraw()

    # ======================================================================
    # Stats display
    # ======================================================================

    def _update_stats_display(self) -> None:
        if self._stats is None:
            return
        s = self._stats
        rows, cols = s["shape"]
        self._lbl_shape.setText(f"{rows} × {cols}")
        self._lbl_minmax.setText(f"{s['nanmin']:.4g} / {s['nanmax']:.4g}")
        self._lbl_mean.setText(f"{s['mean']:.4g}")
        self._lbl_std.setText(f"{s['std']:.4g}")
        self._lbl_nan.setText(str(s["nan_count"]))

    # ======================================================================
    # Range management
    # ======================================================================

    def _reset_ranges_to_data(self) -> None:
        """Set both value-range and color-range controls to the data extent."""
        if self._stats is None:
            return
        dmin = self._stats["nanmin"]
        dmax = self._stats["nanmax"]
        self._data_min = dmin
        self._data_max = dmax
        # Guard against flat arrays
        if dmin == dmax:
            dmin, dmax = dmin - 1.0, dmax + 1.0

        self._val_min = dmin
        self._val_max = dmax
        self._col_min = dmin
        self._col_max = dmax

        self._update_range_ui()

    def _reset_value_range(self) -> None:
        """Reset value-range controls to the full data extent."""
        if self._stats is None:
            return
        self._val_min = self._data_min
        self._val_max = self._data_max
        self._update_range_ui()
        self._redraw()

    def _reset_color_range(self) -> None:
        """Reset color-range controls to the full data extent."""
        if self._stats is None:
            return
        self._col_min = self._data_min
        self._col_max = self._data_max
        self._update_range_ui()
        self._redraw()

    def _update_range_ui(self) -> None:
        """Push current _val_* / _col_* state into the slider + edit widgets."""
        dmin, dmax = self._data_min, self._data_max
        span = dmax - dmin if dmax != dmin else 1.0

        # Block signals while updating programmatically to avoid re-entry
        for widget in (
            self._sl_val_min, self._sl_val_max,
            self._sl_col_min, self._sl_col_max,
            self._ed_val_min, self._ed_val_max,
            self._ed_col_min, self._ed_col_max,
        ):
            widget.blockSignals(True)

        self._sl_val_min.setValue(
            int((self._val_min - dmin) / span * _SLIDER_STEPS))
        self._sl_val_max.setValue(
            int((self._val_max - dmin) / span * _SLIDER_STEPS))
        self._sl_col_min.setValue(
            int((self._col_min - dmin) / span * _SLIDER_STEPS))
        self._sl_col_max.setValue(
            int((self._col_max - dmin) / span * _SLIDER_STEPS))

        self._ed_val_min.setText(f"{self._val_min:.6g}")
        self._ed_val_max.setText(f"{self._val_max:.6g}")
        self._ed_col_min.setText(f"{self._col_min:.6g}")
        self._ed_col_max.setText(f"{self._col_max:.6g}")

        for widget in (
            self._sl_val_min, self._sl_val_max,
            self._sl_col_min, self._sl_col_max,
            self._ed_val_min, self._ed_val_max,
            self._ed_col_min, self._ed_col_max,
        ):
            widget.blockSignals(False)

    def _slider_to_value(self, slider_pos: int) -> float:
        """Convert a slider position [0, _SLIDER_STEPS] to a data value."""
        dmin, dmax = self._data_min, self._data_max
        span = dmax - dmin if dmax != dmin else 1.0
        return dmin + slider_pos / _SLIDER_STEPS * span

    # ======================================================================
    # Signal handlers
    # ======================================================================

    def _on_slider_moved(self, value: int, which: str) -> None:
        """Handle a slider move for value/color range controls."""
        if self._array is None:
            return
        v = self._slider_to_value(value)

        if which == "val_min":
            if v >= self._val_max:
                return
            self._val_min = v
            self._ed_val_min.blockSignals(True)
            self._ed_val_min.setText(f"{v:.6g}")
            self._ed_val_min.blockSignals(False)
        elif which == "val_max":
            if v <= self._val_min:
                return
            self._val_max = v
            self._ed_val_max.blockSignals(True)
            self._ed_val_max.setText(f"{v:.6g}")
            self._ed_val_max.blockSignals(False)
        elif which == "col_min":
            if v >= self._col_max:
                return
            self._col_min = v
            self._ed_col_min.blockSignals(True)
            self._ed_col_min.setText(f"{v:.6g}")
            self._ed_col_min.blockSignals(False)
        elif which == "col_max":
            if v <= self._col_min:
                return
            self._col_max = v
            self._ed_col_max.blockSignals(True)
            self._ed_col_max.setText(f"{v:.6g}")
            self._ed_col_max.blockSignals(False)

        self._redraw()

    def _on_edit_finished(self, which: str) -> None:
        """Handle a return/focus-out in a float edit box."""
        if self._array is None:
            return

        edit_map = {
            "val_min": self._ed_val_min,
            "val_max": self._ed_val_max,
            "col_min": self._ed_col_min,
            "col_max": self._ed_col_max,
        }
        v = edit_map[which].float_value()
        if v is None:
            return  # invalid text — leave previous value

        if which == "val_min":
            if v >= self._val_max:
                # Restore
                self._ed_val_min.setText(f"{self._val_min:.6g}")
                return
            self._val_min = v
        elif which == "val_max":
            if v <= self._val_min:
                self._ed_val_max.setText(f"{self._val_max:.6g}")
                return
            self._val_max = v
        elif which == "col_min":
            if v >= self._col_max:
                self._ed_col_min.setText(f"{self._col_min:.6g}")
                return
            self._col_min = v
        elif which == "col_max":
            if v <= self._col_min:
                self._ed_col_max.setText(f"{self._col_max:.6g}")
                return
            self._col_max = v

        self._update_range_ui()
        self._redraw()

    def _on_mode_changed(self, _index: int) -> None:
        """Handle a mode-selector change."""
        mode = self._cb_mode.currentData()
        # Show/hide the profile-specific controls
        self._profile_box.setVisible(mode == RenderMode.PROFILE.value)
        # Interpolation only applies to heatmap
        self._cb_interp.setEnabled(mode == RenderMode.HEATMAP.value)
        if self._array is not None:
            self._redraw()

    def _on_param_changed(self, _value: object = None) -> None:
        """Handle any parameter change (cmap, interpolation)."""
        if self._array is not None:
            self._redraw()

    def _on_profile_changed(self) -> None:
        """Handle profile axis / index changes."""
        if self._array is not None:
            self._redraw()

    # ======================================================================
    # Core drawing
    # ======================================================================

    def _redraw(self) -> None:
        """Redraw the canvas for the current array and all current parameters.

        Calls the appropriate Axes-level drawing helper from ``map_visualizer.core``
        directly on the live QTAgg figure — no PNG round-trip, no pyplot.
        """
        if self._array is None:
            return

        mode = self._cb_mode.currentData()
        cmap = self._cb_cmap.currentText()
        interp = self._cb_interp.currentText()

        # Apply value-range clamp for modes that use it
        if mode in (RenderMode.HEATMAP.value, RenderMode.CONTOUR.value):
            display_array = apply_value_range(
                self._array, (self._val_min, self._val_max))
        else:
            display_array = self._array

        color_range = (self._col_min, self._col_max)

        self._canvas.clear_axes()
        ax = self._canvas.ax
        fig = self._canvas.fig

        try:
            if mode == RenderMode.HEATMAP.value:
                draw_heatmap(
                    ax, fig, display_array,
                    cmap=cmap,
                    interpolation=interp,
                    color_range=color_range,
                )

            elif mode == RenderMode.CONTOUR.value:
                draw_contour(
                    ax, fig, display_array,
                    cmap=cmap,
                    color_range=color_range,
                )

            elif mode == RenderMode.HISTOGRAM.value:
                draw_histogram(ax, display_array, cmap=cmap)

            elif mode == RenderMode.PROFILE.value:
                profile_axis = self._cb_profile_axis.currentText()
                try:
                    profile_index = int(self._ed_profile_index.text())
                except ValueError:
                    profile_index = None
                draw_profile(
                    ax, self._array,
                    profile_index=profile_index,
                    profile_axis=profile_axis,
                )

        except InvalidParameterError as exc:
            QMessageBox.warning(
                self,
                "Map-Visualizer — Invalid parameter",
                f"Render parameter error:\n\n{exc}",
            )
            log.warning("InvalidParameterError during redraw (mode=%r): %s", mode, exc)
            return
        except RenderError as exc:
            QMessageBox.critical(
                self,
                "Map-Visualizer — Render error",
                f"Rendering failed:\n\n{exc}",
            )
            log.error("RenderError during redraw (mode=%r): %s", mode, exc)
            return

        self._canvas.draw_idle()

    # ======================================================================
    # Mouse hover — pixel readout
    # ======================================================================

    def _on_mouse_move(self, event) -> None:
        """Update the status-bar pixel readout from a matplotlib motion event."""
        if event.inaxes is None or self._array is None:
            self._sb_x.setText("X: —")
            self._sb_y.setText("Y: —")
            self._sb_val.setText("val: —")
            return

        mode = self._cb_mode.currentData()
        # Pixel readout only makes sense for 2D image modes
        if mode not in (RenderMode.HEATMAP.value, RenderMode.CONTOUR.value):
            self._sb_x.setText("")
            self._sb_y.setText("")
            self._sb_val.setText("")
            return

        xdata = event.xdata
        ydata = event.ydata
        if xdata is None or ydata is None:
            return

        rows, cols = self._array.shape
        # The axes extent is [1, cols+1, 1, rows+1]; convert to 0-based index
        col_idx = int(xdata) - 1
        row_idx = int(ydata) - 1

        if 0 <= col_idx < cols and 0 <= row_idx < rows:
            val = self._array[row_idx, col_idx]
            if abs(val) < 0.01 or abs(val) >= 1000:
                val_str = f"{val:.3e}"
            else:
                val_str = f"{val:.3f}"
            self._sb_x.setText(f"X: {col_idx + 1}")
            self._sb_y.setText(f"Y: {row_idx + 1}")
            self._sb_val.setText(f"val: {val_str}")
        else:
            self._sb_x.setText("X: —")
            self._sb_y.setText("Y: —")
            self._sb_val.setText("val: —")

    # ======================================================================
    # View actions
    # ======================================================================

    def _toggle_fullscreen(self, checked: bool) -> None:
        """Toggle fullscreen mode."""
        if checked:
            self.showFullScreen()
        else:
            self.showNormal()
        self._is_fullscreen = checked

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Map-Visualizer",
            f"<b>Map-Visualizer v{_VERSION}</b><br>"
            f"Author: {_AUTHOR}<br>"
            f"License: {_LICENSE}<br><br>"
            "2D numeric-array heatmap viewer.<br>"
            "Visualize whitespace-delimited .txt/.dat grid files.",
        )

    # ======================================================================
    # Context menu (right-click on canvas / window)
    # ======================================================================

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        act_open = menu.addAction("Open map file...")
        act_fullscreen = menu.addAction("Fullscreen")
        act_fullscreen.setCheckable(True)
        act_fullscreen.setChecked(self._is_fullscreen)
        menu.addSeparator()
        act_about = menu.addAction("About Map-Visualizer...")
        menu.addSeparator()
        act_exit = menu.addAction("Exit")

        chosen = menu.exec(event.globalPos())
        if chosen == act_open:
            self._open_file()
        elif chosen == act_fullscreen:
            new_state = not self._is_fullscreen
            self._act_fullscreen.setChecked(new_state)
            self._toggle_fullscreen(new_state)
        elif chosen == act_about:
            self._show_about()
        elif chosen == act_exit:
            self.close()
