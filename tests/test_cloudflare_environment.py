from __future__ import annotations

from fastapi import Request

from app.ai.config import AISettings
from app.main import request_ai_environment


class CloudflareBindings:
    OPENAI_API_KEY = "worker-secret"
    OPENAI_PLAYER_MODEL = "worker-model"


def test_cloudflare_ai_bindings_are_available_to_settings():
    request = Request({"type": "http", "env": CloudflareBindings()})

    environment = request_ai_environment(request)

    assert environment is not None
    settings = AISettings.for_openai_players(
        player_count=6,
        env_file=None,
        environ=environment,
    )
    assert settings.provider_mode == "openai-luna"
    assert len(settings.player_providers) == 6
    assert settings.player_providers[0].api_key == "worker-secret"
    assert settings.player_providers[0].model == "worker-model"


def test_local_request_keeps_dotenv_loading_available():
    request = Request({"type": "http"})

    assert request_ai_environment(request) is None
