"""
Juan García Sánchez, 2023-2026
Map-Visualizer — headless render core (workstream a).

Public API
----------
load_array(source, *, max_cells=...) -> numpy.ndarray
array_stats(array) -> dict
render(array, *, mode, value_range, color_range, cmap, interpolation,
       profile_index, profile_axis) -> bytes
list_colormaps() -> list[str]
list_interpolations() -> list[str]

Design constraints
------------------
* NEVER imports ``matplotlib.pyplot``.  All rendering uses
  ``matplotlib.figure.Figure`` + ``matplotlib.backends.backend_agg.FigureCanvasAgg``
  so this module is safe to import in headless / server contexts without
  triggering any GUI backend initialisation.
* No Tkinter, no Qt, no display dependency of any kind.
* Returns raw PNG bytes from ``render()`` so every consumer (PySide6 UI,
  FastAPI REST endpoint, FastMCP tool) can use the same core unchanged.
"""

from __future__ import annotations

import io
import logging
import math
import textwrap
from typing import IO, Union

import numpy as np

from .enums import RenderMode
from .exceptions import (
    GridLoadError,
    GridValidationError,
    InvalidParameterError,
    RenderError,
)

# ---------------------------------------------------------------------------
# Module-level logger (replaces bare print() calls — R-2 / strategy step 4)
# ---------------------------------------------------------------------------
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Default maximum number of array cells accepted by :func:`load_array`.
#: A 4 K × 4 K grid (≈ 16 M cells × 8 bytes ≈ 128 MB) is a sensible ceiling.
DEFAULT_MAX_CELLS: int = 4096 * 4096

#: Default figure size (width, height) in inches used by :func:`render`.
_FIGURE_SIZE = (6, 5)
#: Default DPI used by :func:`render`.
_FIGURE_DPI = 100

# ---------------------------------------------------------------------------
# Lazy colormap / interpolation caches
# ---------------------------------------------------------------------------

_colormaps_cache: list[str] | None = None
_interpolations_cache: list[str] | None = None


def list_colormaps() -> list[str]:
    """Return the sorted list of all matplotlib colormap names.

    The list is computed once and cached.  Uses the ``matplotlib.colormaps``
    registry (matplotlib ≥ 3.5) without importing ``pyplot``.

    Returns
    -------
    list[str]
        Sorted colormap name strings.
    """
    global _colormaps_cache
    if _colormaps_cache is None:
        import matplotlib
        _colormaps_cache = sorted(matplotlib.colormaps.keys())
    return list(_colormaps_cache)


def list_interpolations() -> list[str]:
    """Return the sorted list of all matplotlib ``imshow`` interpolation names.

    Returns
    -------
    list[str]
        Sorted interpolation name strings.
    """
    global _interpolations_cache
    if _interpolations_cache is None:
        import matplotlib.image as mimage
        _interpolations_cache = sorted(mimage.interpolations_names)
    return list(_interpolations_cache)


# ---------------------------------------------------------------------------
# Array loading — hardened loader (R-2, R-3)
# ---------------------------------------------------------------------------

#: Type alias for the ``source`` parameter of :func:`load_array`.
SourceType = Union[str, "os.PathLike[str]", IO[str], IO[bytes]]


