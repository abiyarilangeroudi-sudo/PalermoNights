"""Cloudflare Worker entrypoint for the FastAPI backend and Frontend assets."""

from fastapi import Request
from fastapi.responses import Response
from workers import asgi

from app.main import app


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
