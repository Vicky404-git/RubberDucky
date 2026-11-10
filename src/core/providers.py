"""Provider registry for BYOK (bring your own key) integrations.

Every external service RubberDucky talks to is declared here exactly once.
Adding a new provider means adding one :class:`ProviderSpec` entry; the
diagnosis pipeline, credential management and Settings UI then pick it up
without further changes. No provider may be advertised unless the matching
client integration actually exists.
"""
from __future__ import annotations

from dataclasses import dataclass

SUPPORTED_LLM_PROVIDERS = ("openrouter", "groq")


@dataclass(frozen=True)
class ProviderSpec:
    """Static description of one external service provider."""

    id: str
    name: str
    kind: str  # "llm" or "speech"
    env_var: str
    description: str
    capabilities: tuple[str, ...]
    base_url: str | None = None
    default_model: str | None = None
    connection_test: bool = False
    json_mode: bool = False
    # Retry once without response_format when the provider rejects JSON mode
    # (HTTP 400) for the configured model. Never changes provider.
    json_mode_fallback: bool = False


PROVIDERS: dict[str, ProviderSpec] = {
    "openrouter": ProviderSpec(
        id="openrouter",
        name="OpenRouter",
        kind="llm",
        env_var="OPENROUTER_API_KEY",
        base_url="https://openrouter.ai/api/v1",
        default_model="liquid/lfm-3-1.7b:free",
        description=(
            "Unified access to many hosted models, including free tiers. "
            "Usage is billed to your own OpenRouter account."
        ),
        capabilities=("diagnosis",),
        connection_test=True,
        json_mode=True,
        json_mode_fallback=False,
    ),
    "groq": ProviderSpec(
        id="groq",
        name="Groq",
        kind="llm",
        env_var="GROQ_API_KEY",
        base_url="https://api.groq.com/openai/v1",
        default_model="openai/gpt-oss-120b",
        description=(
            "Fast LPU inference for OpenAI-compatible chat models. "
            "Usage is billed to your own Groq account."
        ),
        capabilities=("diagnosis",),
        connection_test=True,
        json_mode=True,
        # Some Groq models reject response_format=json_object with HTTP 400;
        # the shared prompt plus fence-tolerant parsing keeps output valid.
        json_mode_fallback=True,
    ),
    "gnani": ProviderSpec(
        id="gnani",
        name="Gnani",
        kind="speech",
        env_var="GNANI_API",
        base_url=None,
        default_model=None,
        description=(
            "Gnani speech services. The same credential enables Prisma STT "
            "(speech to text) and Timbre TTS (text to speech)."
        ),
        capabilities=("stt", "tts"),
        # No credential-only verification endpoint exists in the SDK; a real
        # check requires sending audio through the speech pipeline.
        connection_test=False,
    ),
}


def get_provider(provider_id: str) -> ProviderSpec | None:
    return PROVIDERS.get(provider_id.strip().lower())


def is_llm_provider(provider_id: str) -> bool:
    spec = get_provider(provider_id)
    return spec is not None and spec.kind == "llm"


def llm_provider_ids() -> tuple[str, ...]:
    return tuple(
        spec.id for spec in PROVIDERS.values() if spec.kind == "llm"
    )