def load_array(
    source: SourceType,
    *,
    max_cells: int = DEFAULT_MAX_CELLS,
) -> np.ndarray:
    """Load a whitespace-delimited 2-D numeric grid.

    Accepts a file path (``str`` / ``os.PathLike``), an open text/binary
    file-like object, or a raw multi-line string (passed through a
    ``io.StringIO`` wrapper internally).

    Parameters
    ----------
    source:
        Path to a ``.txt`` or ``.dat`` file, an open file-like, or a string
        containing the raw grid text.
    max_cells:
        Maximum total number of array cells allowed.  Default is
        :data:`DEFAULT_MAX_CELLS` (~16 M).  Pass ``0`` to disable the cap.

    Returns
    -------
    numpy.ndarray
        A 2-D array of ``float64``.  A 1-D result (single row or column) is
        promoted to a ``(1, N)`` or ``(N, 1)`` 2-D array.

    Raises
    ------
    GridLoadError
        If the source cannot be read or parsed (file not found, wrong
        extension, not numeric, etc.).
    GridValidationError
        If the loaded array is empty, all-NaN, has ragged rows, or exceeds
        *max_cells*.
    """
    import os

    # ------------------------------------------------------------------
    # Resolve the source to a readable object
    # ------------------------------------------------------------------
    raw_text: str | None = None

    if isinstance(source, str):
        # Detect whether it looks like raw text (contains a newline or
        # spaces that suggest multi-token content but no OS path separators).
        is_path = (
            os.sep in source
            or (os.altsep and os.altsep in source)
            or "\n" not in source
        )
        if is_path:
            # Validate extension before attempting to read
            lower = source.lower()
            if not (lower.endswith(".txt") or lower.endswith(".dat")):
                raise GridLoadError(
                    f"Unsupported file extension: '{source}'.  "
                    "Only .txt and .dat files are supported."
                )
            if not os.path.exists(source):
                raise GridLoadError(f"File not found: '{source}'.")
        else:
            # Treat as raw text content
            raw_text = source
    elif hasattr(source, "read"):
        pass  # file-like: pass through to np.loadtxt below
    else:
        # Attempt to coerce path-like objects
        try:
            import os
            source = os.fspath(source)  # type: ignore[arg-type]
        except TypeError as exc:
            raise GridLoadError(
                f"Cannot interpret source of type {type(source).__name__!r} "
                "as a file path or text string."
            ) from exc

    # ------------------------------------------------------------------
    # Parse with np.loadtxt, catching ALL real errors
    # ------------------------------------------------------------------
    try:
        if raw_text is not None:
            fileobj: IO[str] = io.StringIO(raw_text)
            array = np.loadtxt(fileobj)
        else:
            array = np.loadtxt(source)
    except ValueError as exc:
        # np.loadtxt raises ValueError for ragged rows ("Wrong number of
        # columns") and for non-numeric content.
        msg = str(exc)
        if "Wrong number of columns" in msg or "columns" in msg.lower():
            raise GridValidationError(
                "The grid has ragged rows (rows with different column counts).  "
                f"NumPy reported: {msg}"
            ) from exc
        raise GridLoadError(
            f"Failed to parse the grid as numeric data: {msg}"
        ) from exc
    except OSError as exc:
        raise GridLoadError(f"Could not read source: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise GridLoadError(
            f"Unexpected error while loading grid: {type(exc).__name__}: {exc}"
        ) from exc

    # ------------------------------------------------------------------
    # Shape normalisation: promote 0-D and 1-D to 2-D
    # ------------------------------------------------------------------
    if array.ndim == 0:
        # Single scalar — treat as a 1×1 grid
        array = array.reshape(1, 1)
    elif array.ndim == 1:
        # Single row (np.loadtxt flattens a one-row file to 1-D)
        array = array.reshape(1, -1)
    # Note: a single-column file loads as (N, 1) naturally via np.loadtxt
    # when the file has N lines each with one number — already 2-D.

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    if array.size == 0:
        raise GridValidationError(
            "The loaded array is empty (zero elements)."
        )

    if max_cells > 0 and array.size > max_cells:
        rows, cols = array.shape
        raise GridValidationError(
            f"Array size {rows}×{cols} = {array.size:,} cells exceeds the "
            f"maximum of {max_cells:,} cells.  Use a smaller file or increase "
            "max_cells."
        )

    if np.all(np.isnan(array)):
        raise GridValidationError(
            "The loaded array contains only NaN values; cannot visualize."
        )

    log.debug("load_array: loaded %s array from %r", array.shape, source)
    return array


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def array_stats(array: np.ndarray) -> dict:
    """Compute lightweight statistics for a 2-D array.

    Parameters
    ----------
    array:
        A 2-D ``numpy.ndarray``.

    Returns
    -------
    dict with keys:
        ``shape``       — (rows, cols) tuple.
        ``min``         — global minimum (including NaN regions → may be NaN
                          if the whole column is NaN, but :func:`load_array`
                          rejects all-NaN arrays so this only fires on partial
                          NaN arrays).
        ``max``         — global maximum (same caveat).
        ``nanmin``      — NaN-ignoring minimum.
        ``nanmax``      — NaN-ignoring maximum.
        ``mean``        — NaN-ignoring mean.
        ``std``         — NaN-ignoring standard deviation.
        ``nan_count``   — number of NaN cells.
        ``sci_exp``     — base-10 exponent for scientific-notation axis
                          scaling (same logic as the original ``sci_exp``
                          utility, but returns 0 when reference magnitude is
                          already in [0.01, 1000)).
    """
    shape = array.shape
    nan_count = int(np.sum(np.isnan(array)))
    nanmin = float(np.nanmin(array))
    nanmax = float(np.nanmax(array))

    return {
        "shape": shape,
        "min": float(np.min(array)),
        "max": float(np.max(array)),
        "nanmin": nanmin,
        "nanmax": nanmax,
        "mean": float(np.nanmean(array)),
        "std": float(np.nanstd(array)),
        "nan_count": nan_count,
        "sci_exp": _sci_exp_for_range(nanmin, nanmax),
    }


