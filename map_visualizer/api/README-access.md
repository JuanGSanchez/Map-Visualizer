# Map-Visualizer — Agent Access Layer

Single shared service module (`service.py`) exposed as **REST** (FastAPI) and **MCP**
(FastMCP) over ONE shared core.  External agents can drive the headless render pipeline
without launching the PySide6 GUI.

## Install

```
pip install "map-visualizer[api]"
```

## Start the server (REST + MCP Streamable HTTP)

```
map-visualizer-api
# or:
uvicorn map_visualizer.api.main:app --host 0.0.0.0 --port 8000
```

## Start the MCP stdio server

```
map-visualizer-mcp
# or:
python -m map_visualizer.api.mcp_server
```

## REST endpoints

| Method | Path              | Description                                                 |
|--------|-------------------|-------------------------------------------------------------|
| GET    | `/health`         | Liveness check — returns `{"status": "ok", "version": …}`. |
| GET    | `/colormaps`      | Sorted list of all supported matplotlib colormap names.     |
| GET    | `/interpolations` | Sorted list of all supported imshow interpolation names.    |
| POST   | `/stats`          | Load an inline grid and return statistics (JSON).           |
| POST   | `/render`         | Render an inline grid — returns `image/png` by default.     |
| POST   | `/render?format=base64` | JSON variant: `{"png_base64": "…", "stats": {…}}`. |

Interactive docs: http://localhost:8000/docs

## MCP tools (over the same core)

| Tool               | Equivalent REST    | Description                               |
|--------------------|--------------------|-------------------------------------------|
| `health`           | GET /health        | Liveness + version.                       |
| `get_colormaps`    | GET /colormaps     | List colormap names.                      |
| `get_interpolations` | GET /interpolations | List interpolation names.              |
| `post_stats`       | POST /stats        | Load inline grid → JSON statistics.       |
| `post_render`      | POST /render       | Render inline grid → MCP ImageContent.    |

MCP endpoint (Streamable HTTP): `http://localhost:8000/mcp`

## Inline grid format

Remote clients embed the grid in the request body (strategy D4 — no shared filesystem).
Two formats are accepted:

**Whitespace-delimited text (native np.loadtxt format):**
```
"1.0 2.0 3.0\n4.0 5.0 6.0\n7.0 8.0 9.0"
```

**JSON array-of-arrays:**
```
"[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]]"
```

## Example: POST /stats

```
POST /stats
Content-Type: application/json

{"grid": "1.0 2.0 3.0\n4.0 5.0 6.0\n7.0 8.0 9.0"}
```

Response:
```json
{"shape": [3, 3], "min": 1.0, "max": 9.0, "nanmin": 1.0, "nanmax": 9.0,
 "mean": 5.0, "std": 2.58, "nan_count": 0, "sci_exp": 0}
```

## Example: POST /render (PNG response)

```
POST /render
Content-Type: application/json

{
  "grid": "1.0 2.0 3.0\n4.0 5.0 6.0\n7.0 8.0 9.0",
  "mode": "heatmap",
  "cmap": "viridis"
}
```

Response: `200 Content-Type: image/png` — raw PNG bytes.

## Example: POST /render?format=base64 (JSON response)

```
POST /render?format=base64
Content-Type: application/json

{"grid": "[[1.0, 2.0], [3.0, 4.0]]", "mode": "contour", "cmap": "plasma"}
```

Response:
```json
{
  "png_base64": "<base64-encoded PNG>",
  "stats": {"shape": [2, 2], "min": 1.0, "max": 4.0, ...}
}
```

## Render modes

| Mode        | Description                                                         |
|-------------|---------------------------------------------------------------------|
| `heatmap`   | `imshow` heatmap with colorbar (default). Uses `cmap`, `interpolation`, `value_range`, `color_range`. |
| `contour`   | Filled + line contour. Uses `cmap`, `value_range`, `color_range`.  |
| `histogram` | Distribution of grid values. Uses `cmap`.                          |
| `profile`   | Row or column 1-D slice. Uses `profile_index`, `profile_axis`.     |

## Error handling

All core errors map to **HTTP 422** with a structured body:

```json
{"detail": {"error": "InvalidParameterError", "message": "Unknown render mode 'surface3d'. ..."}}
```

MCP tool errors surface as `isError: true` with the same message format.

## Dependency versions

See `requirements-access.txt` and `pyproject.toml` `[project.optional-dependencies] api`.

- fastmcp `>=3.4,<4` (3.4.2)
- fastapi `>=0.136,<1` (0.136.3)
- uvicorn `>=0.49,<1` (0.49.0)
