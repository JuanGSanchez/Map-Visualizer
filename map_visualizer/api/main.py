"""
map_visualizer.api.main
========================
Combined ASGI application: REST routes + MCP at ``/mcp``.

This is the **single runnable entry point** for the access layer.  It
stitches together the FastAPI REST app (``rest.app``) and the FastMCP ASGI
app (``mcp_server.mcp_app``) into one ``FastAPI`` instance served by a
single uvicorn process.

Architecture
------------
  rest.app          — the FastAPI REST app (routes: /health, /colormaps,
                      /interpolations, /stats, /render)
  mcp_server.mcp_app — the FastMCP ASGI app (Streamable HTTP at /mcp)
  app               — this module's combined app: all routes merged,
                      MCP lifespan forwarded

The MCP lifespan is forwarded to ``app`` as required by FastMCP
(it starts the internal MCP session manager).

Run commands
------------
HTTP server (REST + MCP Streamable HTTP)::

    uvicorn map_visualizer.api.main:app --host 0.0.0.0 --port 8000

or via the ``map-visualizer-api`` console script::

    map-visualizer-api

stdio MCP client::

    map-visualizer-mcp

Endpoints after startup
-----------------------
REST:
  GET  http://localhost:8000/health
  GET  http://localhost:8000/colormaps
  GET  http://localhost:8000/interpolations
  POST http://localhost:8000/stats
  POST http://localhost:8000/render
  POST http://localhost:8000/render?format=base64  (JSON variant)

MCP (Streamable HTTP):
  http://localhost:8000/mcp

Interactive docs (FastAPI auto-generated):
  http://localhost:8000/docs
  http://localhost:8000/redoc
"""
from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from map_visualizer import __version__
from map_visualizer.api.mcp_server import mcp_app
from map_visualizer.api.rest import app as _rest_app

# ---------------------------------------------------------------------------
# Combine REST routes + MCP routes in one ASGI app.
# The MCP lifespan MUST be forwarded — it starts the FastMCP session manager
# (required per research Finding F2.3 / gofastmcp.com/integrations/fastapi).
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Map-Visualizer (REST + MCP)",
    version=__version__,
    description=(
        "Combined REST + MCP access layer for the Map-Visualizer headless render core. "
        "REST routes are served directly; MCP (Streamable HTTP) is at /mcp. "
        "POST /render returns image/png (raw) or JSON+base64 (?format=base64)."
    ),
    lifespan=mcp_app.lifespan,  # REQUIRED: starts the MCP session manager
)

# Mount all routes from both apps into the combined app.
for route in mcp_app.routes:
    app.routes.append(route)
for route in _rest_app.routes:
    app.routes.append(route)


# ---------------------------------------------------------------------------
# Console-script entry points
# ---------------------------------------------------------------------------

def run_server(host: str = "0.0.0.0", port: int = 8000) -> None:  # pragma: no cover
    """Start the uvicorn server (REST + MCP Streamable HTTP).

    Invoked by the ``map-visualizer-api`` console script.
    """
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":  # pragma: no cover
    run_server()