def _sci_exp_for_range(vmin: float, vmax: float) -> int:
    """Return the ref_exp scaling integer used in the original app.

    The original logic is::

        ref_val = max(|vmin|, |vmax|)
        if not 1000 >= ref_val > 0.01:
            ref_exp = -sci_exp(ref_val) + 2
        else:
            ref_exp = 0

    where ``sci_exp(x) = floor(log10(x))``.

    Returns
    -------
    int
        The exponent (``ref_exp``) to multiply values by ``10**ref_exp`` to
        bring them into a comfortable display range.  0 if already in range.
    """
    ref_val = max(abs(vmin), abs(vmax))
    if ref_val == 0.0:
        return 0
    if 0.01 < ref_val <= 1000:
        return 0
    exp = int(math.floor(math.log10(ref_val)))
    return -exp + 2


# ---------------------------------------------------------------------------
# Value-range and color-range pure helpers
# ---------------------------------------------------------------------------

def apply_value_range(
    array: np.ndarray,
    value_range: tuple[float, float],
) -> np.ndarray:
    """Clip array values to [vmin, vmax] via ``np.where`` (preserves shape).

    Parameters
    ----------
    array:
        Input 2-D array.
    value_range:
        ``(vmin, vmax)`` clamp limits.

    Returns
    -------
    numpy.ndarray
        New array with values outside *value_range* clamped to the boundary.
    """
    vmin, vmax = float(value_range[0]), float(value_range[1])
    clipped = np.where(array < vmin, vmin, array)
    clipped = np.where(clipped > vmax, vmax, clipped)
    return clipped


# ---------------------------------------------------------------------------
# Parameter validation helpers
# ---------------------------------------------------------------------------

def _validate_mode(mode: str) -> RenderMode:
    try:
        return RenderMode(mode)
    except ValueError:
        raise InvalidParameterError(
            f"Unknown render mode {mode!r}.  "
            f"Supported modes: {RenderMode.values()}"
        )


def _validate_cmap(cmap: str) -> str:
    available = list_colormaps()
    if cmap not in available:
        raise InvalidParameterError(
            f"Unknown colormap {cmap!r}.  "
            f"Call list_colormaps() for the full list."
        )
    return cmap


