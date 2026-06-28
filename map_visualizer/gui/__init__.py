"""
Juan García Sánchez, 2023-2026
Map-Visualizer — PySide6 GUI package (workstream b).

Entry point: ``map_visualizer.gui.app:main``
GUI script: ``map-visualizer-gui`` (declared in pyproject.toml).

This package builds the interactive PySide6 window on top of the headless
render core (``map_visualizer.core``).  The Qt UI embeds matplotlib via
``FigureCanvasQTAgg`` (the ``qtagg`` backend) and draws live onto the canvas
using the same Axes-level helpers (``draw_heatmap``, ``draw_contour``, etc.)
that the headless ``render()`` function uses — one drawing code path, two
front-ends.

No ``matplotlib.pyplot`` is imported anywhere in this package.
No ``os.getcwd()`` is used for resource resolution; all asset paths go through
``map_visualizer.resources.resource_path`` (``__file__``-relative,
``sys._MEIPASS``-aware).
"""
