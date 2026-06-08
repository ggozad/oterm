import pytest
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.providers.openai import OpenAIProvider

from oterm.agent import _build_model_settings, get_agent
from oterm.providers import UNRESOLVED_API_KEY
from oterm.providers.capabilities import ModelCapabilities


@pytest.fixture
def ollama_thinking(monkeypatch):
    """Stub Ollama capability detection so get_agent stays offline."""

    def _set(supports_thinking: bool) -> None:
        import oterm.agent as agent_mod

        monkeypatch.setattr(
            agent_mod,
            "get_capabilities",
            lambda provider, model: ModelCapabilities(
                supports_thinking=supports_thinking
            ),
        )

    return _set


class TestBuildModelSettings:
    def test_none_parameters_only_sets_thinking(self):
        settings = _build_model_settings(None, thinking=True, provider="ollama")
        assert settings is not None
        assert settings.get("thinking") is True  # pydantic-ai dict-like settings
        assert "temperature" not in settings

    def test_empty_parameters_only_sets_thinking(self):
        settings = _build_model_settings({}, thinking=False, provider="ollama")
        assert settings is not None
        assert settings.get("thinking") is False
        assert "temperature" not in settings

    def test_picks_known_keys(self):
        settings = _build_model_settings(
            {
                "temperature": 0.7,
                "top_p": 0.9,
                "max_tokens": 128,
                "ignored": "nope",
            },
            thinking=False,
            provider="ollama",
        )
        assert settings is not None
        assert settings["temperature"] == 0.7
        assert settings["top_p"] == 0.9
        assert settings["max_tokens"] == 128
        assert "ignored" not in settings

    @pytest.mark.parametrize("provider", ["openai-chat", "anthropic", "groq", "ollama"])
    def test_seed_roundtrips_for_supported_providers(self, provider):
        settings = _build_model_settings(
            {"seed": 42}, thinking=False, provider=provider
        )
        assert settings is not None
        assert settings["seed"] == 42

    def test_unknown_keys_are_dropped_silently(self):
        """Stale Ollama-native keys from older oterm chats must not raise."""
        settings = _build_model_settings(
            {
                "num_ctx": 8192,
                "repeat_penalty": 1.1,
                "made_up": True,
                "temperature": 0.3,
            },
            thinking=False,
            provider="ollama",
        )
        assert settings is not None
        assert settings["temperature"] == 0.3
        assert "num_ctx" not in settings
        assert "repeat_penalty" not in settings
        assert "made_up" not in settings

    def test_anthropic_thinking_drops_sampling_params_and_bumps_max_tokens(self):
        settings = _build_model_settings(
            {"temperature": 0.7, "top_p": 0.9, "max_tokens": 128},
            thinking=True,
            provider="anthropic",
        )
        assert settings is not None
        assert "temperature" not in settings
        assert "top_p" not in settings
        # Anthropic requires max_tokens > thinking.budget_tokens (10000).
        assert settings["max_tokens"] > 10000
        assert settings.get("thinking") is True

    def test_anthropic_thinking_keeps_high_user_max_tokens(self):
        settings = _build_model_settings(
            {"max_tokens": 32000},
            thinking=True,
            provider="anthropic",
        )
        assert settings is not None
        assert settings["max_tokens"] == 32000

    def test_anthropic_thinking_off_keeps_sampling_params(self):
        settings = _build_model_settings(
            {"temperature": 0.7, "top_p": 0.9},
            thinking=False,
            provider="anthropic",
        )
        assert settings is not None
        assert settings["temperature"] == 0.7
        assert settings["top_p"] == 0.9


