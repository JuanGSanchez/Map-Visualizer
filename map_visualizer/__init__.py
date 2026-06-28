"""
map_visualizer — headless render core for Map-Visualizer.

Public API
----------
The following names are the stable, documented surface of this package.
All other names are internal and may change without notice.

Functions
~~~~~~~~~
load_array(source, *, max_cells=DEFAULT_MAX_CELLS) -> numpy.ndarray
    Load a whitespace-delimited 2-D numeric grid from a file path,
    file-like object, or raw text string.  Raises typed errors for all
    structural problems (ragged rows, empty input, all-NaN, size cap).

array_stats(array) -> dict
    Compute lightweight statistics (shape, min/max/nanmin/nanmax/mean/std,
    nan_count, sci_exp) for a 2-D array.

render(array, *, mode="heatmap", value_range=None, color_range=None,
       cmap="viridis", interpolation="nearest",
       profile_index=None, profile_axis="row") -> bytes
    Render *array* headlessly via the Agg backend and return raw PNG bytes.
    mode must be one of: "heatmap", "contour", "histogram", "profile".

list_colormaps() -> list[str]
    Return all supported matplotlib colormap names.

list_interpolations() -> list[str]
    Return all supported matplotlib imshow interpolation names.

Enumerations
~~~~~~~~~~~~
RenderMode
    String enum whose values are the supported mode strings.

Exceptions
~~~~~~~~~~
MapVisualizerError   — base
GridLoadError        — file / parse failure
GridValidationError  — structural validation failure (subclass of GridLoadError)
RenderError          — matplotlib render failure
InvalidParameterError — unsupported parameter value
"""

from .core import (
    DEFAULT_MAX_CELLS,
    apply_value_range,
    array_stats,
    draw_contour,
    draw_contourf,
    draw_heatmap,
    draw_histogram,
    draw_profile,
    draw_surface3d,
    list_colormaps,
    list_interpolations,
    load_array,
    render,
)
from .enums import RenderMode
from .exceptions import (
    GridLoadError,
    GridValidationError,
    InvalidParameterError,
    MapVisualizerError,
    RenderError,
)
from .resources import resource_path

__all__ = [
    # Core functions
    "load_array",
    "array_stats",
    "render",
    "list_colormaps",
    "list_interpolations",
    "apply_value_range",
    # Public Axes-level drawing helpers (shared by Qt UI and Agg render path)
    "draw_heatmap",
    "draw_contour",
    "draw_contourf",
    "draw_surface3d",
    "draw_histogram",
    "draw_profile",
    # Constants
    "DEFAULT_MAX_CELLS",
    # Enums
    "RenderMode",
    # Exceptions
    "MapVisualizerError",
    "GridLoadError",
    "GridValidationError",
    "RenderError",
    "InvalidParameterError",
    # Utilities
    "resource_path",
]

__version__ = "2.0.0"
__author__ = "Juan García Sánchez"
__license__ = "GPLv3"
