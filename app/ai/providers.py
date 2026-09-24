from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import quote

import httpx

from .config import ProviderConfig


class ProviderError(RuntimeError):
    pass


class JsonProvider(Protocol):
    provider_name: str
    model: str

    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
        max_output_tokens: int,
    ) -> dict[str, Any]: ...


class FailoverProvider:
    def __init__(self, providers: list[JsonProvider]) -> None:
        if not providers:
            raise ValueError("FailoverProvider requires at least one provider")
        self.providers = providers
        self.provider_name = providers[0].provider_name
        self.model = providers[0].model

    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
        max_output_tokens: int,
    ) -> dict[str, Any]:
        last_error: ProviderError | None = None
        for provider in self.providers:
            try:
                return await provider.generate_json(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    schema=schema,
                    max_output_tokens=max_output_tokens,
                )
            except ProviderError as exc:
                last_error = exc
        raise ProviderError("All configured provider routes failed") from last_error


@dataclass(slots=True)
class RateGate:
    interval_seconds: float
    _lock: asyncio.Lock | None = None
    _last_request: float = 0.0

    async def wait(self) -> None:
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            remaining = self.interval_seconds - (time.monotonic() - self._last_request)
            if remaining > 0:
                await asyncio.sleep(remaining)
            self._last_request = time.monotonic()


class HttpProvider:
    def __init__(
        self,
        config: ProviderConfig,
        *,
        timeout_seconds: float,
        min_interval_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = config
        self.provider_name = config.provider
        self.model = config.model
        self.timeout_seconds = timeout_seconds
        self.gate = RateGate(min_interval_seconds)
        self.transport = transport

    async def _post(
        self, url: str, *, headers: dict[str, str], body: dict[str, Any]
    ) -> dict[str, Any]:
        await self.gate.wait()
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout_seconds, transport=self.transport
                ) as client:
                    response = await client.post(url, headers=headers, json=body)
                if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                    await asyncio.sleep(0.25 * (2**attempt))
                    continue
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise ProviderError("Provider returned a non-object response")
                return data
            except (httpx.HTTPError, ValueError, ProviderError) as exc:
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(0.25 * (2**attempt))
                    continue
        status = getattr(getattr(last_error, "response", None), "status_code", None)
        suffix = f" (HTTP {status})" if status else ""
        raise ProviderError(f"{self.provider_name} request failed{suffix}") from last_error


class GeminiProvider(HttpProvider):
    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
        max_output_tokens: int,
    ) -> dict[str, Any]:
        model = quote(self.model, safe="-_.")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        data = await self._post(
            url,
            headers={"x-goog-api-key": self.config.api_key, "content-type": "application/json"},
            body={
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseJsonSchema": schema,
                    "maxOutputTokens": max_output_tokens,
                    "temperature": 0.6,
                },
            },
        )
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(part.get("text", "") for part in parts)
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("Gemini response contained no JSON candidate") from exc
        return parse_json_object(text)


class OpenAICompatibleProvider(HttpProvider):
    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
        max_output_tokens: int,
    ) -> dict[str, Any]:
        if not self.config.base_url:
            raise ProviderError("OpenAI-compatible provider has no base URL")
        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": max_output_tokens,
            "temperature": 0.6,
        }
        body["messages"][0]["content"] += (
            "\nRequired JSON Schema:\n" + json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
        )
        if self.config.provider == "hetzner":
            # Hetzner's current Qwen reasoning route otherwise spends the full
            # completion budget on `reasoning` and returns no final `content`.
            body["chat_template_kwargs"] = {"enable_thinking": False}
        data = await self._post(
            url,
            headers={
                "authorization": f"Bearer {self.config.api_key}",
                "content-type": "application/json",
            },
            body=body,
        )
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("OpenAI-compatible response contained no content") from exc
        return parse_json_object(content)


