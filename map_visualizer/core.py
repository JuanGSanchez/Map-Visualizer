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
import threading
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

#: Output formats supported by :func:`render` (SPEC-16).  Each maps to the
#: matplotlib ``savefig`` backend format and the bytes' validating magic prefix.
_OUTPUT_FORMATS: dict[str, bytes] = {
    "png": b"\x89PNG\r\n\x1a\n",
    "svg": b"<?xml",            # SVG documents start with the XML declaration
    "pdf": b"%PDF",
}

#: matplotlib is NOT thread-safe: the Agg font cache is class-level and a
#: concurrent ``draw``/``savefig`` is a documented segfault risk (SPEC-20,
#: research §4).  Each render builds its OWN ``Figure`` (never shared), and the
#: draw/serialise critical section is additionally serialised by this module-level
#: lock so the REST/MCP server can call :func:`render` from worker threads safely.
_RENDER_LOCK = threading.Lock()

#: Per-format ``savefig`` metadata that strips the non-deterministic
#: ``Software``/``CreationDate`` stamps matplotlib injects, so identical inputs
#: yield byte-identical output run-to-run (SPEC-18, research §7).
_DETERMINISTIC_METADATA: dict[str, dict[str, None]] = {
    "png": {"Software": None},
    "svg": {"Date": None},
    "pdf": {"CreationDate": None},
}

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


#: File extensions accepted by :func:`load_array`.
_SUPPORTED_EXTENSIONS = (".txt", ".dat", ".csv")


def _sniff_delimiter(sample: str) -> str | None:
    """Auto-detect the column delimiter from a text *sample* (SPEC-15).

    Returns the delimiter string for :func:`numpy.loadtxt`, or ``None`` for the
    native any-whitespace behaviour.  Comma and semicolon are detected from the
    first non-empty, non-comment data line; tabs and spaces fall back to the
    whitespace default (``None``).
    """
    for line in sample.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "," in stripped:
            return ","
        if ";" in stripped:
            return ";"
        return None  # whitespace-delimited (spaces / tabs)
    return None


