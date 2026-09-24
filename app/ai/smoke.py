from __future__ import annotations

import argparse
import asyncio
import json
import time
from typing import Any

from .config import AISettings, ProviderConfig
from .providers import TypeSafeDecisionProvider, build_provider


SMOKE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
}


def _unique_provider_samples(settings: AISettings) -> list[ProviderConfig]:
    samples: dict[tuple[str, str], ProviderConfig] = {}
    for config in settings.player_providers:
        samples.setdefault((config.provider, config.model), config)
    if settings.analyst:
        samples.setdefault((settings.analyst.provider, settings.analyst.model), settings.analyst)
    return list(samples.values())


async def run_smoke(
    settings: AISettings, *, live: bool, only: str | None = None
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    samples = _unique_provider_samples(settings)
    if only:
        samples = [config for config in samples if config.provider == only]
    if not live:
        return {
            "configuration": "valid",
            "player_slots": len(settings.player_providers),
            "provider_models": sorted({f"{item.provider}:{item.model}" for item in samples}),
            "typesafe_configured": settings.typesafe is not None,
            "live_requests": False,
        }

    for config in samples:
        started = time.monotonic()
        try:
            provider = build_provider(
                config,
                timeout_seconds=settings.request_timeout_seconds,
                min_interval_seconds=0,
                reasoning_effort=settings.openai_reasoning_effort,
            )
            response = await provider.generate_json(
                system_prompt="Return only JSON matching the supplied schema.",
                user_prompt='Return {"ok": true}. This is a minimal connectivity test.',
                schema=SMOKE_SCHEMA,
                # Reasoning-capable OpenAI-compatible models may consume part
                # of this budget before emitting their short JSON answer.
                max_output_tokens=max(64, settings.max_output_tokens),
            )
            ok = response.get("ok") is True
            error = None if ok else "schema_mismatch"
        except Exception as exc:  # sanitized below; never print response bodies or keys
            ok = False
            error = str(exc) if type(exc).__name__ == "ProviderError" else type(exc).__name__
        results.append(
            {
                "provider": config.provider,
                "model": config.model,
                "ok": ok,
                "error": error,
                "elapsed_ms": round((time.monotonic() - started) * 1000),
            }
        )

    if settings.typesafe and (only is None or only == "typesafe"):
        started = time.monotonic()
        try:
            gate = TypeSafeDecisionProvider(
                settings.typesafe,
                timeout_seconds=settings.request_timeout_seconds,
                min_interval_seconds=0,
            )
            choice, confidence = await gate.choose(
                state={"purpose": "connectivity test"},
                question_id="target",
                options=["P1", "P2"],
                instructions="Choose P1 for this connectivity test.",
            )
            ok = choice in {"P1", "P2"}
            error = None if ok else "schema_mismatch"
        except Exception as exc:
            ok = False
            error = str(exc) if type(exc).__name__ == "ProviderError" else type(exc).__name__
            confidence = None
        results.append(
            {
                "provider": "typesafe",
                "model": settings.typesafe.model,
                "ok": ok,
                "error": error,
                "confidence_returned": confidence is not None,
                "elapsed_ms": round((time.monotonic() - started) * 1000),
            }
        )

    return {
        "configuration": "valid",
        "player_slots": len(settings.player_providers),
        "live_requests": True,
        "results": results,
        "all_ok": all(item["ok"] for item in results),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Palermo AI provider configuration")
    parser.add_argument("--live", action="store_true", help="Send one minimal request per provider")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument(
        "--only", choices=["gemini", "hetzner", "openai", "typesafe"], default=None
    )
    args = parser.parse_args()
    settings = AISettings.from_environment(env_file=args.env_file)
    result = asyncio.run(run_smoke(settings, live=args.live, only=args.only))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.live and not result["all_ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
