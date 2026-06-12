"""
Juan García Sánchez, 2023-2026
Map-Visualizer — resource-path helper (R-1 fix).

This module provides a single utility, ``resource_path``, that resolves
asset paths correctly in three runtime contexts:

1. Normal development / source-tree launch (uses ``__file__``-relative
   resolution).
2. Launch from an arbitrary working directory (uses ``__file__``, NOT
   ``os.getcwd()``  — the original defect R-1).
3. A frozen PyInstaller bundle (uses ``sys._MEIPASS`` — the temporary
   extraction directory that PyInstaller sets at bundle startup).
"""

from __future__ import annotations

import os
import sys


# The directory that contains this file at source time.
# If frozen by PyInstaller, ``sys._MEIPASS`` points to the unpacked bundle
# directory and takes precedence.
def _base_dir() -> str:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS  # type: ignore[attr-defined]
    # Walk up one level: resources.py lives inside the package; assets are
    # in the repository root (the parent of the package directory).
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(relative: str) -> str:
    """Return the absolute path to *relative*, resolved from the correct base.

    Parameters
    ----------
    relative:
        Path relative to the project / bundle root (e.g. ``"Logo MVis.png"``).

    Returns
    -------
    str
        Absolute path that is valid whether the app is run from source or as a
        frozen PyInstaller executable.

    Examples
    --------
    >>> from map_visualizer.resources import resource_path
    >>> path = resource_path("Logo MVis.png")
    """
    return os.path.join(_base_dir(), relative)
