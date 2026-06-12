"""
map_visualizer.api.rest
========================
FastAPI REST application over the shared ``service`` module.

Routes
------
GET  /health             — liveness + version.
GET  /colormaps          — list all supported colormap names.
GET  /interpolations     — list all supported interpolation names.
POST /stats              — load an inline grid and return statistics.
POST /render             — load an inline grid, render headlessly, return PNG.

Image-return contract (POST /render)
-------------------------------------
Default response: ``200 image/png`` with the raw PNG bytes as the body.
``Content-Type: image/png``.  Browsers and HTTP clients display it directly.

JSON variant: add the query parameter ``?format=base64`` (or set header
``Accept: application/json``) to receive::

    {
        "png_base64": "<base64-encoded PNG>",
        "stats": { ... }
    }

The ``?format`` parameter takes precedence over the ``Accept`` header.

Error mapping
-------------
All core typed exceptions are mapped to HTTP 422 with a structured body:

    {"detail": "<error message>", "error": "<ExceptionClassName>"}

This includes:
  ``GridLoadError`` / ``GridValidationError`` — parse/structural failures
  ``InvalidParameterError`` — bad mode / cmap / interpolation / profile_axis
  ``RenderError`` — unexpected matplotlib error

This module exposes a bare ``FastAPI`` instance (``app``).  Composition with
MCP routes happens in ``main.py`` so this module stays importable and testable
without the MCP stack.
"""
from __future__ import annotations

import base64

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from map_visualizer import __version__
from map_visualizer.exceptions import (
    GridLoadError,
    GridValidationError,
    InvalidParameterError,
    RenderError,
)
from map_visualizer.api import service

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Map-Visualizer REST API",
    version=__version__,
    description=(
        "REST interface over the Map-Visualizer headless render core. "
        "External agents can load grids, compute statistics, and render "
        "visualizations without launching the GUI. "
        "POST /render returns image/png by default; add ?format=base64 for JSON."
    ),
)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """Result of GET /health."""
    status: str
    version: str


class StatsRequest(BaseModel):
    """Body for POST /stats.

    The ``grid`` field accepts either:

    * Whitespace-delimited numeric text (rows of space/tab-separated numbers,
      one row per newline) — the native ``np.loadtxt`` format.
    * A JSON string whose top-level value is a list of lists of numbers, e.g.
      ``"[[1.0, 2.0], [3.0, 4.0]]"``.

    Remote clients must embed the grid inline; server-local paths are not
    accepted (strategy D4).
    """
    grid: str = Field(
        ...,
        description=(
            "Inline 2-D numeric grid: whitespace-delimited text rows "
            "OR a JSON array-of-arrays string."
        ),
        examples=["1.0 2.0 3.0\n4.0 5.0 6.0"],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "summary": "Whitespace-delimited text",
                    "value": {"grid": "1.0 2.0 3.0\n4.0 5.0 6.0\n7.0 8.0 9.0"},
                },
                {
                    "summary": "JSON array-of-arrays",
                    "value": {"grid": "[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]"},
                },
            ]
        }
    }


class RenderRequest(BaseModel):
    """Body for POST /render.

    The ``grid`` field follows the same inline contract as :class:`StatsRequest`.
    All render parameters are optional and default to the core's built-in defaults.
    """
    grid: str = Field(
        ...,
        description=(
            "Inline 2-D numeric grid: whitespace-delimited text rows "
            "OR a JSON array-of-arrays string."
        ),
    )
    mode: str = Field(
        default="heatmap",
        description='Render mode: "heatmap", "contour", "histogram", "profile".',
    )
    cmap: str = Field(
        default="viridis",
        description="Matplotlib colormap name (see GET /colormaps for valid values).",
    )
    interpolation: str = Field(
        default="nearest",
        description=(
            "Matplotlib imshow interpolation (heatmap mode only). "
            "See GET /interpolations for valid values."
        ),
    )
    value_range: list[float] | None = Field(
        default=None,
        description="[vmin, vmax] clamp limits (heatmap and contour modes).",
    )
    color_range: list[float] | None = Field(
        default=None,
        description="[cmin, cmax] colormap normalisation limits (heatmap and contour modes).",
    )
    profile_index: int | None = Field(
        default=None,
        description="Row or column index for profile mode. Defaults to the middle.",
    )
    profile_axis: str = Field(
        default="row",
        description='"row" (horizontal slice) or "col" (vertical slice) for profile mode.',
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "summary": "Heatmap (default)",
                    "value": {
                        "grid": "1.0 2.0 3.0\n4.0 5.0 6.0\n7.0 8.0 9.0",
                        "mode": "heatmap",
                        "cmap": "viridis",
                    },
                },
                {
                    "summary": "Contour with value range",
                    "value": {
                        "grid": "[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]",
                        "mode": "contour",
                        "cmap": "plasma",
                        "value_range": [0.0, 10.0],
                    },
                },
                {
                    "summary": "Profile (row slice)",
                    "value": {
                        "grid": "1.0 2.0 3.0\n4.0 5.0 6.0",
                        "mode": "profile",
                        "profile_axis": "row",
                        "profile_index": 0,
                    },
                },
            ]
        }
    }


