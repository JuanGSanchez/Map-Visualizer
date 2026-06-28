# Map-Visualizer

**Map-Visualizer** converts a 2-D numeric grid (`.txt`/`.dat`/`.csv` file with auto-detected
whitespace/comma/semicolon delimiter, or inline text/JSON over the API) into a rendered image
(PNG, SVG, or PDF). Eight visualization modes are supported: heatmap, contour, filled contour,
3-D surface, histogram, and row/column profiles. The same headless render core powers three
independent surfaces: a PySide6 desktop GUI, a REST + MCP access layer, and a packaged Windows
executable. Rendering is deterministic (byte-identical output for identical input) and
thread-safe (a module-level lock guards the matplotlib draw/serialise section).

- **Version:** 2.0.0
- **License:** GPL-3.0-or-later
- **Python:** 3.11 – 3.13
- **Author:** Juan García Sánchez

---

## Visualization modes

| Mode | Description |
|---|---|
| `heatmap` | `imshow` color map with colorbar. Supports `cmap`, `interpolation`, `value_range`, `color_range`. |
| `contour` | Filled + line contour of grid values. Supports `cmap`, `value_range`, `color_range`, `levels`. |
| `contourf` | Filled contour (no line overlay). Supports `cmap`, `value_range`, `color_range`, `levels`. |
| `surface3d` | 3-D surface plot (`projection="3d"` + `plot_surface`). Supports `cmap`, `color_range`. |
| `histogram` | Distribution of all cell values, bars colored by `cmap`. Supports `bins`. |
| `profile` | 1-D line plot of a single row or column slice. Controlled by `profile_index` and `profile_axis`. |
| `profile_row` / `profile_col` | Explicit row / column profile (axis fixed; API/MCP convenience). |

Shared render parameters: `colorbar` (toggle), `title` / `xlabel` / `ylabel` (annotations),
`output_format` (`png` / `svg` / `pdf`), and `max_render_cells` (additive render-time downsampling
for large grids). Output is deterministic — metadata stamps are stripped and a fixed `svg.hashsalt`
keeps SVG ids stable, so two renders of one input are byte-identical.

---

## Three surfaces

| Surface | Entry point | Purpose |
|---|---|---|
| PySide6 GUI | `map-visualizer-gui` | Interactive desktop application |
| REST + MCP access layer | `map-visualizer-api` / `map-visualizer-mcp` | Headless API for agents and automation |
| Packaged executable | `packaging/bin/MapVisualizer/MapVisualizer.exe` | Standalone one-dir bundle (Windows) |

The headless render core (`map_visualizer.core`) is shared by all three surfaces. It never imports
`matplotlib.pyplot` or any GUI backend, so it is safe to import in server and test contexts.

---

## Install

### GUI + core only

```bash
pip install map-visualizer
```

Installs the core library, PySide6 GUI, and the `map-visualizer-gui` entry point.

### With the access layer (REST + MCP)

```bash
pip install "map-visualizer[api]"
```

Adds FastAPI, FastMCP, and uvicorn; enables `map-visualizer-api` and `map-visualizer-mcp`.

### With development tools

```bash
pip install "map-visualizer[dev]"
```

Adds pytest, pytest-cov, and PyInstaller.

---

## Quick start

### PySide6 GUI

```bash
map-visualizer-gui
```

The application opens a file dialog. Select a `.txt`, `.dat`, or `.csv` file containing a 2-D
numeric grid (whitespace/comma/semicolon delimiter auto-detected). Once loaded:

- Use the **mode selector** to switch among heatmap, contour, filled contour, 3-D surface,
  histogram, and profile views.
- Adjust **colormap** and **interpolation** from the drop-down lists.
- Set the **value range** (clip raw values before rendering) and **color range** (colormap
  normalisation limits) independently.
- Toggle the **colorbar** and set a **title** / **axis labels** in the Annotations panel.
- **Export** the current view to PNG, SVG, or PDF (File ▸ Export image…); the format follows the
  chosen file extension.
- Hover over the map to see the pixel's column, row, and value in the stats panel.
- Choose a profile axis and index in profile mode.

**Widget help & accessibility.** Every control carries a single registry-fed info text reachable
three ways: hover (tooltip), keyboard focus / screen reader (accessible description), and
What's-This mode (Help ▸ What's This?, or **Shift+F1**). There is one centralized info surface and
one tooltip theme — no per-widget popups.

### REST + MCP access layer (HTTP)

```bash
map-visualizer-api
# Server ready at http://localhost:8000
# MCP endpoint: http://localhost:8000/mcp
# Interactive docs: http://localhost:8000/docs
```

### MCP stdio server (for Claude Desktop / local agent clients)

```bash
map-visualizer-mcp
```

MCP client configuration:

```json
{
  "mcpServers": {
    "map-visualizer": {
      "command": "map-visualizer-mcp"
    }
  }
}
```

### Packaged executable (Windows)

No Python installation required. Run `packaging/bin/MapVisualizer/MapVisualizer.exe` directly, or
distribute the entire `packaging/bin/MapVisualizer/` one-dir folder. See
[`packaging/README-packaging.md`](packaging/README-packaging.md) for rebuild instructions.

---

## Input data format

Map-Visualizer reads **whitespace-delimited 2-D numeric grids**:

- Each line is one row; values are separated by spaces or tabs.
- All rows must have the same number of values (ragged rows are rejected).
- The array must not be empty or all-NaN.
- A single-row or single-column file is accepted (promoted to a `(1, N)` or `(N, 1)` 2-D array).
- Maximum size: 4096 × 4096 cells (~16 M cells) by default.

File extensions `.txt` and `.dat` are accepted by the GUI and by `load_array` when given a file
path. Over the API, grids are submitted inline as either whitespace-delimited text or JSON
array-of-arrays.

Example grid (3 × 3, whitespace-delimited):

```
1.0 2.0 3.0
4.0 5.0 6.0
7.0 8.0 9.0
```

---

## Python version compatibility

| Boundary | Version |
|---|---|
| Minimum (source) | Python 3.11 |
| Maximum (build ceiling) | Python 3.13 |
| Packaged executable built with | Python 3.13.13 / PyInstaller 6.20 |

---

## Project layout

```
map_visualizer/
  __init__.py         — package root; re-exports the public API
  core.py             — headless render core (load_array, array_stats, render, draw_*)
  enums.py            — RenderMode enum
  exceptions.py       — typed exception hierarchy
  resources.py        — resource_path() helper (sys._MEIPASS-aware)
  gui/                — PySide6 desktop application
    app.py            — entry point (main function, map-visualizer-gui)
  api/                — REST + MCP access layer
    service.py        — shared service module
    rest.py           — FastAPI routes
    mcp_server.py     — FastMCP server + stdio entry point
    main.py           — combined ASGI app (REST + MCP Streamable HTTP)
    README-access.md  — access layer documentation
tests/                — pytest suite (150 tests, ~95% core coverage)
packaging/
  MapVisualizer.spec  — PyInstaller spec (one-dir, windowed)
  build.py / build_windows.bat / build_posix.sh — build scripts
  README-packaging.md — packaging guide
  bin/MapVisualizer/  — built executable (Windows one-dir bundle)
docs/
  agent-operating-doc.md — guide for agents driving this repo via MCP/REST
```

---

## License

GPL-3.0-or-later. See [`LICENSE`](LICENSE).
