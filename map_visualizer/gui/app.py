"""
Juan García Sánchez, 2023-2026
Map-Visualizer — PySide6 GUI application entry point (workstream b).

Entry point: ``map-visualizer-gui`` (gui-script in pyproject.toml)
             calls  ``map_visualizer.gui.app:main``.

Design notes
------------
* ``QT_API=PySide6`` is set as early as possible (before matplotlib is
  imported) so matplotlib's backend auto-detection always picks PySide6.
* No ``matplotlib.pyplot`` is imported here or in any gui sub-module.
* All resource paths go through ``map_visualizer.resources.resource_path``
  (``__file__``-relative, ``sys._MEIPASS``-aware) — never ``os.getcwd()``.
* High-DPI is handled via the Qt 6 default (enabled automatically; the old
  ``AA_EnableHighDpiScaling`` attribute was removed in Qt 6).
"""

from __future__ import annotations

import logging
import os
import sys

# ---------------------------------------------------------------------------
# Bind matplotlib's Qt backend to PySide6 before any matplotlib import.
# ---------------------------------------------------------------------------
os.environ.setdefault("QT_API", "PySide6")

from PySide6.QtWidgets import QApplication

from map_visualizer.gui.main_window import MainWindow

log = logging.getLogger(__name__)


def main() -> None:
    """Launch the Map-Visualizer PySide6 GUI.

    This is the function wired as the ``map-visualizer-gui`` gui-script entry
    point in ``pyproject.toml``.
    """
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Map-Visualizer")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("JuanGSanchez")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
