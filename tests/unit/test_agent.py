import pytest
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.providers.openai import OpenAIProvider

from oterm.agent import _build_model_settings, get_agent
from oterm.providers import UNRESOLVED_API_KEY


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
    def test_ollama_provider(self):
        agent = get_agent(provider="ollama", model="llama3")
        assert isinstance(agent, Agent)
        assert isinstance(agent.model, OpenAIChatModel)
        assert isinstance(agent.model._provider, OllamaProvider)

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
                    "api_key": "$MY_LOCAL_KEY",
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
                    "api_key": "$MY_MISSING_VAR",
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

    def test_fallthrough_provider_uses_prefix_string(self):
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
