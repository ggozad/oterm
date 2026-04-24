import os

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


def _list_models_from_api(provider: str) -> list[str] | None:
    from oterm.log import log

    if provider == "openai":
        try:
            from openai import OpenAI

            return sorted(m.id for m in OpenAI().models.list().data)
        except Exception as e:
            log.warning(f"Failed to list OpenAI models: {e}")
            return None

    if provider == "anthropic":
        try:
            from anthropic import Anthropic

            return sorted(m.id for m in Anthropic().models.list().data)
        except Exception as e:
            log.warning(f"Failed to list Anthropic models: {e}")
            return None

    if provider == "google-gla":
        try:
            from google import genai  # type: ignore[reportAttributeAccessIssue]

            client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY", ""))
            return sorted(
                m.name.removeprefix("models/") for m in client.models.list() if m.name
            )
        except Exception as e:
            log.warning(f"Failed to list Google AI models: {e}")
            return None

    if provider == "mistral":
        try:
            from mistralai.client import Mistral
            from mistralai.client.models.basemodelcard import BaseModelCard
            from mistralai.client.models.ftmodelcard import FTModelCard

            client = Mistral(api_key=os.getenv("MISTRAL_API_KEY", ""))
            response = client.models.list()
            if response and response.data:
                return sorted(
                    m.id
                    for m in response.data
                    if isinstance(m, (BaseModelCard, FTModelCard)) and m.id
                )
            return None
        except Exception as e:
            log.warning(f"Failed to list Mistral models: {e}")
            return None

    if provider == "cohere":
        try:
            import cohere

            client = cohere.ClientV2(api_key=os.getenv("COHERE_API_KEY", ""))
            response = client.models.list()
            if response and response.models:
                return sorted(m.name for m in response.models if m.name)
            return None
        except Exception as e:
            log.warning(f"Failed to list Cohere models: {e}")
            return None

    if provider.startswith("openai-compat/"):
        endpoint_name = provider.removeprefix("openai-compat/")
        configs = get_openai_compatible_providers()
        config = configs.get(endpoint_name)
        if not config:
            return None
        base_url = config["base_url"]
        api_key = _resolve_api_key(config.get("api_key")) or UNRESOLVED_API_KEY
        try:
            from openai import OpenAI

            client = OpenAI(base_url=base_url, api_key=api_key)
            return sorted(m.id for m in client.models.list().data)
        except Exception as e:
            log.warning(f"Failed to list models for {provider}: {e}")
            return None

    # Built-in OpenAI-compatible providers
    base_urls: dict[str, tuple[str, str]] = {
        "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
        "deepseek": ("https://api.deepseek.com/v1", "DEEPSEEK_API_KEY"),
        "cerebras": ("https://api.cerebras.ai/v1", "CEREBRAS_API_KEY"),
        "grok": ("https://api.x.ai/v1", "GROK_API_KEY"),
    }

    if provider in base_urls:
        base_url, env_var = base_urls[provider]
        api_key = os.getenv(env_var, "")
        if not api_key:
            return None
        try:
            from openai import OpenAI

            client = OpenAI(base_url=base_url, api_key=api_key)
            return sorted(m.id for m in client.models.list().data)
        except Exception as e:
            log.warning(f"Failed to list {provider} models: {e}")
            return None

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
