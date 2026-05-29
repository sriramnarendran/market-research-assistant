"""Pydantic AI model factories.

One switch point for the entire AI layer. Production agents instantiate models
via these helpers; tests override with `Agent.override(model=TestModel())`.

Provider strategy
-----------------
Both the main pipeline (extract / synth / research agent) and the judge run on
**Azure OpenAI**. To recover model-family independence for the judge, point
`AZURE_OPENAI_MAIN_DEPLOYMENT` and `AZURE_OPENAI_JUDGE_DEPLOYMENT` at different
deployments (e.g. `gpt-5` and `gpt-5-mini`). Defaulting them to the same
deployment is acceptable for a single-deployment Azure setup; the prompt
docs call out the caveat.

When `settings.LLM_MODE == "test"`, every helper returns a `TestModel`, so the
whole pipeline runs without any external API calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.core.config import get_settings


@dataclass(frozen=True)
class ModelInfo:
    """Provider + model identifier used when recording `usage_events`."""

    provider: str  # "azure_openai" or "test"
    model: str  # the deployment name


# -----------------------------------------------------------------------------
# Live model builders
# -----------------------------------------------------------------------------


@lru_cache(maxsize=8)
def _build_azure_openai(deployment: str) -> Any:
    """GPT-class model served through Azure OpenAI."""
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.azure import AzureProvider

    settings = get_settings()
    return OpenAIChatModel(
        deployment,
        provider=AzureProvider(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_KEY,
        ),
    )


def _build_test_model() -> Any:
    """TestModel returns valid-shaped output for any `output_type` automatically."""
    from pydantic_ai.models.test import TestModel

    return TestModel()


# -----------------------------------------------------------------------------
# Public factories — one per pipeline phase. Lets us swap a single phase to a
# different deployment without touching the others.
# -----------------------------------------------------------------------------


def get_agent_model() -> Any:
    """Model used by the research agent (topic path)."""
    return _build_test_model() if _is_test_mode() else _build_azure_openai(_main_deployment())


def get_extract_model() -> Any:
    """Model used by the per-source fact extractor."""
    return _build_test_model() if _is_test_mode() else _build_azure_openai(_main_deployment())


def get_synth_model() -> Any:
    """Model used by the synthesiser."""
    return _build_test_model() if _is_test_mode() else _build_azure_openai(_main_deployment())


def get_judge_model() -> Any:
    """Model used by the LLM-as-judge.

    For independence, set `AZURE_OPENAI_JUDGE_DEPLOYMENT` to a different
    deployment than `AZURE_OPENAI_MAIN_DEPLOYMENT`. They may be the same.
    """
    return _build_test_model() if _is_test_mode() else _build_azure_openai(_judge_deployment())


# -----------------------------------------------------------------------------
# Model identifiers for telemetry (kept in sync with the factories above)
# -----------------------------------------------------------------------------


def info_for(phase: str) -> ModelInfo:
    """Return provider + deployment identifier for the given pipeline phase."""
    if _is_test_mode():
        return ModelInfo(provider="test", model="test")
    if phase == "judge":
        return ModelInfo(provider="azure_openai", model=_judge_deployment())
    return ModelInfo(provider="azure_openai", model=_main_deployment())


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _is_test_mode() -> bool:
    return get_settings().LLM_MODE == "test"


def _main_deployment() -> str:
    return get_settings().AZURE_OPENAI_MAIN_DEPLOYMENT


def _judge_deployment() -> str:
    return get_settings().AZURE_OPENAI_JUDGE_DEPLOYMENT
