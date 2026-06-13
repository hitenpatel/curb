"""Model gateway.

Single place where the model is chosen. Default comes from MODEL_PROVIDER /
MODEL_API_KEY env (set on the box for the server-side free-tier demo path).
A per-request BYOK override is supported: the request carries
`model_provider` + `model_api_key`; we build a one-off model for that audit
and never persist the key.

Provider strings use pydantic-ai's convention: `'google-gla:gemini-1.5-flash'`,
`'groq:llama-3.1-70b-versatile'`, `'openai:gpt-4o-mini'`, etc.
"""

from __future__ import annotations

from dataclasses import dataclass

from curb_shared.config import Settings
from pydantic_ai.models import Model

# Sensible free-tier defaults per provider, keyed by the bare provider string.
_DEFAULT_MODEL_FOR: dict[str, str] = {
    "google-gla": "gemini-2.0-flash",
    "groq": "llama-3.3-70b-versatile",
    "openai": "gpt-4o-mini",
}


@dataclass(frozen=True)
class ModelChoice:
    """The fully-qualified model name + the key to use, if any.

    `qualified` is a pydantic-ai model string like 'google-gla:gemini-2.0-flash'.
    `api_key` is set on the relevant provider env when the model is built.
    """

    qualified: str
    api_key: str | None


def _qualify(provider: str, model_hint: str | None) -> str:
    """Build a 'provider:model' string. `model_hint` may already include the
    colon (in which case it wins); otherwise use the per-provider default."""
    if model_hint and ":" in model_hint:
        return model_hint
    model = model_hint or _DEFAULT_MODEL_FOR.get(provider, "")
    if not model:
        raise ValueError(f"no default model known for provider '{provider}'")
    return f"{provider}:{model}"


def resolve(
    settings: Settings,
    *,
    byok_provider: str | None = None,
    byok_api_key: str | None = None,
    byok_model: str | None = None,
) -> ModelChoice | None:
    """Pick the model for one audit.

    Returns None when no usable model is configured (no BYOK and no server
    key). The caller then skips remediation rather than crashing — detection
    + retrieval still ran, and that's a useful audit on its own.
    """
    if byok_provider and byok_api_key:
        return ModelChoice(
            qualified=_qualify(byok_provider, byok_model),
            api_key=byok_api_key,
        )
    if settings.model_provider and settings.model_api_key:
        return ModelChoice(
            qualified=_qualify(settings.model_provider, None),
            api_key=settings.model_api_key,
        )
    return None


def build_model(choice: ModelChoice) -> Model:
    """Instantiate the pydantic-ai Model for a resolved choice.

    Imports are local so unrelated providers don't get pulled in for an
    audit that's using one of them.
    """
    # Local imports per provider so unrelated SDK trees stay cold; if the
    # audit is on Gemini, the OpenAI client never gets touched.
    provider, _, _ = choice.qualified.partition(":")
    model_name = choice.qualified.split(":", 1)[1]
    key = choice.api_key or ""
    if provider == "google-gla":
        from pydantic_ai.models.google import GoogleModel  # noqa: PLC0415
        from pydantic_ai.providers.google import GoogleProvider  # noqa: PLC0415

        return GoogleModel(model_name, provider=GoogleProvider(api_key=key))
    if provider == "groq":
        from pydantic_ai.models.groq import GroqModel  # noqa: PLC0415
        from pydantic_ai.providers.groq import GroqProvider  # noqa: PLC0415

        return GroqModel(model_name, provider=GroqProvider(api_key=key))
    if provider == "openai":
        from pydantic_ai.models.openai import OpenAIChatModel  # noqa: PLC0415
        from pydantic_ai.providers.openai import OpenAIProvider  # noqa: PLC0415

        return OpenAIChatModel(model_name, provider=OpenAIProvider(api_key=key))
    raise ValueError(f"unsupported provider: {provider}")
