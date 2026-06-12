"""
map_visualizer.api.service
===========================
Single shared service layer.

**Both** the REST app (``rest.py``) and the MCP server (``mcp_server.py``)
call this module.  No render logic is duplicated here — every operation is a
thin, typed wrapper over ``map_visualizer.core``.

Inline-grid contract
--------------------
Remote clients do not share the server filesystem (strategy D4), so grids are
accepted as inline data in two formats:

1. **Whitespace-delimited text** — the native ``np.loadtxt`` format (rows of
   space/tab-separated numbers, one row per line).  Passed as a raw string.
2. **Nested JSON numbers** — a JSON array of arrays, e.g.
   ``[[1.0, 2.0], [3.0, 4.0]]``.  Detected by a leading ``[`` and converted
   to whitespace text internally before passing to ``load_array``.

The conversion happens in :func:`_coerce_grid` (private to this module).

Error contract
--------------
Core typed exceptions are re-raised unchanged.  Callers (REST layer:
``HTTPException``; MCP layer: FastMCP tool error) map them to their transport's
error format.

  ``GridLoadError`` / ``GridValidationError`` → typically HTTP 422
  ``InvalidParameterError``                   → HTTP 422
  ``RenderError``                             → HTTP 422
"""
from __future__ import annotations

import io
import json as _json

import numpy as np

from map_visualizer.core import (
    DEFAULT_MAX_CELLS,
    array_stats as _core_array_stats,
    list_colormaps as _core_list_colormaps,
    list_interpolations as _core_list_interpolations,
    load_array as _core_load_array,
    render as _core_render,
)
from map_visualizer.exceptions import (
    GridLoadError,
    GridValidationError,
    InvalidParameterError,
    RenderError,
)
from map_visualizer import __version__