def _validate_interpolation(interpolation: str) -> str:
    available = list_interpolations()
    if interpolation not in available:
        raise InvalidParameterError(
            f"Unknown interpolation {interpolation!r}.  "
            f"Call list_interpolations() for the full list."
        )
    return interpolation


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def render(
    array: np.ndarray,
    *,
    mode: str = "heatmap",
    value_range: tuple[float, float] | None = None,
    color_range: tuple[float, float] | None = None,
    cmap: str = "viridis",
    interpolation: str = "nearest",
    profile_index: int | None = None,
    profile_axis: str = "row",
    figsize: tuple[float, float] = _FIGURE_SIZE,
    dpi: int = _FIGURE_DPI,
) -> bytes:
    """Render *array* headlessly and return PNG bytes.

    This function never imports ``matplotlib.pyplot`` or any GUI backend.
    It constructs a :class:`matplotlib.figure.Figure`, attaches a
    :class:`~matplotlib.backends.backend_agg.FigureCanvasAgg`, draws the
    requested visualization, and serialises the result to a PNG byte string
    via a :class:`io.BytesIO` buffer.

    Parameters
    ----------
    array:
        A 2-D ``numpy.ndarray`` (as returned by :func:`load_array`).
    mode:
        Visualization mode.  One of ``"heatmap"``, ``"contour"``,
        ``"histogram"``, ``"profile"``.  Case-sensitive; use
        :class:`~map_visualizer.enums.RenderMode` for safety.
    value_range:
        Optional ``(vmin, vmax)`` pair.  Values outside this window are
        clamped before rendering (heatmap and contour modes).
    color_range:
        Optional ``(cmin, cmax)`` pair that sets the colormap normalisation
        limits independently of the data range.  Only meaningful for modes
        that draw a colorbar (heatmap, contour).
    cmap:
        Matplotlib colormap name (default ``"viridis"``).  Must be a value
        returned by :func:`list_colormaps`.
    interpolation:
        Matplotlib ``imshow`` interpolation name (default ``"nearest"``).
        Must be a value returned by :func:`list_interpolations`.  Only used
        in ``"heatmap"`` mode.
    profile_index:
        Row or column index for ``"profile"`` mode.  Defaults to the middle
        row/column if ``None``.
    profile_axis:
        ``"row"`` (plot a horizontal slice) or ``"col"`` (plot a vertical
        slice).  Only used in ``"profile"`` mode.
    figsize:
        ``(width, height)`` in inches for the figure (default ``(6, 5)``).
    dpi:
        Dots per inch for the figure (default ``100``).

    Returns
    -------
    bytes
        Raw PNG byte string.  Suitable for writing to a file, returning as an
        HTTP ``image/png`` response, or wrapping in a FastMCP ``Image``.

    Raises
    ------
    InvalidParameterError
        If *mode*, *cmap*, or *interpolation* is not a recognised value.
    RenderError
        If an unexpected matplotlib error occurs during rendering.
    """
    # -- Validate parameters (typed errors, not bare except) ----------------
    render_mode = _validate_mode(mode)
    _validate_cmap(cmap)
    if render_mode == RenderMode.HEATMAP:
        _validate_interpolation(interpolation)

    # -- Ensure 2-D input ---------------------------------------------------
    if array.ndim != 2:
        raise RenderError(
            f"render() requires a 2-D array; got shape {array.shape}."
        )

    # -- Apply value range clamp (heatmap + contour) -----------------------
    display_array = array
    if value_range is not None and render_mode in (
        RenderMode.HEATMAP,
        RenderMode.CONTOUR,
    ):
        display_array = apply_value_range(array, value_range)

    # -- Build figure (Agg only — no pyplot, no GUI) -----------------------
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    fig = Figure(figsize=figsize, dpi=dpi, facecolor="white", tight_layout=True)
    FigureCanvasAgg(fig)  # attach Agg canvas — no display, no GUI
    ax = fig.add_subplot(111)

    try:
        if render_mode == RenderMode.HEATMAP:
            _render_heatmap(
                ax, fig, display_array,
                cmap=cmap,
                interpolation=interpolation,
                color_range=color_range,
            )

        elif render_mode == RenderMode.CONTOUR:
            _render_contour(
                ax, fig, display_array,
                cmap=cmap,
                color_range=color_range,
            )

        elif render_mode == RenderMode.HISTOGRAM:
            _render_histogram(ax, display_array, cmap=cmap)

        elif render_mode == RenderMode.PROFILE:
            _render_profile(
                ax, array,
                profile_index=profile_index,
                profile_axis=profile_axis,
            )

    except (InvalidParameterError, RenderError):
        raise
    except Exception as exc:  # noqa: BLE001
        raise RenderError(
            f"Matplotlib raised an unexpected error during render "
            f"(mode={mode!r}): {type(exc).__name__}: {exc}"
        ) from exc

    # -- Serialise to PNG bytes --------------------------------------------
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Public Axes-level drawing helpers
# ---------------------------------------------------------------------------
# These are the single source of truth for per-mode drawing.  They accept a
# matplotlib ``Axes`` (and the parent ``Figure`` when a colorbar is needed)
# and draw the requested visualization onto that axes.  Both the headless
# ``render()`` path (Agg backend) and the interactive Qt UI (QTAgg backend)
# call these helpers — one set of drawing code, two front-ends.