def load_array(
    source: SourceType,
    *,
    max_cells: int = DEFAULT_MAX_CELLS,
    delimiter: str | None = None,
) -> np.ndarray:
    """Load a 2-D numeric grid from text (whitespace, CSV, or ``;``-delimited).

    Accepts a file path (``str`` / ``os.PathLike``), an open text/binary
    file-like object, or a raw multi-line string.  The column delimiter is
    auto-detected (comma / semicolon / whitespace) unless *delimiter* is given
    explicitly (SPEC-15).

    Parameters
    ----------
    source:
        Path to a ``.txt`` / ``.dat`` / ``.csv`` file, an open file-like, or a
        string containing the raw grid text.
    max_cells:
        Maximum total number of array cells allowed.  Default is
        :data:`DEFAULT_MAX_CELLS` (~16 M).  Pass ``0`` to disable the cap.
    delimiter:
        Explicit column delimiter (e.g. ``","``).  ``None`` (default)
        auto-detects from the content.

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
    # Resolve the source to raw text (so we can sniff the delimiter)
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
            if not lower.endswith(_SUPPORTED_EXTENSIONS):
                raise GridLoadError(
                    f"Unsupported file extension: '{source}'.  "
                    f"Supported extensions: {', '.join(_SUPPORTED_EXTENSIONS)}."
                )
            if not os.path.exists(source):
                raise GridLoadError(f"File not found: '{source}'.")
            try:
                with open(source, "r") as fh:
                    raw_text = fh.read()
            except OSError as exc:
                raise GridLoadError(f"Could not read source: {exc}") from exc
        else:
            # Treat as raw text content
            raw_text = source
    elif hasattr(source, "read"):
        data = source.read()
        raw_text = data.decode("utf-8") if isinstance(data, bytes) else data
    else:
        # Attempt to coerce path-like objects
        try:
            spath = os.fspath(source)  # type: ignore[arg-type]
        except TypeError as exc:
            raise GridLoadError(
                f"Cannot interpret source of type {type(source).__name__!r} "
                "as a file path or text string."
            ) from exc
        lower = spath.lower()
        if not lower.endswith(_SUPPORTED_EXTENSIONS):
            raise GridLoadError(
                f"Unsupported file extension: '{spath}'.  "
                f"Supported extensions: {', '.join(_SUPPORTED_EXTENSIONS)}."
            )
        if not os.path.exists(spath):
            raise GridLoadError(f"File not found: '{spath}'.")
        try:
            with open(spath, "r") as fh:
                raw_text = fh.read()
        except OSError as exc:
            raise GridLoadError(f"Could not read source: {exc}") from exc

    # ------------------------------------------------------------------
    # Parse with np.loadtxt, catching ALL real errors
    # ------------------------------------------------------------------
    used_delimiter = delimiter if delimiter is not None else _sniff_delimiter(raw_text or "")
    try:
        array = np.loadtxt(io.StringIO(raw_text or ""), delimiter=used_delimiter)
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


def downsample(array: np.ndarray, max_cells: int) -> np.ndarray:
    """Stride-decimate a 2-D *array* so its cell count is <= *max_cells* (SPEC-22).

    Returns the array unchanged when it already fits or *max_cells* <= 0.  The
    decimation factor is the same on both axes (``array[::f, ::f]``) so aspect
    ratio is preserved.  This is an *additive* render-time bound — it never
    replaces the :func:`load_array` ``max_cells`` load guard (invariant 6).

    Parameters
    ----------
    array:
        Input 2-D array.
    max_cells:
        Target maximum cell count after decimation.

    Returns
    -------
    numpy.ndarray
        A view/strided copy with <= *max_cells* cells (best effort; the result
        may be slightly above the target by at most one stride step).
    """
    if max_cells <= 0 or array.size <= max_cells:
        return array
    factor = int(math.ceil(math.sqrt(array.size / max_cells)))
    factor = max(factor, 1)
    return array[::factor, ::factor]


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
    levels: int | None = None,
    bins: int | None = None,
    colorbar: bool = True,
    title: str | None = None,
    xlabel: str | None = None,
    ylabel: str | None = None,
    output_format: str = "png",
    max_render_cells: int | None = None,
    figsize: tuple[float, float] = _FIGURE_SIZE,
    dpi: int = _FIGURE_DPI,
) -> bytes:
    """Render *array* headlessly and return image bytes.

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
        ``"contourf"``, ``"surface3d"``, ``"histogram"``, ``"profile"``,
        ``"profile_row"``, ``"profile_col"``.  Case-sensitive; use
        :class:`~map_visualizer.enums.RenderMode` for safety.
    levels:
        Contour band count for ``contour``/``contourf`` modes (default 12).
    bins:
        Histogram bin count for ``histogram`` mode (default: auto).
    colorbar:
        Whether to draw a colorbar for the colorbar-bearing modes.
    title, xlabel, ylabel:
        Optional explicit axis title / axis labels (SPEC-16).
    output_format:
        ``"png"`` (default), ``"svg"``, or ``"pdf"`` (SPEC-16).  Returns valid
        bytes of the requested format with non-deterministic metadata stripped.
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

    out_fmt = output_format.lower()
    if out_fmt not in _OUTPUT_FORMATS:
        raise InvalidParameterError(
            f"Unknown output_format {output_format!r}.  "
            f"Supported: {sorted(_OUTPUT_FORMATS)}"
        )

    # -- Ensure 2-D input ---------------------------------------------------
    if array.ndim != 2:
        raise RenderError(
            f"render() requires a 2-D array; got shape {array.shape}."
        )

    # -- Optional render-time downsampling (SPEC-22) -----------------------
    # An ADDITIVE bound that caps the per-render imshow work; it never replaces
    # the load_array max_cells guard (invariant 6).
    if max_render_cells is not None:
        array = downsample(array, max_render_cells)

    # -- Apply value range clamp (heatmap + contour family) ----------------
    display_array = array
    if value_range is not None and render_mode in (
        RenderMode.HEATMAP,
        RenderMode.CONTOUR,
        RenderMode.CONTOURF,
        RenderMode.SURFACE3D,
    ):
        display_array = apply_value_range(array, value_range)

    # matplotlib is not thread-safe (SPEC-20): build the figure, draw, and
    # serialise entirely inside the module-level render lock.  The Figure is
    # function-local so it is never shared across threads (SPEC-19/20).
    with _RENDER_LOCK:
        # -- Build figure (Agg only — no pyplot, no GUI) -------------------
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg

        fig = Figure(figsize=figsize, dpi=dpi, facecolor="white", tight_layout=True)
        FigureCanvasAgg(fig)  # attach Agg canvas — no display, no GUI

        if render_mode == RenderMode.SURFACE3D:
            ax = fig.add_subplot(111, projection="3d")
        else:
            ax = fig.add_subplot(111)

        try:
            if render_mode == RenderMode.HEATMAP:
                _render_heatmap(
                    ax, fig, display_array,
                    cmap=cmap,
                    interpolation=interpolation,
                    color_range=color_range,
                    colorbar=colorbar,
                )

            elif render_mode == RenderMode.CONTOUR:
                _render_contour(
                    ax, fig, display_array,
                    cmap=cmap,
                    color_range=color_range,
                    levels=levels,
                    lines=True,
                    colorbar=colorbar,
                )

            elif render_mode == RenderMode.CONTOURF:
                _render_contour(
                    ax, fig, display_array,
                    cmap=cmap,
                    color_range=color_range,
                    levels=levels,
                    lines=False,
                    colorbar=colorbar,
                )

            elif render_mode == RenderMode.SURFACE3D:
                _render_surface3d(
                    ax, fig, display_array,
                    cmap=cmap,
                    color_range=color_range,
                    colorbar=colorbar,
                )

            elif render_mode == RenderMode.HISTOGRAM:
                _render_histogram(ax, display_array, cmap=cmap, bins=bins)

            elif render_mode == RenderMode.PROFILE:
                _render_profile(
                    ax, array,
                    profile_index=profile_index,
                    profile_axis=profile_axis,
                )

            elif render_mode == RenderMode.PROFILE_ROW:
                _render_profile(
                    ax, array, profile_index=profile_index, profile_axis="row",
                )

            elif render_mode == RenderMode.PROFILE_COL:
                _render_profile(
                    ax, array, profile_index=profile_index, profile_axis="col",
                )

            # -- Optional explicit annotations (SPEC-16) ------------------
            if title is not None:
                ax.set_title(title)
            if xlabel is not None:
                ax.set_xlabel(xlabel)
            if ylabel is not None:
                ax.set_ylabel(ylabel)

        except (InvalidParameterError, RenderError):
            raise
        except Exception as exc:  # noqa: BLE001
            raise RenderError(
                f"Matplotlib raised an unexpected error during render "
                f"(mode={mode!r}): {type(exc).__name__}: {exc}"
            ) from exc

        # -- Serialise to deterministic bytes (SPEC-18) -------------------
        # Strip the version/date stamp matplotlib injects so identical inputs
        # produce byte-identical output run-to-run.  No bbox_inches="tight" —
        # pixel dimensions stay exactly figsize*dpi.  A fixed ``svg.hashsalt``
        # makes SVG clip-path / gid identifiers stable across runs (otherwise
        # they are randomised per process and break byte-equality).
        import matplotlib

        buf = io.BytesIO()
        with matplotlib.rc_context({"svg.hashsalt": "map-visualizer"}):
            fig.savefig(
                buf,
                format=out_fmt,
                metadata=_DETERMINISTIC_METADATA[out_fmt],
            )
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
    colorbar: bool = True,
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
    colorbar:
        Whether to attach a colorbar (default ``True``).
    """
    _render_heatmap(ax, fig, array, cmap=cmap, interpolation=interpolation,
                    color_range=color_range, colorbar=colorbar)


def draw_contour(
    ax,
    fig,
    array: np.ndarray,
    *,
    cmap: str = "viridis",
    color_range: tuple[float, float] | None = None,
    levels: int | None = None,
    colorbar: bool = True,
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
    levels:
        Number of contour bands (default :data:`_DEFAULT_CONTOUR_LEVELS`).
    colorbar:
        Whether to attach a colorbar (default ``True``).
    """
    _render_contour(ax, fig, array, cmap=cmap, color_range=color_range,
                    levels=levels, lines=True, colorbar=colorbar)


