"""
map_visualizer.api
==================
Agent-access layer for the Map-Visualizer package.

Exposes the headless render core (``map_visualizer.core``) through two
front-doors — a FastAPI REST app and a FastMCP MCP server — over a
**single shared service implementation**.  No render logic lives here;
all computation is delegated to the core.

Importing this package does NOT require the GUI dependencies (PySide6).
The ``api`` optional-dependency group must be installed to run the server::

    pip install "map-visualizer[api]"

Sub-modules
-----------
service    — thin typed wrappers over the core; both REST and MCP call this.
rest       — FastAPI application (REST surface: /health, /colormaps,
             /interpolations, /stats, /render).
mcp_server — FastMCP server: Streamable HTTP + stdio entry point + image override.
main       — combined ASGI app (REST routes + MCP at ``/mcp``); uvicorn entry.
"""
