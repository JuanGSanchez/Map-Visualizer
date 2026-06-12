"""
Juan García Sánchez, 2023-2026
Map-Visualizer — typed exception hierarchy for the core package.
"""

# ---------------------------------------------------------------------------
# Public exception hierarchy
# ---------------------------------------------------------------------------

class MapVisualizerError(Exception):
    """Base exception for all map_visualizer errors."""


class GridLoadError(MapVisualizerError):
    """Raised when a grid file or text cannot be loaded into a valid 2-D array.

    Attributes
    ----------
    reason : str
        Human-readable description of what went wrong.
    """

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class GridValidationError(GridLoadError):
    """Raised when the loaded array fails a structural validation check
    (ragged rows, empty input, all-NaN values, size cap exceeded, etc.).
    """


class RenderError(MapVisualizerError):
    """Raised when a render call cannot be completed due to bad parameters
    or an internal matplotlib error.
    """


class InvalidParameterError(MapVisualizerError):
    """Raised when a caller passes an unsupported value for a named parameter
    (e.g. an unknown ``mode``, ``cmap``, or ``interpolation``).
    """
