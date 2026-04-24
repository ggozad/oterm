import pytest

from oterm.providers.capabilities import (
    ModelCapabilities,
    get_capabilities,
    is_chat_model,
)


class TestIsChatModel:
    @pytest.mark.parametrize(
        "provider,model",
        [
            ("ollama", "llama3"),
            ("anthropic", "claude-3-haiku"),
            ("google-gla", "gemini-1.5"),
            ("google-vertex", "gemini-2.0-flash"),
            ("mistral", "mistral-large"),
            ("cohere", "command-r"),
            ("openai", "gpt-4o"),
            ("openai", "o1-preview"),
        ],
    )
    def test_chat_models_accepted(self, provider, model):
        assert is_chat_model(provider, model) is True

    @pytest.mark.parametrize(
        "provider,model",
        [
            ("google-gla", "embedding-001"),
            ("mistral", "mistral-embed"),
            ("cohere", "embed-v3"),
            ("cohere", "rerank-v3"),
            ("openai", "dall-e-3"),
            ("openai", "tts-1"),
            ("openai", "whisper-1"),
            ("openai", "text-embedding-3-small"),
            ("openai", "gpt-4o-transcribe"),
            ("openai", "gpt-4o-realtime-preview"),
        ],
    )
    def test_non_chat_models_rejected(self, provider, model):
        assert is_chat_model(provider, model) is False


class TestGetCapabilities:
    def test_openai_compat_always_supports_tools(self):
        caps = get_capabilities("openai-compat/vllm", "any-model")
        assert caps.supports_tools is True
        assert caps.supports_thinking is False
        assert caps.supports_vision is False

    def test_anthropic_claude_3_has_vision(self):
        caps = get_capabilities("anthropic", "claude-3-opus")
        assert caps.supports_tools is True
        assert caps.supports_vision is True

    def test_anthropic_claude_4_has_thinking_and_vision(self):
        caps = get_capabilities("anthropic", "claude-4-sonnet")
        assert caps.supports_thinking is True
        assert caps.supports_vision is True

    def test_anthropic_claude_2_no_thinking(self):
        caps = get_capabilities("anthropic", "claude-2.1")
        assert caps.supports_thinking is False

    def test_openai_vision_models(self):
        for model in ("gpt-4o", "gpt-4-turbo", "gpt-4.1", "gpt-5", "o1", "o3", "o4"):
            caps = get_capabilities("openai", model)
            assert caps.supports_vision is True, model

    def test_google_gla_gemini_vision(self):
        caps = get_capabilities("google-gla", "gemini-1.5-pro")
        assert caps.supports_vision is True

    def test_google_gla_thinking_branch(self):
        caps = get_capabilities("google-gla", "gemini-2.5-pro")
        assert caps.supports_thinking is True

    def test_groq_deepseek_r1_thinking(self):
        caps = get_capabilities("groq", "deepseek-r1-distill-llama-70b")
        assert caps.supports_thinking is True

    def test_groq_vision(self):
        caps = get_capabilities("groq", "llama-vision")
        assert caps.supports_vision is True

    def test_grok_vision(self):
        caps = get_capabilities("grok", "grok-vision-beta")
        assert caps.supports_vision is True

    def test_deepseek_reasoner_thinking(self):
        caps = get_capabilities("deepseek", "deepseek-reasoner")
        assert caps.supports_thinking is True

    def test_unknown_provider_defaults(self):
        caps = get_capabilities("unknown", "some-model")
        assert caps.supports_tools is True
        assert caps.supports_thinking is False
        assert caps.supports_vision is False

    def test_ollama_uses_show_api(self, monkeypatch):
        def fake_show(model):
            return {"capabilities": ["tools", "thinking", "vision"]}

        from oterm.providers import ollama as ollama_mod

        monkeypatch.setattr(ollama_mod, "show_model", fake_show)

        caps = get_capabilities("ollama", "llama3")
        assert caps.supports_tools is True
        assert caps.supports_thinking is True
        assert caps.supports_vision is True

    def test_ollama_falls_back_to_empty_on_error(self, monkeypatch):
        from oterm.providers import ollama as ollama_mod

        def boom(model):
            raise RuntimeError("ollama down")

        monkeypatch.setattr(ollama_mod, "show_model", boom)
        caps = get_capabilities("ollama", "llama3")
        assert caps == ModelCapabilities()

    def test_openai_thinking_via_pydantic_profile(self, monkeypatch):
        """`_supports_thinking` delegates to pydantic-ai's OpenAIModelProfile."""
        from pydantic_ai.profiles import openai as openai_profile_mod
        from pydantic_ai.profiles.openai import OpenAIModelProfile

        monkeypatch.setattr(
            openai_profile_mod,
            "openai_model_profile",
            lambda m: OpenAIModelProfile(openai_supports_reasoning=True),
        )
        assert get_capabilities("openai", "anything").supports_thinking is True

        monkeypatch.setattr(
            openai_profile_mod,
            "openai_model_profile",
            lambda m: OpenAIModelProfile(openai_supports_reasoning=False),
        )
        assert get_capabilities("openai", "anything").supports_thinking is False

    def test_openai_thinking_non_openai_profile(self, monkeypatch):
        """If pydantic-ai returns a non-OpenAI profile, fall back to False."""
        from pydantic_ai.profiles import openai as openai_profile_mod

        monkeypatch.setattr(
            openai_profile_mod, "openai_model_profile", lambda m: object()
        )
        assert get_capabilities("openai", "x").supports_thinking is False
