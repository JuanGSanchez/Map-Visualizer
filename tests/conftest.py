"""
Shared fixtures for the Map-Visualizer test suite.

All fixtures that build numpy arrays or temporary files are defined here so
individual test modules can import them by name without duplication.

Design notes
------------
* NEVER touches real user files.  tmp_path (pytest's per-test temp dir) is used
  for all file-system fixtures.
* Sets the matplotlib backend to Agg before any import of the core so tests run
  headlessly on every platform.
* Inline grids are small (3x3 to 5x5) to keep test execution fast.
"""
from __future__ import annotations

import os
import textwrap

import matplotlib
matplotlib.use("Agg")  # must be set before any map_visualizer import

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Small 2-D arrays
# ---------------------------------------------------------------------------

@pytest.fixture
def simple_3x3() -> np.ndarray:
    """A clean 3x3 float64 array with known values 1..9."""
    return np.arange(1.0, 10.0).reshape(3, 3)


@pytest.fixture
def simple_5x4() -> np.ndarray:
    """A clean 5x4 float64 array."""
    return np.arange(1.0, 21.0).reshape(5, 4)


@pytest.fixture
def array_with_nans() -> np.ndarray:
    """A 3x3 array where the centre cell is NaN."""
    arr = np.arange(1.0, 10.0).reshape(3, 3)
    arr[1, 1] = np.nan
    return arr


@pytest.fixture
def all_nan_3x3() -> np.ndarray:
    """A 3x3 array that is entirely NaN (used to test rejection path)."""
    return np.full((3, 3), np.nan)


# ---------------------------------------------------------------------------
# Temporary grid files
# ---------------------------------------------------------------------------

@pytest.fixture
def grid_txt_file(tmp_path, simple_3x3) -> str:
    """Write simple_3x3 to a .txt file and return the absolute path."""
    path = tmp_path / "grid.txt"
    np.savetxt(str(path), simple_3x3, fmt="%.1f")
    return str(path)


@pytest.fixture
def grid_dat_file(tmp_path, simple_5x4) -> str:
    """Write simple_5x4 to a .dat file and return the absolute path."""
    path = tmp_path / "grid.dat"
    np.savetxt(str(path), simple_5x4, fmt="%.1f")
    return str(path)


@pytest.fixture
def grid_with_nan_file(tmp_path, array_with_nans) -> str:
    """Write the partial-NaN array to a .txt file and return the absolute path."""
    path = tmp_path / "nan_grid.txt"
    np.savetxt(str(path), array_with_nans, fmt="%.6f")
    return str(path)


# ---------------------------------------------------------------------------
# Raw inline text strings
# ---------------------------------------------------------------------------

@pytest.fixture
def inline_text_3x3() -> str:
    """Whitespace-delimited inline text equivalent of simple_3x3."""
    return "1.0 2.0 3.0\n4.0 5.0 6.0\n7.0 8.0 9.0"


@pytest.fixture
def inline_json_2x3() -> str:
    """JSON array-of-arrays string for the REST service tests."""
    return "[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]"


# ---------------------------------------------------------------------------
# Matplotlib Figure / Axes (no pyplot)
# ---------------------------------------------------------------------------

@pytest.fixture
def fig_ax():
    """Return a (Figure, Axes) pair created without pyplot."""
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    fig = Figure(figsize=(4, 3), dpi=72)
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    return fig, ax