class OpenAIResponsesProvider(HttpProvider):
    def __init__(self, *args: Any, reasoning_effort: str = "low", **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.reasoning_effort = reasoning_effort

    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
        max_output_tokens: int,
    ) -> dict[str, Any]:
        if not self.config.base_url:
            raise ProviderError("OpenAI provider has no base URL")
        data = await self._post(
            f"{self.config.base_url.rstrip('/')}/responses",
            headers={
                "authorization": f"Bearer {self.config.api_key}",
                "content-type": "application/json",
            },
            body={
                "model": self.model,
                "instructions": system_prompt,
                "input": user_prompt,
                "max_output_tokens": max_output_tokens,
                "reasoning": {"effort": self.reasoning_effort},
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "palermo_decision",
                        "strict": True,
                        "schema": schema,
                    }
                },
                "store": False,
            },
        )
        text = data.get("output_text")
        if not text:
            chunks: list[str] = []
            for item in data.get("output", []):
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        chunks.append(content.get("text", ""))
            text = "".join(chunks)
        if not text:
            raise ProviderError("OpenAI response contained no output text")
        return parse_json_object(text)


class TypeSafeDecisionProvider(HttpProvider):
    async def choose(
        self,
        *,
        state: dict[str, Any],
        question_id: str,
        options: list[str],
        instructions: str,
    ) -> tuple[str, float | None]:
        if not self.config.base_url:
            raise ProviderError("TypeSafe provider has no base URL")
        if not options:
            raise ProviderError("TypeSafe choice requires at least one option")
        criteria = {option: f"Choose {option} when it best satisfies the game objective" for option in options}
        data = await self._post(
            f"{self.config.base_url.rstrip('/')}/v1/systemone",
            headers={
                "authorization": f"Bearer {self.config.api_key}",
                "content-type": "application/json",
            },
            body={
                "model": self.model,
                "state": state,
                "questions": {
                    question_id: {
                        "type": "choice",
                        "instructions": instructions,
                        "criteria": criteria,
                    }
                },
            },
        )
        try:
            answer = data["answers"][question_id]
            choice = answer["choice"]
            confidence = answer.get("confidence")
        except (KeyError, TypeError) as exc:
            raise ProviderError("TypeSafe response contained no requested choice") from exc
        if choice not in options:
            raise ProviderError("TypeSafe returned a choice outside the legal options")
        return choice, float(confidence) if confidence is not None else None


def build_provider(
    config: ProviderConfig,
    *,
    timeout_seconds: float,
    min_interval_seconds: float,
    reasoning_effort: str = "low",
    transport: httpx.AsyncBaseTransport | None = None,
) -> JsonProvider:
    kwargs = {
        "timeout_seconds": timeout_seconds,
        "min_interval_seconds": min_interval_seconds,
        "transport": transport,
    }
    if config.provider == "gemini":
        return GeminiProvider(config, **kwargs)
    if config.provider in {"hetzner", "litellm"}:
        return OpenAICompatibleProvider(config, **kwargs)
    if config.provider == "openai":
        return OpenAIResponsesProvider(config, reasoning_effort=reasoning_effort, **kwargs)
    raise ProviderError(f"No JSON provider adapter for {config.provider}")


def build_failover_provider(
    primary: ProviderConfig,
    fallbacks: tuple[ProviderConfig, ...],
    *,
    timeout_seconds: float,
    min_interval_seconds: float,
    reasoning_effort: str = "low",
) -> JsonProvider:
    configs = (primary, *fallbacks)
    providers = [
        build_provider(
            config,
            timeout_seconds=timeout_seconds,
            min_interval_seconds=min_interval_seconds,
            reasoning_effort=reasoning_effort,
        )
        for config in configs
        if config.provider != "typesafe"
    ]
    return FailoverProvider(providers)


def parse_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        raise ProviderError("Provider output is not JSON text")
    text = value.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProviderError("Provider output is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ProviderError("Provider JSON output must be an object")
    return parsed