__all__ = [
    "health",
    "get_colormaps",
    "get_interpolations",
    "stats_from_inline_grid",
    "render_from_inline_grid",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _coerce_grid(grid: str, max_cells: int = DEFAULT_MAX_CELLS) -> np.ndarray:
    """Parse *grid* (inline text or JSON array-of-arrays) into a 2-D ndarray.

    Parameters
    ----------
    grid:
        Either whitespace-delimited numeric text (native ``np.loadtxt`` format)
        or a JSON string whose top-level value is a list of lists of numbers.
    max_cells:
        Forwarded to :func:`~map_visualizer.core.load_array` as the size cap.

    Returns
    -------
    numpy.ndarray
        A 2-D ``float64`` array.

    Raises
    ------
    GridLoadError
        If the input cannot be parsed.
    GridValidationError
        If the parsed array violates structural constraints or exceeds
        *max_cells*.
    """
    stripped = grid.strip()
    if stripped.startswith("["):
        # Treat as JSON array-of-arrays and convert to whitespace text.
        try:
            nested = _json.loads(stripped)
        except _json.JSONDecodeError as exc:
            raise GridLoadError(
                f"grid looks like JSON but could not be parsed: {exc}"
            ) from exc
        if not isinstance(nested, list):
            raise GridLoadError(
                "JSON grid must be a list of lists of numbers (array of rows)."
            )
        lines: list[str] = []
        for row in nested:
            if not isinstance(row, list):
                raise GridLoadError(
                    "JSON grid must be a list of lists; found a non-list row."
                )
            lines.append(" ".join(str(v) for v in row))
        stripped = "\n".join(lines)

    return _core_load_array(stripped, max_cells=max_cells)


# ---------------------------------------------------------------------------
# Public service operations
# ---------------------------------------------------------------------------

def health() -> dict:
    """Return liveness status and package version.

    Returns
    -------
    dict
        ``{"status": "ok", "version": "<version>"}``
    """
    return {"status": "ok", "version": __version__}


def get_colormaps() -> list[str]:
    """Return the sorted list of all supported matplotlib colormap names.

    Returns
    -------
    list[str]
        Sorted colormap name strings.
    """
    return _core_list_colormaps()


def get_interpolations() -> list[str]:
    """Return the sorted list of all supported ``imshow`` interpolation names.

    Returns
    -------
    list[str]
        Sorted interpolation name strings.
    """
    return _core_list_interpolations()


def stats_from_inline_grid(
    grid: str,
    *,
    max_cells: int = DEFAULT_MAX_CELLS,
) -> dict:
    """Load *grid* and return statistics.

    Parameters
    ----------
    grid:
        Whitespace-delimited text rows or a JSON array-of-arrays string.
    max_cells:
        Size cap forwarded to :func:`_coerce_grid`.

    Returns
    -------
    dict
        As returned by :func:`~map_visualizer.core.array_stats`:
        ``{shape, min, max, nanmin, nanmax, mean, std, nan_count, sci_exp}``.

    Raises
    ------
    GridLoadError, GridValidationError
        On parse or structural errors.
    """
    array = _coerce_grid(grid, max_cells=max_cells)
    stats = _core_array_stats(array)
    # array_stats returns shape as a tuple; convert to list for JSON-safety.
    stats["shape"] = list(stats["shape"])
    return stats


def render_from_inline_grid(
    grid: str,
    *,
    mode: str = "heatmap",
    value_range: list[float] | None = None,
    color_range: list[float] | None = None,
    cmap: str = "viridis",
    interpolation: str = "nearest",
    profile_index: int | None = None,
    profile_axis: str = "row",
    max_cells: int = DEFAULT_MAX_CELLS,
) -> tuple[bytes, dict]:
    """Load *grid*, render headlessly, and return ``(png_bytes, stats)``.

    The core's Agg render path is headless — it never touches matplotlib.pyplot
    or any GUI backend.  The PNG bytes are suitable for:

    * REST: ``Response(content=png_bytes, media_type="image/png")``.
    * MCP: ``Image(data=png_bytes, format="png")`` (auto → ``ImageContent``).

    Parameters
    ----------
    grid:
        Whitespace-delimited text rows or a JSON array-of-arrays string.
    mode:
        Render mode: ``"heatmap"``, ``"contour"``, ``"histogram"``,
        ``"profile"``.  Default ``"heatmap"``.
    value_range:
        ``[vmin, vmax]`` clamp limits (heatmap + contour only).
    color_range:
        ``[cmin, cmax]`` colormap normalisation limits (heatmap + contour).
    cmap:
        Matplotlib colormap name.  Must be a value from :func:`get_colormaps`.
    interpolation:
        Matplotlib imshow interpolation name (heatmap mode only).
        Must be a value from :func:`get_interpolations`.
    profile_index:
        Row or column index for profile mode.  Defaults to the middle.
    profile_axis:
        ``"row"`` or ``"col"`` for profile mode.
    max_cells:
        Size cap forwarded to :func:`_coerce_grid`.

    Returns
    -------
    tuple[bytes, dict]
        ``(png_bytes, stats)`` — raw PNG bytes and the stats dict from
        :func:`stats_from_inline_grid`.

    Raises
    ------
    GridLoadError, GridValidationError
        On parse or structural errors.
    InvalidParameterError
        On unsupported mode, cmap, or interpolation.
    RenderError
        On unexpected matplotlib error during render.
    """
    array = _coerce_grid(grid, max_cells=max_cells)

    vr: tuple[float, float] | None = None
    if value_range is not None:
        vr = (float(value_range[0]), float(value_range[1]))

    cr: tuple[float, float] | None = None
    if color_range is not None:
        cr = (float(color_range[0]), float(color_range[1]))

    png_bytes = _core_render(
        array,
        mode=mode,
        value_range=vr,
        color_range=cr,
        cmap=cmap,
        interpolation=interpolation,
        profile_index=profile_index,
        profile_axis=profile_axis,
    )

    stats = _core_array_stats(array)
    stats["shape"] = list(stats["shape"])

    return png_bytes, stats
