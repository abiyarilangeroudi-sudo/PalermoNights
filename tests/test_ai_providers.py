from __future__ import annotations

import json

import httpx
import pytest

from app.ai.config import ProviderConfig
from app.ai.providers import (
    FailoverProvider,
    GeminiProvider,
    OpenAICompatibleProvider,
    OpenAIResponsesProvider,
    TypeSafeDecisionProvider,
)


SCHEMA = {
    "type": "object",
    "properties": {"action": {"type": "string"}},
    "required": ["action"],
}


class AlwaysFails:
    provider_name = "failing"
    model = "failing"

    async def generate_json(self, **_):
        from app.ai.providers import ProviderError

        raise ProviderError("expected")


class AlwaysWorks:
    provider_name = "working"
    model = "working"

    async def generate_json(self, **_):
        return {"action": "PASS"}


@pytest.mark.anyio
async def test_failover_provider_uses_next_route():
    provider = FailoverProvider([AlwaysFails(), AlwaysWorks()])
    result = await provider.generate_json(
        system_prompt="", user_prompt="", schema=SCHEMA, max_output_tokens=10
    )
    assert result == {"action": "PASS"}


@pytest.mark.anyio
async def test_gemini_adapter_sends_schema_and_parses_json():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-goog-api-key"] == "secret"
        body = json.loads(request.content)
        assert body["generationConfig"]["responseJsonSchema"] == SCHEMA
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": '{"action":"PASS"}'}]}}]},
        )

    provider = GeminiProvider(
        ProviderConfig("gemini", "gemini-test", "secret"),
        timeout_seconds=1,
        min_interval_seconds=0,
        transport=httpx.MockTransport(handler),
    )
    result = await provider.generate_json(
        system_prompt="system", user_prompt="user", schema=SCHEMA, max_output_tokens=20
    )
    assert result == {"action": "PASS"}


@pytest.mark.anyio
async def test_openai_compatible_adapter():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert json.loads(request.content)["chat_template_kwargs"]["enable_thinking"] is False
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"action":"SPEAK"}'}}]},
        )

    provider = OpenAICompatibleProvider(
        ProviderConfig("hetzner", "qwen-test", "secret", "https://example.test/v1"),
        timeout_seconds=1,
        min_interval_seconds=0,
        transport=httpx.MockTransport(handler),
    )
    result = await provider.generate_json(
        system_prompt="system", user_prompt="user", schema=SCHEMA, max_output_tokens=20
    )
    assert result["action"] == "SPEAK"


@pytest.mark.anyio
async def test_openai_responses_adapter_uses_structured_outputs():
    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["text"]["format"]["type"] == "json_schema"
        assert body["store"] is False
        return httpx.Response(
            200,
            json={
                "output": [
                    {"content": [{"type": "output_text", "text": '{"action":"PASS"}'}]}
                ]
            },
        )

    provider = OpenAIResponsesProvider(
        ProviderConfig("openai", "gpt-test", "secret", "https://example.test/v1"),
        timeout_seconds=1,
        min_interval_seconds=0,
        transport=httpx.MockTransport(handler),
    )
    result = await provider.generate_json(
        system_prompt="system", user_prompt="user", schema=SCHEMA, max_output_tokens=20
    )
    assert result["action"] == "PASS"


@pytest.mark.anyio
async def test_typesafe_choice_adapter():
    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["questions"]["target"]["type"] == "choice"
        return httpx.Response(
            200,
            json={"answers": {"target": {"choice": "P4", "confidence": 0.82}}},
        )

    provider = TypeSafeDecisionProvider(
        ProviderConfig("typesafe", "jev-test", "secret", "https://example.test"),
        timeout_seconds=1,
        min_interval_seconds=0,
        transport=httpx.MockTransport(handler),
    )
    choice, confidence = await provider.choose(
        state={"round": 2},
        question_id="target",
        options=["P3", "P4"],
        instructions="Choose a legal target",
    )
    assert choice == "P4"
    assert confidence == 0.82
