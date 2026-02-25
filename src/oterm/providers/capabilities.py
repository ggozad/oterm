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

    return ModelCapabilities(
        supports_tools=_supports_tools(provider, model),
        supports_thinking=_supports_thinking(provider, model),
        supports_vision=_supports_vision(provider, model),
    )


def _supports_tools(provider: str, model: str) -> bool:
    return True


def _supports_thinking(provider: str, model: str) -> bool:
    if provider == "openai":
        from pydantic_ai.profiles.openai import OpenAIModelProfile, openai_model_profile

        profile = openai_model_profile(model)
        if isinstance(profile, OpenAIModelProfile):
            return profile.openai_supports_reasoning
        return False
    if provider == "anthropic":
        return (
            "claude-3-7" in model
            or "claude-4" in model
            or "claude-opus-4" in model
            or "claude-sonnet-4" in model
            or "claude-haiku-4" in model
        )
    if provider == "deepseek":
        return "reasoner" in model
    if provider in ("google-gla", "google-vertex"):
        return "thinking" in model or "2.5" in model
    if provider == "groq":
        return "deepseek-r1" in model
    return False


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
