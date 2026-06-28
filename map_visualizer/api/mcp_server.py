"""
map_visualizer.api.mcp_server
==============================
FastMCP server derived from the REST FastAPI app.

This module creates the MCP server from the **same** ``rest.app`` FastAPI
application, ensuring zero logic duplication (F-single-core principle).
FastMCP introspects the FastAPI routes and auto-generates MCP tools from them.

MCP tools exposed
-----------------
health              — liveness + version (from GET /health).
get_colormaps       — list colormap names (from GET /colormaps).
get_interpolations  — list interpolation names (from GET /interpolations).
post_stats          — load inline grid and return statistics (from POST /stats).
post_render         — render inline grid and return image (from POST /render).

Image return (post_render)
--------------------------
The ``post_render`` tool is overridden with a ``@mcp.tool`` decorator that
calls ``service.render_from_inline_grid`` directly and returns
``fastmcp.utilities.types.Image(data=png_bytes, format="png")``.  FastMCP
auto-converts this to an MCP ``ImageContent`` block with
``mimeType: image/png`` and the PNG bytes base64-encoded.  MCP-aware clients
render the image inline.

Per research Finding F2.1 (gofastmcp.com/servers/tools), this is the
canonical FastMCP idiom for returning a viewable image from an MCP tool.

Transports
----------
Streamable HTTP: ``mcp_app`` (ASGI app) mounted at ``/mcp`` by ``main.py``.
stdio:           run this module directly or via the ``map-visualizer-mcp``
                 console script.

Error propagation
-----------------
FastMCP propagates HTTP 422 responses from the underlying FastAPI layer as
structured MCP tool errors (``isError: true`` with the ``detail`` field from
the 422 body), so the core's typed exception messages reach the MCP client
in a structured form with the ``error`` class name included.

The overridden ``post_render`` tool raises ``ValueError`` for core exceptions;
FastMCP surfaces this as an ``isError`` tool result with a structured message.
"""
from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.utilities.types import Image

from map_visualizer.api.rest import app as _rest_app
from map_visualizer.api import service
from map_visualizer.exceptions import (
    GridLoadError,
    GridValidationError,
    InvalidParameterError,
    RenderError,
)

# ---------------------------------------------------------------------------
# Create the MCP server from the REST app (single-core dual-interface pattern).
# FastMCP.from_fastapi() introspects the FastAPI route table and generates one
# MCP tool per route, delegating execution back to the FastAPI app.
# ---------------------------------------------------------------------------

mcp: FastMCP = FastMCP.from_fastapi(
    app=_rest_app,
    name="Map-Visualizer MCP",
)

# ASGI app for Streamable HTTP transport.
# transport="streamable-http" is set explicitly per research limitation L3.
mcp_app = mcp.http_app(path="/mcp", transport="streamable-http")


# ---------------------------------------------------------------------------
# Override post_render to return a native MCP ImageContent block.
#
# FastMCP.from_fastapi generates a tool that wraps the HTTP handler and returns
# the HTTP response body.  For the render endpoint that is a Response object
# (image/png bytes), which is not natively image-renderable by MCP clients.
#
# We override the tool with a @mcp.tool that calls the service directly and
# returns fastmcp.utilities.types.Image(data=png_bytes, format="png"), which
# FastMCP auto-converts to an ImageContent block (base64, mimeType image/png).
# Research Q2 / Finding F2.1: this is the canonical image-return idiom.
# ---------------------------------------------------------------------------

@mcp.tool(name="post_render")  # type: ignore[misc]
def post_render_image(
    grid: str,
    mode: str = "heatmap",
    cmap: str = "viridis",
    interpolation: str = "nearest",
    value_range: list[float] | None = None,
    color_range: list[float] | None = None,
    profile_index: int | None = None,
    profile_axis: str = "row",
    levels: int | None = None,
    bins: int | None = None,
    colorbar: bool = True,
) -> Image:
    """Render an inline grid headlessly and return the PNG as an MCP image block.

    Parameters
    ----------
    grid:
        Inline 2-D numeric grid: whitespace-delimited text rows OR a JSON
        array-of-arrays string, e.g. ``"[[1.0, 2.0], [3.0, 4.0]]"``.
    mode:
        Render mode: ``"heatmap"`` (default), ``"contour"``, ``"contourf"``,
        ``"surface3d"``, ``"histogram"``, ``"profile"``, ``"profile_row"``,
        ``"profile_col"``.
    levels:
        Contour band count for contour/contourf modes (default 12).
    bins:
        Histogram bin count for histogram mode (default: auto).
    colorbar:
        Whether to draw a colorbar (colorbar-bearing modes).
    cmap:
        Matplotlib colormap name (see the ``get_colormaps`` tool for valid values).
    interpolation:
        Matplotlib imshow interpolation name — only used in heatmap mode.
        See the ``get_interpolations`` tool for valid values.
    value_range:
        ``[vmin, vmax]`` clamp limits applied before render (heatmap + contour).
    color_range:
        ``[cmin, cmax]`` colormap normalisation limits (heatmap + contour).
    profile_index:
        Row or column index to plot in profile mode.  Defaults to the middle.
    profile_axis:
        ``"row"`` (horizontal slice) or ``"col"`` (vertical slice) for profile
        mode.

    Returns
    -------
    Image
        FastMCP ``Image`` wrapping the raw PNG bytes.  FastMCP auto-converts
        this to an MCP ``ImageContent`` block (base64, ``mimeType: image/png``)
        so MCP-aware clients render it inline.

    Raises MCP tool error (``isError: true``) for any core exception:
        ``GridLoadError`` / ``GridValidationError`` — bad grid input
        ``InvalidParameterError`` — unknown mode, cmap, or interpolation
        ``RenderError`` — unexpected matplotlib failure
    """
    try:
        png_bytes, _stats = service.render_from_inline_grid(
            grid,
            mode=mode,
            value_range=value_range,
            color_range=color_range,
            cmap=cmap,
            interpolation=interpolation,
            profile_index=profile_index,
            profile_axis=profile_axis,
            levels=levels,
            bins=bins,
            colorbar=colorbar,
            output_format="png",
        )
    except (GridLoadError, GridValidationError, InvalidParameterError, RenderError) as exc:
        # FastMCP surfaces raised exceptions as isError tool results.
        raise ValueError(f"{type(exc).__name__}: {exc}") from exc

    # Return as MCP ImageContent: FastMCP converts Image(data=..., format="png")
    # to { "type": "image", "data": "<base64>", "mimeType": "image/png" }.
    return Image(data=png_bytes, format="png")


# ---------------------------------------------------------------------------
# stdio entry point
# ---------------------------------------------------------------------------

def run_stdio() -> None:  # pragma: no cover
    """Run the MCP server over stdio (for CLI/agent clients).

    Invoked by the ``map-visualizer-mcp`` console script or directly::

        python -m map_visualizer.api.mcp_server
    """
    mcp.run(transport="stdio")


if __name__ == "__main__":  # pragma: no cover
    run_stdio()
