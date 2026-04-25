import os
from collections.abc import Callable

PROVIDER_ENV_VARS: dict[str, list[str]] = {
    "ollama": [],
    "openai": ["OPENAI_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY"],
    "google-gla": ["GOOGLE_API_KEY"],
    "google-vertex": ["GOOGLE_APPLICATION_CREDENTIALS"],
    "groq": ["GROQ_API_KEY"],
    "mistral": ["MISTRAL_API_KEY"],
    "cohere": ["COHERE_API_KEY"],
    "bedrock": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"],
    "deepseek": ["DEEPSEEK_API_KEY"],
    "grok": ["GROK_API_KEY"],
    "cerebras": ["CEREBRAS_API_KEY"],
    "huggingface": ["HF_TOKEN"],
}

PROVIDER_NAMES: dict[str, str] = {
    "ollama": "Ollama",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google-gla": "Google AI",
    "google-vertex": "Google Vertex AI",
    "groq": "Groq",
    "mistral": "Mistral",
    "cohere": "Cohere",
    "bedrock": "AWS Bedrock",
    "deepseek": "DeepSeek",
    "grok": "Grok",
    "cerebras": "Cerebras",
    "huggingface": "Hugging Face",
}


UNRESOLVED_API_KEY = "unresolved-api-key"
"""Placeholder sent to OpenAI-compatible endpoints when no key is configured.

Passed instead of ``None`` to prevent ``openai.AsyncOpenAI`` from falling back
to the ``OPENAI_API_KEY`` environment variable, which would leak it to a
different endpoint (e.g. a local vLLM or OpenRouter)."""


def _resolve_api_key(api_key: str | None) -> str | None:
    """Resolve an API key, expanding $ENV_VAR references. None if unresolved."""
    if api_key is None:
        return None
    if api_key.startswith("$"):
        return os.getenv(api_key[1:])
    return api_key


def get_openai_compatible_providers() -> dict[str, dict]:
    """Return configured OpenAI-compatible endpoints from appConfig."""
    from oterm.config import appConfig

    raw = appConfig.get("openaiCompatible", {})
    if not raw or not isinstance(raw, dict):
        return {}
    return {
        name: config
        for name, config in raw.items()
        if isinstance(config, dict) and "base_url" in config
    }


def get_all_providers() -> list[str]:
    return list(PROVIDER_ENV_VARS.keys())


def get_provider_name(provider: str) -> str:
    if provider.startswith("openai-compat/"):
        return provider.removeprefix("openai-compat/")
    return PROVIDER_NAMES.get(provider, provider.title())


def get_available_providers() -> list[str]:
    available = []
    for provider_id in get_all_providers():
        env_vars = PROVIDER_ENV_VARS.get(provider_id, [])
        if not env_vars or all(os.getenv(var) for var in env_vars):
            available.append(provider_id)
    for name, config in get_openai_compatible_providers().items():
        api_key = _resolve_api_key(config.get("api_key"))
        if api_key is not None or "api_key" not in config:
            available.append(f"openai-compat/{name}")
    return available


def _list_via_openai_client(base_url: str, api_key: str) -> list[str]:
    from openai import OpenAI

    client = OpenAI(base_url=base_url, api_key=api_key)
    return sorted(m.id for m in client.models.list().data)


def _list_openai() -> list[str]:
    from openai import OpenAI

    return sorted(m.id for m in OpenAI().models.list().data)


def _list_anthropic() -> list[str]:
    from anthropic import Anthropic

    return sorted(m.id for m in Anthropic().models.list().data)


def _list_google_gla() -> list[str]:
    from google import genai

    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY", ""))
    return sorted(
        m.name.removeprefix("models/") for m in client.models.list() if m.name
    )


def _list_mistral() -> list[str] | None:
    from mistralai.client import Mistral
    from mistralai.client.models.basemodelcard import BaseModelCard
    from mistralai.client.models.ftmodelcard import FTModelCard

    client = Mistral(api_key=os.getenv("MISTRAL_API_KEY", ""))
    response = client.models.list()
    if not (response and response.data):
        return None
    return sorted(
        m.id
        for m in response.data
        if isinstance(m, (BaseModelCard, FTModelCard)) and m.id
    )


def _list_cohere() -> list[str] | None:
    import cohere

    client = cohere.ClientV2(api_key=os.getenv("COHERE_API_KEY", ""))
    response = client.models.list()
    if not (response and response.models):
        return None
    return sorted(m.name for m in response.models if m.name)


_NATIVE_LISTERS: dict[str, Callable[[], list[str] | None]] = {
    "openai": _list_openai,
    "anthropic": _list_anthropic,
    "google-gla": _list_google_gla,
    "mistral": _list_mistral,
    "cohere": _list_cohere,
}

# OpenAI-compatible providers shipped with oterm: hard-coded base URL + env var.
_BUILTIN_OPENAI_COMPAT: dict[str, tuple[str, str]] = {
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
    "deepseek": ("https://api.deepseek.com/v1", "DEEPSEEK_API_KEY"),
    "cerebras": ("https://api.cerebras.ai/v1", "CEREBRAS_API_KEY"),
    "grok": ("https://api.x.ai/v1", "GROK_API_KEY"),
}


def _list_models_from_api(provider: str) -> list[str] | None:
    from oterm.log import log

    if provider.startswith("openai-compat/"):
        endpoint_name = provider.removeprefix("openai-compat/")
        config = get_openai_compatible_providers().get(endpoint_name)
        if not config:
            return None
        api_key = _resolve_api_key(config.get("api_key")) or UNRESOLVED_API_KEY
        try:
            return _list_via_openai_client(config["base_url"], api_key)
        except Exception as e:
            log.warning(f"Failed to list models for {provider}: {e}")
            return None

    if provider in _BUILTIN_OPENAI_COMPAT:
        base_url, env_var = _BUILTIN_OPENAI_COMPAT[provider]
        api_key = os.getenv(env_var, "")
        if not api_key:
            return None
        try:
            return _list_via_openai_client(base_url, api_key)
        except Exception as e:
            log.warning(f"Failed to list {provider} models: {e}")
            return None

    lister = _NATIVE_LISTERS.get(provider)
    if lister is None:
        return None
    try:
        return lister()
    except Exception as e:
        log.warning(f"Failed to list {get_provider_name(provider)} models: {e}")
        return None


def _list_models_from_known(provider: str) -> list[str]:
    from typing import get_args

    from pydantic_ai.models import KnownModelName

    prefix = f"{provider}:"
    return [
        name[len(prefix) :]
        for name in get_args(KnownModelName.__value__)
        if name.startswith(prefix)
    ]


def list_models(provider: str) -> list[str]:
    from oterm.providers.capabilities import is_chat_model

    if provider == "ollama":
        from oterm.providers import ollama

        try:
            response = ollama.list_models()
            return [model.model or "" for model in response.models if model.model]
        except Exception:
            return []

    models = _list_models_from_api(provider) or _list_models_from_known(provider)
    return [m for m in models if is_chat_model(provider, m)]
