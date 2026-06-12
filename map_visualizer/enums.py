"""
Juan García Sánchez, 2023-2026
Map-Visualizer — enumeration constants for the core API.

Keep this module import-side-effect-free (no matplotlib import at module
level) so it can be imported cheaply without triggering backend selection.
"""

from __future__ import annotations

from enum import Enum


class RenderMode(str, Enum):
    """Supported visualization modes for :func:`map_visualizer.core.render`.

    Inherits ``str`` so values compare equal to plain string literals, which
    keeps the access-layer serialisation simple.

    Examples
    --------
    >>> RenderMode.HEATMAP == "heatmap"
    True
    >>> RenderMode("contour")
    <RenderMode.CONTOUR: 'contour'>
    """

    HEATMAP = "heatmap"
    """2-D imshow heatmap (default; preserves original behavior)."""

    CONTOUR = "contour"
    """Filled + line contour of the grid values."""

    HISTOGRAM = "histogram"
    """Distribution histogram of all cell values."""

    PROFILE = "profile"
    """Line plot of a single row or column slice."""

    @classmethod
    def values(cls) -> list[str]:
        """Return the list of supported mode strings."""
        return [m.value for m in cls]
