"""Cloudflare Worker entrypoint for the FastAPI backend and Frontend assets."""

import os
import asyncio
import time
import json

from fastapi import Request
from fastapi.responses import Response
from workers import DurableObject, WorkerEntrypoint, asgi

# The regular FastAPI server mounts Frontend/ from its local filesystem. Workers
# serves those files through the ASSETS binding instead, so disable that mount
# before importing the application and registering its routes.
os.environ["PALERMO_CLOUDFLARE_WORKER"] = "1"

from app.main import app, runtime, ai_runs, AI_ENVIRONMENT_NAMES  # noqa: E402
from app.cloud_store import CloudStore
from app.ai import service as ai_service  # noqa: E402

@app.get("/health/ai-config")
async def ai_config_health(request: Request):
    """Report whether production AI bindings exist without exposing their values."""
    env = request.scope.get("env")
    api_key = getattr(env, "OPENAI_API_KEY", None) if env is not None else None
    model = getattr(env, "OPENAI_PLAYER_MODEL", None) if env is not None else None
    return {
        "release": "2026-10-04-cloud-library",
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
    """Durable checkpoints and bounded alarm-driven turns for the game server."""

    def __init__(self, ctx, env):
        super().__init__(ctx, env)
        self.storage = ctx.storage
        self.ready = False
        self.init_lock = asyncio.Lock()
        self.alarm_lock = asyncio.Lock()

    async def initialize(self):
        async with self.init_lock:
            if self.ready:
                return
            for name in (*AI_ENVIRONMENT_NAMES, "PALERMO_PLAY_KEY", "PALERMO_REVIEW_KEY", "PALERMO_MAX_ACTIVE_GAMES",
                         "PALERMO_MAX_ACTIVE_PER_CLIENT", "PALERMO_MAX_ACTIVE_LIVE",
                         "PALERMO_GAMES_PER_HOUR", "PALERMO_TOTAL_GAMES_PER_HOUR",
                         "PALERMO_LIVE_GAMES_PER_DAY", "PALERMO_DECISIONS_PER_AGENT"):
                value = getattr(self.env, name, None)
                if value is not None:
                    os.environ[name] = str(value)
            runtime.external_scheduler = True
            runtime.store = CloudStore(self.storage.sql)
            ai_service._write_audit_record = runtime.store.audit
            # One named object owns this app. Keep its existing namespace for compatibility.
            for value in runtime.store.all():
                if value['game']['game_id'] not in runtime.games._games:
                    runtime.restore(value)
            self.ready = True

    async def arm(self):
        from datetime import datetime
        from app.admission import limit
        active = [r for r in ai_runs._runs.values() if r.status in {'RUNNING', 'QUEUED', 'WAITING_FOR_HUMAN'}]
        if not active:
            await self.storage.deleteAlarm()
            return
        now = int(time.time() * 1000)
        when = now + 100 if any(r.status in {'RUNNING', 'QUEUED'} for r in active) else max(now + 1000, int(min(datetime.fromisoformat(r.created_at).timestamp() for r in active) * 1000) + limit('PALERMO_GAME_TTL_SECONDS', 86400) * 1000)
        previous = await self.storage.getAlarm()
        if previous is None or previous > when:
            await self.storage.setAlarm(when)

    async def fetch(self, request):
        await self.initialize()
        # Persist a wake-up before accepting mutations; a lost HTTP response is recoverable.
        if request.method == "POST":
            await self.storage.setAlarm(int(time.time() * 1000) + 1000)
        try:
            return await asgi.fetch(app, request.js_object, self.env)
        finally:
            await self.arm()

    async def alarm(self, alarm_info=None):
        await self.initialize()
        async with self.alarm_lock:
            await runtime.expire()
            runnable = [r for r in ai_runs._runs.values() if r.status in {'RUNNING', 'QUEUED'}]
            if runnable:
                # A persisted watchdog survives eviction during the provider request.
                await self.storage.setAlarm(int(time.time() * 1000) + 120000)
                run = min(runnable, key=lambda r: r.last_progress_at or r.created_at)
                await ai_service.execute_run(run, run.runner, batch_steps=1)
            await self.arm()


class Default(WorkerEntrypoint):
    """Route every request through the singleton stateful game server."""

    async def fetch(self, request):
        server = self.env.GAME_SERVER.getByName("palermo-nights")
        return await server.fetch(request.js_object)
