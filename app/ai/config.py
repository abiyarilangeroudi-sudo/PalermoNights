from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv


class ConfigurationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    provider: str
    model: str
    api_key: str = field(repr=False)
    base_url: str | None = None


@dataclass(frozen=True, slots=True)
class AISettings:
    provider_mode: str
    player_providers: tuple[ProviderConfig, ...]
    fallback_providers: tuple[ProviderConfig, ...]
    analyst: ProviderConfig | None
    typesafe: ProviderConfig | None
    min_request_interval_seconds: float = 8.0
    max_output_tokens: int = 180
    speak_max_output_tokens: int = 512
    request_timeout_seconds: float = 180.0
    decision_timeout_seconds: float = 45.0
    typesafe_decision_timeout_seconds: float = 15.0
    analyst_max_output_tokens: int = 700
    openai_reasoning_effort: str = "low"

    @classmethod
    def from_environment(
        cls,
        *,
        env_file: str | Path | None = ".env",
        environ: Mapping[str, str] | None = None,
    ) -> "AISettings":
        if environ is None:
            if env_file is not None:
                load_dotenv(Path(env_file), override=False)
            source: Mapping[str, str] = os.environ
        else:
            source = environ

        def value(name: str, default: str | None = None) -> str | None:
            raw = source.get(name, default)
            return raw.strip() if isinstance(raw, str) else raw

        def positive_float(name: str, default: str) -> float:
            try:
                result = float(value(name, default) or default)
            except ValueError as exc:
                raise ConfigurationError(f"{name} must be a number") from exc
            if result < 0:
                raise ConfigurationError(f"{name} must be non-negative")
            return result

        def positive_int(name: str, default: str) -> int:
            try:
                result = int(value(name, default) or default)
            except ValueError as exc:
                raise ConfigurationError(f"{name} must be an integer") from exc
            if result <= 0:
                raise ConfigurationError(f"{name} must be positive")
            return result

        gemini_model = value("GEMINI_MODEL")
        hetzner_model = value("HETZNER_MODEL")
        hetzner_base = value("HETZNER_BASE_URL")
        gemini = cls._numbered_configs(source, "GEMINI_API_KEY", "gemini", gemini_model)
        hetzner = cls._numbered_configs(
            source, "HETZNER_API_KEY", "hetzner", hetzner_model, hetzner_base
        )

        mode = value("LLM_PROVIDER", "pool") or "pool"
        if mode not in {"pool", "gemini", "hetzner", "litellm"}:
            raise ConfigurationError(f"Unsupported LLM_PROVIDER: {mode}")

        if mode == "pool":
            selected = cls._balanced_player_pool(gemini, hetzner)
            fallbacks = tuple(config for config in (*gemini, *hetzner) if config not in selected)
        elif mode == "gemini":
            selected, fallbacks = cls._take_seven(gemini)
        elif mode == "hetzner":
            selected, fallbacks = cls._take_seven(hetzner)
        else:
            lite_key = value("LITELLM_API_KEY")
            lite_base = value("LITELLM_BASE_URL")
            models = [item.strip() for item in (value("LLM_PLAYER_MODELS", "") or "").split(",") if item.strip()]
            if not lite_key or not lite_base or not models:
                raise ConfigurationError(
                    "litellm mode requires LITELLM_API_KEY, LITELLM_BASE_URL and LLM_PLAYER_MODELS"
                )
            configs = tuple(
                ProviderConfig("litellm", models[index % len(models)], lite_key, lite_base)
                for index in range(7)
            )
            selected, fallbacks = configs, ()

        if len(selected) < 7:
            raise ConfigurationError(
                f"At least seven usable player provider slots are required; found {len(selected)}"
            )

        openai_key = value("OPENAI_API_KEY")
        openai_model = value("OPENAI_ANALYST_MODEL")
        analyst = None
        if openai_key and openai_model:
            analyst = ProviderConfig(
                "openai", openai_model, openai_key, value("OPENAI_BASE_URL", "https://api.openai.com/v1")
            )

        typesafe_key = value("TYPESAFE_API_KEY")
        typesafe_model = value("TYPESAFE_MODEL")
        typesafe = None
        if typesafe_key and typesafe_model:
            typesafe = ProviderConfig(
                "typesafe",
                typesafe_model,
                typesafe_key,
                value("TYPESAFE_BASE_URL", "https://api.typesafe.ai"),
            )

        return cls(
            provider_mode=mode,
            player_providers=tuple(selected[:7]),
            fallback_providers=tuple(fallbacks),
            analyst=analyst,
            typesafe=typesafe,
            min_request_interval_seconds=positive_float(
                "LLM_MIN_REQUEST_INTERVAL_SECONDS", "8"
            ),
            max_output_tokens=positive_int("LLM_MAX_OUTPUT_TOKENS", "180"),
            speak_max_output_tokens=positive_int("LLM_SPEAK_MAX_OUTPUT_TOKENS", "512"),
            request_timeout_seconds=positive_float("LLM_REQUEST_TIMEOUT_SECONDS", "180"),
            decision_timeout_seconds=positive_float("LLM_DECISION_TIMEOUT_SECONDS", "45"),
            typesafe_decision_timeout_seconds=positive_float(
                "TYPESAFE_DECISION_TIMEOUT_SECONDS", "15"
            ),
            analyst_max_output_tokens=positive_int("LLM_ANALYST_MAX_OUTPUT_TOKENS", "700"),
            openai_reasoning_effort=value("OPENAI_REASONING_EFFORT", "low") or "low",
        )

    @staticmethod
    def _numbered_configs(
        source: Mapping[str, str],
        prefix: str,
        provider: str,
        model: str | None,
        base_url: str | None = None,
    ) -> tuple[ProviderConfig, ...]:
        if not model:
            return ()
        configs = []
        for index in range(1, 100):
            key = source.get(f"{prefix}_{index}", "").strip()
            if key:
                configs.append(ProviderConfig(provider, model, key, base_url))
        return tuple(configs)

    @staticmethod
    def _balanced_player_pool(
        gemini: tuple[ProviderConfig, ...], hetzner: tuple[ProviderConfig, ...]
    ) -> tuple[ProviderConfig, ...]:
        # Prefer a 4/3 mix when both pools exist so a seven-agent match exercises
        # both model families. Extra keys remain available as fallbacks.
        selected: list[ProviderConfig] = []
        g_index = h_index = 0
        while len(selected) < 7 and (g_index < len(gemini) or h_index < len(hetzner)):
            if g_index < len(gemini):
                selected.append(gemini[g_index])
                g_index += 1
            if len(selected) < 7 and h_index < len(hetzner):
                selected.append(hetzner[h_index])
                h_index += 1
        return tuple(selected)

    @staticmethod
    def _take_seven(
        configs: tuple[ProviderConfig, ...]
    ) -> tuple[tuple[ProviderConfig, ...], tuple[ProviderConfig, ...]]:
        return configs[:7], configs[7:]