def draw_heatmap(
    ax,
    fig,
    array: np.ndarray,
    *,
    cmap: str = "viridis",
    interpolation: str = "nearest",
    color_range: tuple[float, float] | None = None,
) -> None:
    """Draw an imshow heatmap on *ax*.

    Parameters
    ----------
    ax:
        Matplotlib ``Axes`` to draw on.
    fig:
        Parent ``Figure`` (needed to attach the colorbar).
    array:
        2-D ``numpy.ndarray`` to visualise.
    cmap:
        Matplotlib colormap name.
    interpolation:
        ``imshow`` interpolation name.
    color_range:
        Optional ``(cmin, cmax)`` colormap normalisation limits.  When given,
        the colorbar limits are set to this range independently of the data.
    """
    _render_heatmap(ax, fig, array, cmap=cmap, interpolation=interpolation,
                    color_range=color_range)


def draw_contour(
    ax,
    fig,
    array: np.ndarray,
    *,
    cmap: str = "viridis",
    color_range: tuple[float, float] | None = None,
) -> None:
    """Draw a filled + line contour on *ax*.

    Parameters
    ----------
    ax:
        Matplotlib ``Axes`` to draw on.
    fig:
        Parent ``Figure`` (needed to attach the colorbar).
    array:
        2-D ``numpy.ndarray`` to visualise.
    cmap:
        Matplotlib colormap name.
    color_range:
        Optional ``(vmin, vmax)`` contour normalisation limits.
    """
    _render_contour(ax, fig, array, cmap=cmap, color_range=color_range)


def draw_histogram(
    ax,
    array: np.ndarray,
    *,
    cmap: str = "viridis",
) -> None:
    """Draw a histogram of the non-NaN cell values on *ax*.

    Parameters
    ----------
    ax:
        Matplotlib ``Axes`` to draw on.
    array:
        2-D ``numpy.ndarray`` whose values are histogrammed.
    cmap:
        Matplotlib colormap name used to colour the histogram bars.
    """
    _render_histogram(ax, array, cmap=cmap)


def draw_profile(
    ax,
    array: np.ndarray,
    *,
    profile_index: int | None = None,
    profile_axis: str = "row",
) -> None:
    """Draw a row or column profile (1-D slice line plot) on *ax*.

    Parameters
    ----------
    ax:
        Matplotlib ``Axes`` to draw on.
    array:
        2-D ``numpy.ndarray`` to slice.
    profile_index:
        Row or column index to plot.  Defaults to the middle row/column.
    profile_axis:
        ``"row"`` (horizontal slice) or ``"col"`` (vertical slice).
    """
    _render_profile(ax, array, profile_index=profile_index,
                    profile_axis=profile_axis)


# ---------------------------------------------------------------------------
# Private per-mode rendering helpers
# ---------------------------------------------------------------------------

def _render_heatmap(
    ax,
    fig,
    array: np.ndarray,
    *,
    cmap: str,
    interpolation: str,
    color_range: tuple[float, float] | None,
) -> None:
    """Draw an imshow heatmap on *ax*, optionally with a colorbar."""
    rows, cols = array.shape
    extent = [1, cols + 1, 1, rows + 1]

    vmin = float(np.nanmin(array))
    vmax = float(np.nanmax(array))

    im = ax.imshow(
        array,
        cmap=cmap,
        interpolation=interpolation,
        origin="lower",
        extent=extent,
        vmin=vmin,
        vmax=vmax,
        aspect="auto",
    )

    if color_range is not None:
        im.set_clim(vmin=color_range[0], vmax=color_range[1])

    fig.colorbar(im, ax=ax, orientation="vertical", format="%.2f")
    ax.tick_params(
        bottom=False, left=False, labelbottom=False, labelleft=False
    )


