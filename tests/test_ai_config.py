from __future__ import annotations

import pytest

from app.ai.config import AISettings, ConfigurationError


def complete_env() -> dict[str, str]:
    env = {
        "LLM_PROVIDER": "pool",
        "GEMINI_MODEL": "gemini-test",
        "HETZNER_BASE_URL": "https://inference.example/v1",
        "HETZNER_MODEL": "qwen-test",
        "OPENAI_BASE_URL": "https://api.example/v1",
        "OPENAI_API_KEY": "openai-secret",
        "OPENAI_ANALYST_MODEL": "analyst-test",
        "TYPESAFE_API_KEY": "typesafe-secret",
        "TYPESAFE_MODEL": "jev-test",
        "LLM_MIN_REQUEST_INTERVAL_SECONDS": "0",
    }
    env.update({f"GEMINI_API_KEY_{index}": f"gemini-secret-{index}" for index in range(1, 7)})
    env.update({f"HETZNER_API_KEY_{index}": f"hetzner-secret-{index}" for index in range(1, 4)})
    return env


def test_pool_builds_seven_balanced_slots_without_exposing_secrets():
    settings = AISettings.from_environment(environ=complete_env())
    assert len(settings.player_providers) == 7
    assert {config.provider for config in settings.player_providers} == {"gemini", "hetzner"}
    assert settings.analyst is not None
    assert settings.typesafe is not None
    assert "secret" not in repr(settings.player_providers[0])


def test_pool_rejects_insufficient_capacity():
    env = complete_env()
    for index in range(2, 7):
        env.pop(f"GEMINI_API_KEY_{index}")
    for index in range(2, 4):
        env.pop(f"HETZNER_API_KEY_{index}")
    with pytest.raises(ConfigurationError, match="seven"):
        AISettings.from_environment(environ=env)


def test_openai_luna_pool_reuses_one_key_without_exposing_it():
    settings = AISettings.for_openai_players(
        player_count=6,
        environ={
            "OPENAI_API_KEY": "openai-secret",
            "OPENAI_PLAYER_MODEL": "gpt-5.6-luna",
            "OPENAI_BASE_URL": "https://api.example/v1",
        },
    )

    assert len(settings.player_providers) == 6
    assert {config.model for config in settings.player_providers} == {"gpt-5.6-luna"}
    assert {config.provider for config in settings.player_providers} == {"openai"}
    assert settings.max_output_tokens == 4096
    assert settings.speak_max_output_tokens == 4096
    assert "openai-secret" not in repr(settings)
