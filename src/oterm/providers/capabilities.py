import re
from dataclasses import dataclass


@dataclass
class ModelCapabilities:
    supports_tools: bool = False
    supports_thinking: bool = False
    supports_vision: bool = False


_NON_CHAT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p)
    for p in [
        r"^dall-e",
        r"^tts-",
        r"^whisper-",
        r"^text-embedding-",
        r"^babbage-",
        r"^davinci-",
        r"^omni-moderation-",
        r"^sora-",
        r"^gpt-image-",
        r"^chatgpt-image-",
        r"^gpt-audio",
        r"^gpt-realtime",
        r"-tts",
        r"-realtime",
        r"-transcribe",
    ]
]


def is_chat_model(provider: str, model: str) -> bool:
    if provider == "ollama":
        return True
    if provider == "anthropic":
        return True
    if provider in ("google-gla", "google-vertex"):
        return "gemini" in model
    if provider == "mistral":
        return not model.startswith("mistral-embed")
    if provider == "cohere":
        return not ("embed" in model or "rerank" in model)
    return not any(p.search(model) for p in _NON_CHAT_PATTERNS)


def get_capabilities(provider: str, model: str) -> ModelCapabilities:
    if provider == "ollama":
        return _get_ollama_capabilities(model)

    if provider.startswith("openai-compat/"):
        return ModelCapabilities(
            supports_tools=True,
            supports_thinking=True,
            supports_vision=True,
        )

    return ModelCapabilities(
        supports_tools=True,
        supports_thinking=_supports_thinking(provider, model),
        supports_vision=_supports_vision(provider, model),
    )


def _supports_thinking(provider: str, model: str) -> bool:
    """Per-provider reasoning/thinking support, sourced from pydantic-ai profiles.

    Falls back to ``False`` for providers pydantic-ai doesn't recognise (e.g.
    ``huggingface``) and for malformed model names. DeepSeek is special-cased
    because its profile delegates to the OpenAI profile, which doesn't know
    about the ``-reasoner`` suffix.
    """
    if provider == "deepseek":
        return "reasoner" in model

    from pydantic_ai.providers import infer_provider_class

    try:
        profile = infer_provider_class(provider).model_profile(model)
    except Exception:
        return False
    return bool(profile and profile.supports_thinking)


def _supports_vision(provider: str, model: str) -> bool:
    if provider == "anthropic":
        return (
            "claude-3" in model
            or "claude-4" in model
            or "claude-opus-4" in model
            or "claude-sonnet-4" in model
            or "claude-haiku-4" in model
        )
    if provider == "openai":
        return any(
            model.startswith(p)
            for p in ("gpt-4o", "gpt-4-turbo", "gpt-4.1", "gpt-5", "o1", "o3", "o4")
        )
    if provider in ("google-gla", "google-vertex"):
        return "gemini" in model
    if provider == "groq":
        return "vision" in model or "llava" in model
    if provider == "grok":
        return "vision" in model
    return False


def _get_ollama_capabilities(model: str) -> ModelCapabilities:
    """Get capabilities from Ollama's show API."""
    from oterm.providers import ollama

    try:
        info = ollama.show_model(model)
        capabilities: list[str] = info.get("capabilities", [])
        return ModelCapabilities(
            supports_tools="tools" in capabilities,
            supports_thinking="thinking" in capabilities,
            supports_vision="vision" in capabilities,
        )
    except Exception:
        return ModelCapabilities()