def draw_contourf(
    ax,
    fig,
    array: np.ndarray,
    *,
    cmap: str = "viridis",
    color_range: tuple[float, float] | None = None,
    levels: int | None = None,
    colorbar: bool = True,
) -> None:
    """Draw a filled contour (no overlaid line contour) on *ax*."""
    _render_contour(ax, fig, array, cmap=cmap, color_range=color_range,
                    levels=levels, lines=False, colorbar=colorbar)


def draw_surface3d(
    ax,
    fig,
    array: np.ndarray,
    *,
    cmap: str = "viridis",
    color_range: tuple[float, float] | None = None,
    colorbar: bool = True,
) -> None:
    """Draw a 3-D surface on a 3-D *ax* (created with ``projection="3d"``)."""
    _render_surface3d(ax, fig, array, cmap=cmap, color_range=color_range,
                      colorbar=colorbar)


def draw_histogram(
    ax,
    array: np.ndarray,
    *,
    cmap: str = "viridis",
    bins: int | None = None,
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
    bins:
        Explicit bin count (default: auto from sample size).
    """
    _render_histogram(ax, array, cmap=cmap, bins=bins)


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
    colorbar: bool = True,
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

    if colorbar:
        fig.colorbar(im, ax=ax, orientation="vertical", format="%.2f")
    ax.tick_params(
        bottom=False, left=False, labelbottom=False, labelleft=False
    )


#: Default contour level count used when *levels* is not supplied.
_DEFAULT_CONTOUR_LEVELS = 12


def _render_contour(
    ax,
    fig,
    array: np.ndarray,
    *,
    cmap: str,
    color_range: tuple[float, float] | None,
    levels: int | None = None,
    lines: bool = True,
    colorbar: bool = True,
) -> None:
    """Draw a filled contour on *ax*, optionally overlaid with line contours.

    *levels* controls the number of contour bands (fixed for deterministic
    output, SPEC-17/18).  When *lines* is true a thin black line-contour is
    overlaid (the ``contour`` mode); when false only the filled bands are drawn
    (the ``contourf`` mode).
    """
    n_levels = _DEFAULT_CONTOUR_LEVELS if levels is None else int(levels)
    if n_levels < 1:
        raise InvalidParameterError(
            f"levels must be a positive integer; got {levels!r}."
        )

    rows, cols = array.shape
    x = np.arange(1, cols + 2)
    y = np.arange(1, rows + 2)
    X, Y = np.meshgrid(x[:-1] + 0.5, y[:-1] + 0.5)

    vmin = float(np.nanmin(array))
    vmax = float(np.nanmax(array))
    if color_range is not None:
        vmin, vmax = color_range[0], color_range[1]

    # Filled contour
    cf = ax.contourf(X, Y, array, levels=n_levels, cmap=cmap, vmin=vmin, vmax=vmax)
    # Optional line contour overlay
    if lines:
        ax.contour(
            X, Y, array, levels=n_levels, colors="k", linewidths=0.5, alpha=0.4
        )

    if colorbar:
        fig.colorbar(cf, ax=ax, orientation="vertical", format="%.2f")
    ax.set_aspect("auto")


def _render_surface3d(
    ax,
    fig,
    array: np.ndarray,
    *,
    cmap: str,
    color_range: tuple[float, float] | None,
    colorbar: bool = True,
) -> None:
    """Draw a 3-D surface on a 3-D *ax* (``projection="3d"``).

    The mplot3d toolkit auto-registers the ``"3d"`` projection (matplotlib
    >= 3.2), so no explicit ``import mpl_toolkits.mplot3d`` is required.  NaNs
    are filled with the data mean so ``plot_surface`` produces a continuous
    mesh instead of holes.
    """
    rows, cols = array.shape
    X, Y = np.meshgrid(np.arange(1, cols + 1), np.arange(1, rows + 1))

    # plot_surface cannot handle NaN gracefully — substitute the mean.
    z = array
    if np.any(np.isnan(z)):
        z = np.where(np.isnan(z), float(np.nanmean(z)), z)

    vmin = float(np.nanmin(array))
    vmax = float(np.nanmax(array))
    if color_range is not None:
        vmin, vmax = color_range[0], color_range[1]

    surf = ax.plot_surface(
        X, Y, z, cmap=cmap, vmin=vmin, vmax=vmax,
        linewidth=0, antialiased=False,
    )
    if colorbar:
        fig.colorbar(surf, ax=ax, orientation="vertical", format="%.2f", shrink=0.6)
    ax.set_xlabel("Column")
    ax.set_ylabel("Row")


def _render_histogram(
    ax,
    array: np.ndarray,
    *,
    cmap: str,
    bins: int | None = None,
) -> None:
    """Draw a histogram of the non-NaN cell values.

    *bins* fixes the bin count for deterministic output (SPEC-18); when
    ``None`` an automatic count derived from the sample size is used.
    """
    flat = array[~np.isnan(array)].ravel()
    if flat.size == 0:
        ax.text(
            0.5, 0.5, "No finite values to plot",
            transform=ax.transAxes, ha="center", va="center",
        )
        return

    if bins is not None:
        if int(bins) < 1:
            raise InvalidParameterError(
                f"bins must be a positive integer; got {bins!r}."
            )
        n_bins = int(bins)
    else:
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
