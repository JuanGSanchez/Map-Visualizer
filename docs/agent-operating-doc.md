# Map-Visualizer — In-Repo Agent Operating Guide

This document describes how an external agent (or any automated client) should drive the
Map-Visualizer repository via its access layer. It is the operating guide that the in-repo
Claude agent asset references.

> **In-repo agent asset:** [`.claude/agents/map-visualizer-operator.md`](../.claude/agents/map-visualizer-operator.md)
> — the `map-visualizer-operator` Claude Code subagent that drives this repo's visualization
> capability headlessly through the MCP/REST access layer described below.
> *(This asset is authored by The Metaprompter. The link will be live once that step completes.)*

---

## Table of contents

1. [What this repo does for agents](#what-this-repo-does-for-agents)
2. [Starting the access layer](#starting-the-access-layer)
3. [Available tools](#available-tools)
4. [Workflow: discovery then render](#workflow-discovery-then-render)
5. [Workflow: stats before render](#workflow-stats-before-render)
6. [Input/output reference](#inputoutput-reference)
7. [Render parameter reference](#render-parameter-reference)
8. [Image return mechanics](#image-return-mechanics)
9. [Error table](#error-table)
10. [Transport selection guide](#transport-selection-guide)
11. [What the agent does NOT control](#what-the-agent-does-not-control)

---

## What this repo does for agents

Map-Visualizer exposes a **read-only, compute-only** visualization service. There are no write
or stateful operations. An agent uses it to:

- Discover valid **colormap** and **interpolation** names (from the matplotlib registry).
- Compute **statistics** for a 2-D numeric grid (shape, min/max, mean, std, NaN count).
- **Render** a 2-D numeric grid to a PNG image in one of four visualization modes.

The service is stateless — the same inputs always produce the same output. The entire grid must
be embedded inline in each request; no shared filesystem path is accepted.

---

## Starting the access layer

Before any tool call the server must be running, or the stdio process must be launched.

### Streamable HTTP (preferred for remote / multi-client use)

```bash
pip install "map-visualizer[api]"
map-visualizer-api
# Server ready at http://localhost:8000
# MCP endpoint:       http://localhost:8000/mcp
# Interactive docs:   http://localhost:8000/docs
```

Or via uvicorn directly:

```bash
uvicorn map_visualizer.api.main:app --host 0.0.0.0 --port 8000
```

### stdio (preferred for local / single-client use)

```bash
pip install "map-visualizer[api]"
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

---

## Available tools

All five tools are available on both the Streamable HTTP MCP endpoint (`/mcp`) and the stdio MCP
server.

| MCP tool | REST equivalent | Description |
|---|---|---|
| `health` | `GET /health` | Liveness check; returns `{"status": "ok", "version": "…"}` |
| `get_colormaps` | `GET /colormaps` | Sorted list of all supported matplotlib colormap names |
| `get_interpolations` | `GET /interpolations` | Sorted list of all supported imshow interpolation names |
| `post_stats` | `POST /stats` | Load an inline grid and return statistics (JSON) |
| `post_render` | `POST /render` | Render an inline grid and return a PNG image |

---

## Workflow: discovery then render

The typical agent workflow for a render is:

1. Call `get_colormaps` to obtain valid colormap names (or use the default `"viridis"`).
2. Call `get_interpolations` to obtain valid interpolation names (heatmap mode only; or use the
   default `"nearest"`).
3. Call `post_render` with the grid, desired mode, and render parameters.

Steps 1 and 2 are optional if the agent already knows the parameter values. Colormap and
interpolation names are **case-sensitive** and must match the strings returned by the discovery
tools exactly.

### Minimal render example — heatmap with defaults

```json
// post_render input (MCP) or POST /render body (REST)
{
  "grid": "1.0 2.0 3.0\n4.0 5.0 6.0\n7.0 8.0 9.0",
  "mode": "heatmap"
}
```

REST response: `200 Content-Type: image/png` — raw PNG bytes.

MCP response: an `ImageContent` block with `mimeType: image/png` and base64-encoded PNG bytes.
MCP-aware clients display the image inline.

### Contour mode example

```json
{
  "grid": "[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]]",
  "mode": "contour",
  "cmap": "plasma",
  "value_range": [2.0, 8.0]
}
```

### Profile mode example (column slice)

```json
{
  "grid": "1.0 2.0 3.0\n4.0 5.0 6.0\n7.0 8.0 9.0",
  "mode": "profile",
  "profile_axis": "col",
  "profile_index": 1
}
```

---

## Workflow: stats before render

To inspect grid properties before committing to a render:

1. Call `post_stats` with the same grid string.
2. Use the returned `shape`, `nanmin`, `nanmax`, and `nan_count` to decide on `value_range` and
   `color_range` for the render call.
3. Call `post_render` with informed parameter choices.

### Stats example

```json
// post_stats input
{"grid": "1.0 2.0 3.0\n4.0 5.0 6.0\n7.0 8.0 9.0"}
```

```json
// post_stats output
{
  "shape": [3, 3],
  "min": 1.0,
  "max": 9.0,
  "nanmin": 1.0,
  "nanmax": 9.0,
  "mean": 5.0,
  "std": 2.58,
  "nan_count": 0,
  "sci_exp": 0
}
```

`sci_exp` is the base-10 exponent needed to bring values into a comfortable display range. It is
`0` when values are already in [0.01, 1000). Use it to decide whether to apply scientific-notation
scaling in a downstream annotation.

---

## Input/output reference

### Inline grid formats

Remote clients must embed the grid inline in the request body — no filesystem path is accepted.
Two formats are supported:

**Whitespace-delimited text** (native `np.loadtxt` format):

```
"1.0 2.0 3.0\n4.0 5.0 6.0\n7.0 8.0 9.0"
```

Each `\n` separates rows; values within a row are separated by spaces or tabs. This is the
format produced by saving a NumPy array with `np.savetxt`.

**JSON array-of-arrays**:

```
"[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]]"
```

Detected by a leading `[`. Converted to whitespace text internally before parsing. All rows must
have the same length (ragged rows raise an error).

Both formats produce identical results. The JSON form is convenient when the agent already has
the grid as a nested list in memory.

### Grid constraints

| Constraint | Detail |
|---|---|
| All rows must have the same column count | Ragged rows → `GridValidationError` |
| Array must not be empty | Zero elements → `GridValidationError` |
| Array must not be all-NaN | All-NaN → `GridValidationError` |
| Maximum size | 4096 × 4096 = ~16 M cells (default). Larger → `GridValidationError` |
| Minimum dimensions | 1 × N and N × 1 (single row or column) are accepted |

### post_stats inputs

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `grid` | string | yes | — | Inline grid in whitespace or JSON-array format |

### post_stats output

| Field | Type | Notes |
|---|---|---|
| `shape` | `[rows, cols]` | Integer list |
| `min` | float | Global minimum (may be NaN on partial-NaN arrays) |
| `max` | float | Global maximum (same caveat) |
| `nanmin` | float | NaN-ignoring minimum |
| `nanmax` | float | NaN-ignoring maximum |
| `mean` | float | NaN-ignoring mean |
| `std` | float | NaN-ignoring standard deviation |
| `nan_count` | int | Number of NaN cells |
| `sci_exp` | int | Scientific-notation exponent; 0 means no scaling needed |

### post_render inputs

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `grid` | string | yes | — | Inline grid (whitespace text or JSON array-of-arrays) |
| `mode` | string | no | `"heatmap"` | One of `"heatmap"`, `"contour"`, `"histogram"`, `"profile"` |
| `cmap` | string | no | `"viridis"` | Matplotlib colormap name; use `get_colormaps` for valid values |
| `interpolation` | string | no | `"nearest"` | imshow interpolation (heatmap mode only); use `get_interpolations` |
| `value_range` | `[vmin, vmax]` | no | `null` | Clamp raw values before rendering (heatmap + contour) |
| `color_range` | `[cmin, cmax]` | no | `null` | Colormap normalisation limits, independent of value clamp (heatmap + contour) |
| `profile_index` | int | no | `null` | Row or column index for profile mode; defaults to the middle row/column |
| `profile_axis` | string | no | `"row"` | `"row"` (horizontal slice) or `"col"` (vertical slice); profile mode only |

### post_render output

See [Image return mechanics](#image-return-mechanics) for the format differences between REST and
MCP transports.

---

## Render parameter reference

### mode

| Value | Description | Parameters honoured |
|---|---|---|
| `"heatmap"` | `imshow` grid with colorbar | `cmap`, `interpolation`, `value_range`, `color_range` |
| `"contour"` | Filled + line contour | `cmap`, `value_range`, `color_range` |
| `"histogram"` | Value distribution histogram | `cmap` (bar colours only) |
| `"profile"` | 1-D row or column slice | `profile_index`, `profile_axis` |

`interpolation` is validated and used only in heatmap mode. In all other modes it is accepted but
ignored.

### value_range vs. color_range

These two parameters are independent:

- `value_range` (`[vmin, vmax]`): clips the raw array values via `np.where` before the image is
  drawn. Values below `vmin` become `vmin`; values above `vmax` become `vmax`. Applies to heatmap
  and contour modes.
- `color_range` (`[cmin, cmax]`): sets the colormap normalisation limits (matplotlib `set_clim`).
  Changes which data values map to the ends of the colormap without altering the raw data. Applies
  to heatmap and contour modes.

Both can be set together to first clamp, then re-normalise the color scale.

### profile_index and profile_axis

For `mode="profile"`:

- `profile_axis="row"`: plots the values of a single row across all columns (x-axis = column
  index, y-axis = value).
- `profile_axis="col"`: plots the values of a single column down all rows (x-axis = value,
  y-axis = row index, inverted so row 0 is at the top).
- `profile_index`: zero-based index of the row or column to plot. If `null`, defaults to the
  middle row or column (`rows // 2` or `cols // 2`).
- Out-of-range `profile_index` raises `InvalidParameterError` (HTTP 422 / MCP isError).

---

## Image return mechanics

The image return contract differs between transports.

### REST: POST /render

**Default response** (`format=png`, which is the default):

```
200 OK
Content-Type: image/png
<raw PNG bytes>
```

The body is the raw binary PNG. Write it to a file, pass it to an image viewer, or decode it
directly.

**JSON variant** (`POST /render?format=base64` or `Accept: application/json`):

```json
{
  "png_base64": "<base64-encoded PNG string>",
  "stats": {
    "shape": [3, 3],
    "min": 1.0,
    "max": 9.0,
    "nanmin": 1.0,
    "nanmax": 9.0,
    "mean": 5.0,
    "std": 2.58,
    "nan_count": 0,
    "sci_exp": 0
  }
}
```

The `?format` query parameter takes precedence over the `Accept` header.

### MCP: post_render tool

The `post_render` MCP tool is implemented with a `@mcp.tool` override that returns a FastMCP
`Image(data=png_bytes, format="png")`. FastMCP automatically converts this to an MCP
`ImageContent` block:

```json
{
  "type": "image",
  "data": "<base64-encoded PNG>",
  "mimeType": "image/png"
}
```

MCP-aware clients (Claude Desktop, Claude Code, etc.) render this block as an inline image. The
agent does not need to decode it.

---

## Error table

All core errors map to **HTTP 422** (REST) or **`isError: true`** (MCP) with a structured body.

REST error body:

```json
{"detail": {"error": "InvalidParameterError", "message": "Unknown render mode 'surface3d'. ..."}}
```

MCP error: the tool result has `isError: true` with the same `error: ExceptionClassName: message`
format in its text content.

| Error condition | Exception class | Typical trigger |
|---|---|---|
| File not found or unsupported extension | `GridLoadError` | Path given instead of inline text, or bad `.ext` |
| Non-numeric content | `GridLoadError` | Grid text contains non-number tokens |
| JSON parse failure | `GridLoadError` | Grid starts with `[` but is not valid JSON |
| Ragged rows (unequal column counts) | `GridValidationError` | Rows have different numbers of values |
| Empty array | `GridValidationError` | Grid parses to zero elements |
| All-NaN array | `GridValidationError` | Every cell is NaN |
| Array exceeds size cap | `GridValidationError` | More than ~16 M cells |
| Unknown render mode | `InvalidParameterError` | `mode` not in `{"heatmap", "contour", "histogram", "profile"}` |
| Unknown colormap name | `InvalidParameterError` | `cmap` not in the list from `get_colormaps` |
| Unknown interpolation name | `InvalidParameterError` | `interpolation` not in the list from `get_interpolations` |
| Out-of-range profile_index | `InvalidParameterError` | Index outside `[0, rows-1]` or `[0, cols-1]` |
| Invalid profile_axis | `InvalidParameterError` | `profile_axis` not `"row"` or `"col"` |
| Unexpected matplotlib failure | `RenderError` | Internal render error; contains matplotlib error detail |

Recovery pattern for parameter errors: call the relevant discovery tool (`get_colormaps`,
`get_interpolations`) to obtain the valid value set, then retry with a corrected parameter.

---

## Transport selection guide

| Scenario | Recommended transport |
|---|---|
| Remote agent / multi-client / CI pipeline | Streamable HTTP (`map-visualizer-api`, MCP at `/mcp`) |
| Local agent / Claude Desktop / CLI tool | stdio (`map-visualizer-mcp`) |
| In-process Python test | ASGI in-process (`httpx.AsyncClient(app=app, base_url="http://test")`) |
| HTTP-native client (curl, requests, httpx) | REST endpoints directly |

---

## What the agent does NOT control

- **The GUI** (`map-visualizer-gui`) — the PySide6 desktop application is a separate entry point
  with its own interactive mode selector, hover readout, and stats panel. It is not driven via
  the API and cannot be remote-controlled through the access layer.
- **The packaged executable** (`packaging/bin/MapVisualizer/MapVisualizer.exe`) — the PyInstaller
  bundle runs the GUI only. Packaging build and rebuild are outside the agent's scope.
- **File-based grid loading** — the access layer follows an inline-grid-only contract (strategy
  D4: no shared filesystem). The agent cannot ask the server to load a file from a path on the
  server's disk.
- **The core library internals** — `render()`, `load_array()`, `array_stats()` are called
  internally by the service layer. The agent drives them only through the documented tool
  parameters; it does not call the Python API directly.
