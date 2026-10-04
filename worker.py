"""Cloudflare Worker entrypoint for the FastAPI backend and Frontend assets."""

import os

from fastapi import Request
from fastapi.responses import Response
from workers import DurableObject, WorkerEntrypoint, asgi

# The regular FastAPI server mounts Frontend/ from its local filesystem. Workers
# serves those files through the ASSETS binding instead, so disable that mount
# before importing the application and registering its routes.
os.environ["PALERMO_CLOUDFLARE_WORKER"] = "1"

from app.main import app  # noqa: E402
from app.ai import service as ai_service  # noqa: E402

# A Worker has no writable project filesystem. Audit events remain available in
# Cloudflare logs; local FastAPI deployments keep their JSONL audit files.
ai_service._write_audit_record = lambda _game_id, _record: None


@app.get("/health/ai-config")
async def ai_config_health(request: Request):
    """Report whether production AI bindings exist without exposing their values."""
    env = request.scope.get("env")
    api_key = getattr(env, "OPENAI_API_KEY", None) if env is not None else None
    model = getattr(env, "OPENAI_PLAYER_MODEL", None) if env is not None else None
    return {
        "release": "cloudflare-ai-bindings-v2",
        "openai_api_key_configured": bool(api_key),
        "openai_player_model_configured": bool(model),
    }


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


class GameServer(DurableObject):
    """Keep the stateful FastAPI game runtime on one Cloudflare isolate."""

    async def fetch(self, request):
        return await asgi.fetch(app, request.js_object, self.env)


class Default(WorkerEntrypoint):
    """Route every request through the singleton stateful game server."""

    async def fetch(self, request):
        server = self.env.GAME_SERVER.getByName("palermo-nights")
        return await server.fetch(request.js_object)
