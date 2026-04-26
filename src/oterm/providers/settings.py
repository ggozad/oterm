from functools import cache

from pydantic_ai.models.anthropic import AnthropicModelSettings
from pydantic_ai.models.bedrock import BedrockModelSettings
from pydantic_ai.models.cerebras import CerebrasModelSettings
from pydantic_ai.models.cohere import CohereModelSettings
from pydantic_ai.models.google import GoogleModelSettings
from pydantic_ai.models.groq import GroqModelSettings
from pydantic_ai.models.huggingface import HuggingFaceModelSettings
from pydantic_ai.models.mistral import MistralModelSettings
from pydantic_ai.models.openai import OpenAIChatModelSettings
from pydantic_ai.settings import ModelSettings

PROVIDER_SETTINGS_TYPE: dict[str, type] = {
    "ollama": OpenAIChatModelSettings,
    "openai": OpenAIChatModelSettings,
    "deepseek": OpenAIChatModelSettings,
    "grok": OpenAIChatModelSettings,
    "anthropic": AnthropicModelSettings,
    "google-gla": GoogleModelSettings,
    "google-vertex": GoogleModelSettings,
    "groq": GroqModelSettings,
    "mistral": MistralModelSettings,
    "cohere": CohereModelSettings,
    "bedrock": BedrockModelSettings,
    "cerebras": CerebrasModelSettings,
    "huggingface": HuggingFaceModelSettings,
}


def get_settings_type(provider: str) -> type:
    """Return the pydantic-ai ModelSettings TypedDict subclass for an oterm provider id.

    OpenAI-compatible endpoints all share OpenAIChatModelSettings.
    Unknown providers fall back to the base ModelSettings.
    """
    if provider.startswith("openai-compat/"):
        return OpenAIChatModelSettings
    return PROVIDER_SETTINGS_TYPE.get(provider, ModelSettings)


@cache
def _keys_for_type(settings_type: type) -> frozenset[str]:
    # TypedDict carries inherited fields in __optional_keys__ / __required_keys__.
    # Use these instead of typing.get_type_hints, which would try to evaluate
    # provider-specific forward refs (e.g. Bedrock's GuardrailConfigurationTypeDef).
    optional = getattr(settings_type, "__optional_keys__", frozenset())
    required = getattr(settings_type, "__required_keys__", frozenset())
    return frozenset(optional) | frozenset(required)


def get_supported_setting_keys(provider: str) -> frozenset[str]:
    """Full set of setting keys (including inherited) accepted by the provider."""
    return _keys_for_type(get_settings_type(provider))