# ---------------------------------------------------------------------------
# Error helpers
# ---------------------------------------------------------------------------

def _core_error_to_422(exc: Exception) -> HTTPException:
    """Map any core typed exception to HTTP 422 with a structured body."""
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"error": type(exc).__name__, "message": str(exc)},
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness and version check",
    tags=["meta"],
)
def health() -> HealthResponse:
    """Return a liveness confirmation and the package version."""
    result = service.health()
    return HealthResponse(**result)


@app.get(
    "/colormaps",
    response_model=list[str],
    summary="List all supported colormap names",
    tags=["discovery"],
)
def get_colormaps() -> list[str]:
    """Return the sorted list of all matplotlib colormap names supported by the core."""
    return service.get_colormaps()


@app.get(
    "/interpolations",
    response_model=list[str],
    summary="List all supported interpolation names",
    tags=["discovery"],
)
def get_interpolations() -> list[str]:
    """Return the sorted list of all matplotlib imshow interpolation names supported."""
    return service.get_interpolations()


@app.post(
    "/stats",
    response_model=dict,
    summary="Load an inline grid and return statistics",
    tags=["analysis"],
)
def post_stats(body: StatsRequest) -> dict:
    """Load *grid* (inline text or JSON array-of-arrays) and return statistics.

    Returns a JSON object with keys:
    ``shape``, ``min``, ``max``, ``nanmin``, ``nanmax``, ``mean``, ``std``,
    ``nan_count``, ``sci_exp``.

    Raises HTTP 422 on parse errors, structural validation errors, or if the
    grid exceeds the maximum cell count.
    """
    try:
        return service.stats_from_inline_grid(body.grid)
    except (GridLoadError, GridValidationError, InvalidParameterError, RenderError) as exc:
        raise _core_error_to_422(exc) from exc


@app.post(
    "/render",
    summary="Render an inline grid and return the PNG image",
    tags=["render"],
    responses={
        200: {
            "description": (
                "PNG image bytes (default) or JSON with base64 PNG + stats "
                "(?format=base64)."
            ),
            "content": {
                "image/png": {"schema": {"type": "string", "format": "binary"}},
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "png_base64": {"type": "string"},
                            "stats": {"type": "object"},
                        },
                    }
                },
            },
        },
        422: {"description": "Validation error (bad grid, bad mode/cmap/interpolation)."},
    },
)
def post_render(body: RenderRequest, request: Request, format: str = "png") -> Response:
    """Render *grid* headlessly via the Agg backend and return the PNG.

    **Default (``format=png``)**: returns ``200 image/png`` with the raw PNG
    bytes as the body.  The ``Content-Disposition`` header is not set, so the
    browser displays the image inline rather than downloading it.

    **JSON variant (``?format=base64``)**: returns a JSON object::

        {
            "png_base64": "<base64-encoded PNG string>",
            "stats": { "shape": [...], "min": ..., "max": ..., ... }
        }

    The ``Accept: application/json`` header is also honoured when
    ``?format`` is absent.

    Raises HTTP 422 on any core error (invalid grid, unknown mode/cmap/
    interpolation, size-cap exceeded, or unexpected render failure).
    """
    try:
        png_bytes, stats = service.render_from_inline_grid(
            body.grid,
            mode=body.mode,
            value_range=body.value_range,
            color_range=body.color_range,
            cmap=body.cmap,
            interpolation=body.interpolation,
            profile_index=body.profile_index,
            profile_axis=body.profile_axis,
        )
    except (GridLoadError, GridValidationError, InvalidParameterError, RenderError) as exc:
        raise _core_error_to_422(exc) from exc

    # Determine response format: query param takes precedence over Accept header.
    wants_json = format == "base64" or (
        format == "png"
        and "application/json" in request.headers.get("accept", "")
    )

    if wants_json:
        return JSONResponse(
            content={
                "png_base64": base64.b64encode(png_bytes).decode("ascii"),
                "stats": stats,
            }
        )

    # Default: raw PNG bytes with image/png content type.
    # Research Q2 / Finding F2.2: Response(content=..., media_type="image/png")
    # is the canonical FastAPI idiom for in-memory PNG bytes (not StreamingResponse
    # or FileResponse, which are for streaming generators and on-disk files).
    return Response(content=png_bytes, media_type="image/png")