def _render_contour(
    ax,
    fig,
    array: np.ndarray,
    *,
    cmap: str,
    color_range: tuple[float, float] | None,
) -> None:
    """Draw a filled + line contour on *ax*."""
    rows, cols = array.shape
    x = np.arange(1, cols + 2)
    y = np.arange(1, rows + 2)
    X, Y = np.meshgrid(x[:-1] + 0.5, y[:-1] + 0.5)

    vmin = float(np.nanmin(array))
    vmax = float(np.nanmax(array))
    if color_range is not None:
        vmin, vmax = color_range[0], color_range[1]

    # Filled contour
    cf = ax.contourf(X, Y, array, levels=12, cmap=cmap, vmin=vmin, vmax=vmax)
    # Line contour overlay
    ax.contour(X, Y, array, levels=12, colors="k", linewidths=0.5, alpha=0.4)

    fig.colorbar(cf, ax=ax, orientation="vertical", format="%.2f")
    ax.set_aspect("auto")


def _render_histogram(
    ax,
    array: np.ndarray,
    *,
    cmap: str,
) -> None:
    """Draw a histogram of the non-NaN cell values."""
    flat = array[~np.isnan(array)].ravel()
    if flat.size == 0:
        ax.text(
            0.5, 0.5, "No finite values to plot",
            transform=ax.transAxes, ha="center", va="center",
        )
        return

    # Use up to 50 bins; fewer if there are very few unique values
    n_bins = min(50, max(5, int(np.sqrt(flat.size))))

    # Colour the bars using the selected cmap to keep aesthetic consistency.
    # matplotlib.cm.get_cmap was removed in 3.9+; use matplotlib.colormaps
    # registry (available since 3.5) instead.
    import matplotlib
    import matplotlib.colors as mplcolors

    n, edges, patches = ax.hist(flat, bins=n_bins, edgecolor="white", linewidth=0.5)
    # Map bar colours to cmap
    cmap_obj = matplotlib.colormaps[cmap]
    norm = mplcolors.Normalize(vmin=edges[0], vmax=edges[-1])
    for patch, left in zip(patches, edges[:-1]):
        patch.set_facecolor(cmap_obj(norm(left + (edges[1] - edges[0]) / 2)))

    ax.set_xlabel("Value")
    ax.set_ylabel("Count")
    ax.set_title("Value Distribution")


def _render_profile(
    ax,
    array: np.ndarray,
    *,
    profile_index: int | None,
    profile_axis: str,
) -> None:
    """Draw a row or column profile (line plot of a 1-D slice)."""
    if profile_axis not in ("row", "col"):
        raise InvalidParameterError(
            f"profile_axis must be 'row' or 'col'; got {profile_axis!r}."
        )

    rows, cols = array.shape

    if profile_axis == "row":
        idx = profile_index if profile_index is not None else rows // 2
        if not (0 <= idx < rows):
            raise InvalidParameterError(
                f"profile_index {idx} is out of range for an array with "
                f"{rows} rows (valid: 0–{rows - 1})."
            )
        xs = np.arange(1, cols + 1)
        ys = array[idx, :]
        ax.plot(xs, ys, linewidth=1.5)
        ax.set_xlabel("Column")
        ax.set_ylabel("Value")
        ax.set_title(f"Row {idx} Profile")
    else:  # "col"
        idx = profile_index if profile_index is not None else cols // 2
        if not (0 <= idx < cols):
            raise InvalidParameterError(
                f"profile_index {idx} is out of range for an array with "
                f"{cols} columns (valid: 0–{cols - 1})."
            )
        ys = np.arange(1, rows + 1)
        xs = array[:, idx]
        ax.plot(xs, ys, linewidth=1.5)
        ax.set_xlabel("Value")
        ax.set_ylabel("Row")
        ax.set_title(f"Column {idx} Profile")
        ax.invert_yaxis()

    ax.grid(True, linestyle="--", alpha=0.4)
