"""Cloudflare Worker entrypoint for the FastAPI backend and Frontend assets."""

import os

from fastapi import Request
from fastapi.responses import Response
from workers import asgi

# The regular FastAPI server mounts Frontend/ from its local filesystem. Workers
# serves those files through the ASSETS binding instead, so disable that mount
# before importing the application and registering its routes.
os.environ["PALERMO_CLOUDFLARE_WORKER"] = "1"

from app.main import app  # noqa: E402


def _frontend_asset_path(path: str) -> str:
    """Translate the app's historical /ui/* URLs to Frontend asset URLs."""
    normalized = path.lstrip("/")
    if normalized == "ui":
        return "/index.html"
    if normalized.startswith("ui/"):
        normalized = normalized[3:]
    return f"/{normalized}" if normalized else "/index.html"


@app.api_route("/{path:path}", methods=["GET", "HEAD"])
async def frontend(path: str, request: Request):
    """Serve Frontend files through the Workers Static Assets binding."""
    env = request.scope["env"]
    asset_url = f"https://assets.local{_frontend_asset_path(path)}"
    asset_response = await env.ASSETS.fetch(asset_url)
    body = await asset_response.bytes()
    return Response(
        content=body,
        status_code=asset_response.status,
        headers=asset_response.headers,
    )


Default = asgi.entrypoint(app)