class TestGetAgent:
    def test_ollama_provider(self, monkeypatch, ollama_thinking):
        import oterm.config

        ollama_thinking(False)
        monkeypatch.setattr(
            oterm.config.envConfig, "OLLAMA_URL", "http://localhost:11434"
        )
        agent = get_agent(provider="ollama", model="llama3")
        assert isinstance(agent, Agent)
        assert isinstance(agent.model, OpenAIChatModel)
        assert isinstance(agent.model._provider, OllamaProvider)
        assert (
            str(agent.model.client.base_url).rstrip("/") == "http://localhost:11434/v1"
        )

    def test_ollama_provider_w_api_key(self, monkeypatch, ollama_thinking):
        import oterm.config

        OLLAMA_URL = "https://ollama.example.com"
        OLLAMA_API_KEY = "TEST_KEY"

        ollama_thinking(False)
        monkeypatch.setattr(
            oterm.config.envConfig,
            "OLLAMA_URL",
            OLLAMA_URL,
        )
        monkeypatch.setattr(oterm.config.envConfig, "OLLAMA_API_KEY", OLLAMA_API_KEY)
        agent = get_agent(provider="ollama", model="llama3")
        assert isinstance(agent, Agent)
        assert isinstance(agent.model, OpenAIChatModel)
        assert isinstance(agent.model._provider, OllamaProvider)
        assert str(agent.model.client.base_url).rstrip("/") == f"{OLLAMA_URL}/v1"
        assert agent.model.client.api_key == OLLAMA_API_KEY

    def test_ollama_thinking_capable_model_enables_thinking_in_profile(
        self, monkeypatch, ollama_thinking
    ):
        """A thinking-capable Ollama model must report supports_thinking so
        pydantic-ai forwards the unified thinking setting (and can disable it)."""
        import oterm.config

        ollama_thinking(True)
        monkeypatch.setattr(
            oterm.config.envConfig, "OLLAMA_URL", "http://localhost:11434"
        )
        agent = get_agent(provider="ollama", model="qwen3.6")
        assert isinstance(agent.model, OpenAIChatModel)
        assert agent.model.profile.supports_thinking is True

    def test_ollama_non_thinking_model_leaves_thinking_disabled_in_profile(
        self, monkeypatch, ollama_thinking
    ):
        import oterm.config

        ollama_thinking(False)
        monkeypatch.setattr(
            oterm.config.envConfig, "OLLAMA_URL", "http://localhost:11434"
        )
        agent = get_agent(provider="ollama", model="devstral")
        assert isinstance(agent.model, OpenAIChatModel)
        assert agent.model.profile.supports_thinking is False

    def test_openai_responses_provider_enables_image_generation_tool(self, monkeypatch):
        from pydantic_ai.models.openai import OpenAIResponsesModel
        from pydantic_ai.native_tools import ImageGenerationTool

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        agent = get_agent(provider="openai-responses", model="gpt-5.4")
        assert isinstance(agent, Agent)
        assert isinstance(agent.model, OpenAIResponsesModel)
        assert any(isinstance(t, ImageGenerationTool) for t in agent._cap_native_tools)

    def test_openai_compat_missing_endpoint_raises(self, app_config):
        with pytest.raises(ValueError, match="not configured"):
            get_agent(provider="openai-compat/ghost", model="x")

    def test_openai_compat_resolves_literal_api_key(self, app_config):
        app_config.set(
            "openaiCompatible",
            {
                "lmstudio": {
                    "base_url": "http://localhost:1234/v1",
                    "api_key": "literal-key",
                }
            },
        )
        agent = get_agent(provider="openai-compat/lmstudio", model="q")
        assert isinstance(agent.model, OpenAIChatModel)
        assert isinstance(agent.model._provider, OpenAIProvider)
        assert agent.model.client.api_key == "literal-key"

    def test_openai_compat_env_api_key(self, app_config, monkeypatch):
        monkeypatch.setenv("MY_LOCAL_KEY", "env-secret")
        app_config.set(
            "openaiCompatible",
            {
                "local": {
                    "base_url": "http://localhost:1234/v1",
                    "api_key": "${MY_LOCAL_KEY}",
                }
            },
        )
        agent = get_agent(provider="openai-compat/local", model="m")
        assert isinstance(agent.model, OpenAIChatModel)
        assert agent.model.client.api_key == "env-secret"

    def test_openai_compat_missing_env_falls_back_to_unresolved(
        self, app_config, monkeypatch
    ):
        """Unresolved env vars must not leak OPENAI_API_KEY to third-party endpoints."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-real")
        monkeypatch.delenv("MY_MISSING_VAR", raising=False)
        app_config.set(
            "openaiCompatible",
            {
                "sketchy": {
                    "base_url": "http://localhost:1234/v1",
                    "api_key": "${MY_MISSING_VAR}",
                }
            },
        )
        agent = get_agent(provider="openai-compat/sketchy", model="m")
        assert isinstance(agent.model, OpenAIChatModel)
        assert agent.model.client.api_key == UNRESOLVED_API_KEY
        assert agent.model.client.api_key != "sk-real"

    def test_openai_compat_no_api_key_configured(self, app_config):
        app_config.set(
            "openaiCompatible",
            {"open": {"base_url": "http://localhost:1234/v1"}},
        )
        agent = get_agent(provider="openai-compat/open", model="m")
        assert isinstance(agent.model, OpenAIChatModel)
        assert agent.model.client.api_key == UNRESOLVED_API_KEY

    def test_fallthrough_provider_uses_prefix_string(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        agent = get_agent(provider="anthropic", model="claude-4")
        model = agent.model
        assert not isinstance(model, str) and model is not None
        assert model.model_name == "claude-4"

    def test_tools_and_system_passed_through(self):
        from pydantic_ai import Tool as PydanticTool

        def hello() -> str:
            return "hi"

        tool = PydanticTool(hello, takes_ctx=False)
        agent = get_agent(
            provider="ollama",
            model="llama3",
            system="be brief",
            tools=[tool],
        )
        tool_names = [t.name for t in agent._function_toolset.tools.values()]
        assert "hello" in tool_names
