"""Offline-only browser reproduction server, with a delayed action response.

Run from the repository root:
  PYTHONPATH=. .venv/bin/python audit/2026-10-02/serve_delayed.py
Open http://127.0.0.1:8017/ui/, start a game and submit a role claim.
For a human Mafia Boss, the same race can happen after selecting a strategy.
Stop with Ctrl-C. No production source is modified and no remote AI is called.
"""
import asyncio
from unittest.mock import patch

import uvicorn

from app.ai.config import ConfigurationError
from app.main import app


@app.middleware("http")
async def delay_action_response(request, call_next):
    response = await call_next(request)
    if request.url.path.endswith("/interactive/action"):
        await asyncio.sleep(1.5)
    return response


if __name__ == "__main__":
    with patch("app.main.AISettings.for_openai_players", side_effect=ConfigurationError("Offline audit")), \
         patch("app.ai.service._write_audit_record"):
        uvicorn.run(app, host="127.0.0.1", port=8017, log_level="warning")
