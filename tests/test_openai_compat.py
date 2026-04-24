from oterm.providers import (
    UNRESOLVED_API_KEY,
    _resolve_api_key,
    get_available_providers,
    get_openai_compatible_providers,
    get_provider_name,
)


def test_get_openai_compatible_providers_empty(monkeypatch):
    from oterm.config import appConfig

    monkeypatch.setattr(appConfig, "_data", {})
    assert get_openai_compatible_providers() == {}


def test_get_openai_compatible_providers(monkeypatch):
    from oterm.config import appConfig

    monkeypatch.setattr(
        appConfig,
        "_data",
        {
            "openaiCompatible": {
                "vllm": {"base_url": "http://localhost:8000/v1"},
                "openrouter": {
                    "base_url": "https://openrouter.ai/api/v1",
                    "api_key": "$OPENROUTER_API_KEY",
                },
            }
        },
    )
    providers = get_openai_compatible_providers()
    assert "vllm" in providers
    assert "openrouter" in providers
    assert providers["vllm"]["base_url"] == "http://localhost:8000/v1"


def test_resolve_api_key(monkeypatch):
    assert _resolve_api_key(None) is None
    assert _resolve_api_key("literal-key") == "literal-key"
    monkeypatch.setenv("MY_KEY", "secret")
    assert _resolve_api_key("$MY_KEY") == "secret"
    assert _resolve_api_key("$NONEXISTENT") is None


def test_openai_compat_endpoints_listed_individually(monkeypatch):
    from oterm.config import appConfig

    monkeypatch.setattr(
        appConfig,
        "_data",
        {
            "openaiCompatible": {
                "vllm": {"base_url": "http://localhost:8000/v1"},
                "lmstudio": {"base_url": "http://localhost:1234/v1"},
            }
        },
    )
    providers = get_available_providers()
    assert "openai-compat/vllm" in providers
    assert "openai-compat/lmstudio" in providers
    assert "openai-compat" not in providers


def test_openai_compat_not_listed_when_empty(monkeypatch):
    from oterm.config import appConfig

    monkeypatch.setattr(appConfig, "_data", {})
    providers = get_available_providers()
    assert not any(p.startswith("openai-compat") for p in providers)


def test_provider_name_for_openai_compat():
    assert get_provider_name("openai-compat/lmstudio") == "lmstudio"
    assert get_provider_name("openai-compat/my-vllm") == "my-vllm"


def test_missing_endpoint_raises_clear_error(monkeypatch):
    """get_agent must raise a clear error if the endpoint isn't configured."""
    import pytest

    from oterm.agent import get_agent
    from oterm.config import appConfig

    monkeypatch.setattr(appConfig, "_data", {})
    with pytest.raises(ValueError, match="not configured"):
        get_agent(provider="openai-compat/gone", model="some-model")


def test_unresolved_api_key_does_not_leak_openai_key(monkeypatch):
    """Ensure we never let the OpenAI client fall back to OPENAI_API_KEY.

    A user configuring `api_key: "$MISSING_VAR"` for a local endpoint, or
    omitting `api_key` entirely, must not cause their OPENAI_API_KEY to be
    sent to that endpoint.
    """
    from oterm.agent import get_agent
    from oterm.config import appConfig

    monkeypatch.setattr(
        appConfig,
        "_data",
        {
            "openaiCompatible": {
                "local": {
                    "base_url": "http://localhost:1234/v1",
                    "api_key": "$NONEXISTENT_VAR",
                },
            }
        },
    )
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real-openai-key")
    monkeypatch.delenv("NONEXISTENT_VAR", raising=False)

    agent = get_agent(provider="openai-compat/local", model="some-model")
    model = agent.model
    openai_client = model.client  # ty: ignore[unresolved-attribute]
    assert openai_client.api_key == UNRESOLVED_API_KEY
    assert openai_client.api_key != "sk-real-openai-key"
