import sys
import types

from oterm.providers import (
    PROVIDER_ENV_VARS,
    PROVIDER_NAMES,
    UNRESOLVED_API_KEY,
    _list_models_from_api,
    _list_models_from_known,
    _resolve_api_key,
    get_all_providers,
    get_available_providers,
    get_openai_compatible_providers,
    get_provider_name,
    list_models,
)


class TestResolveApiKey:
    def test_none_returns_none(self):
        assert _resolve_api_key(None) is None

    def test_literal_returns_as_is(self):
        assert _resolve_api_key("sk-real") == "sk-real"

    def test_env_var_expansion(self, monkeypatch):
        monkeypatch.setenv("MY_KEY", "secret")
        assert _resolve_api_key("$MY_KEY") == "secret"

    def test_missing_env_var_returns_none(self, monkeypatch):
        monkeypatch.delenv("MISSING_VAR", raising=False)
        assert _resolve_api_key("$MISSING_VAR") is None

    def test_unresolved_api_key_constant(self):
        assert UNRESOLVED_API_KEY == "unresolved-api-key"


class TestGetOpenAICompatibleProviders:
    def test_empty_when_not_configured(self, app_config):
        assert get_openai_compatible_providers() == {}

    def test_returns_configured_endpoints(self, app_config):
        app_config.set(
            "openaiCompatible",
            {
                "vllm": {"base_url": "http://localhost:8000/v1"},
                "openrouter": {
                    "base_url": "https://openrouter.ai/api/v1",
                    "api_key": "$OPENROUTER_API_KEY",
                },
            },
        )
        providers = get_openai_compatible_providers()
        assert set(providers) == {"vllm", "openrouter"}

    def test_drops_entries_without_base_url(self, app_config):
        app_config.set(
            "openaiCompatible",
            {"broken": {"api_key": "x"}, "ok": {"base_url": "http://x/v1"}},
        )
        providers = get_openai_compatible_providers()
        assert "broken" not in providers
        assert "ok" in providers

    def test_non_dict_ignored(self, app_config):
        app_config.set("openaiCompatible", ["not", "a", "dict"])
        assert get_openai_compatible_providers() == {}


class TestGetProviderName:
    def test_known(self):
        assert get_provider_name("anthropic") == "Anthropic"

    def test_openai_compat_strips_prefix(self):
        assert get_provider_name("openai-compat/lmstudio") == "lmstudio"

    def test_unknown_titlecased(self):
        assert get_provider_name("weirdprov") == "Weirdprov"


class TestGetAllProviders:
    def test_returns_all_known_providers(self):
        assert set(get_all_providers()) == set(PROVIDER_ENV_VARS.keys())

    def test_names_and_env_vars_aligned(self):
        assert set(PROVIDER_ENV_VARS) == set(PROVIDER_NAMES)


class TestGetAvailableProviders:
    def test_ollama_always_available(self, monkeypatch):
        for var in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GROQ_API_KEY"):
            monkeypatch.delenv(var, raising=False)
        assert "ollama" in get_available_providers()

    def test_provider_included_when_env_var_present(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
        assert "openai" in get_available_providers()

    def test_provider_excluded_when_env_var_missing(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        assert "openai" not in get_available_providers()

    def test_bedrock_needs_both_env_vars(self, monkeypatch):
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "x")
        monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
        assert "bedrock" not in get_available_providers()

        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "y")
        assert "bedrock" in get_available_providers()

    def test_openai_compat_listed_per_endpoint(self, app_config):
        app_config.set(
            "openaiCompatible",
            {
                "vllm": {"base_url": "http://localhost:8000/v1"},
                "lmstudio": {"base_url": "http://localhost:1234/v1"},
            },
        )
        providers = get_available_providers()
        assert "openai-compat/vllm" in providers
        assert "openai-compat/lmstudio" in providers
        assert "openai-compat" not in providers

    def test_openai_compat_with_missing_env_key_is_skipped(
        self, app_config, monkeypatch
    ):
        monkeypatch.delenv("MISSING_COMPAT_KEY", raising=False)
        app_config.set(
            "openaiCompatible",
            {
                "strict": {
                    "base_url": "http://localhost:1/v1",
                    "api_key": "$MISSING_COMPAT_KEY",
                }
            },
        )
        assert "openai-compat/strict" not in get_available_providers()


class _FakeModelItem:
    def __init__(self, id: str, name: str | None = None):
        self.id = id
        self.name = name or id


class _FakeList:
    def __init__(self, items):
        self.data = items


class _FakeClient:
    """Stands in for any SDK client whose `.models.list().data` returns items."""

    def __init__(self, items, raise_on_list: Exception | None = None):
        self._items = items
        self._raise = raise_on_list

        class _Models:
            def list(inner):
                if self._raise:
                    raise self._raise
                return _FakeList(self._items)

        self.models = _Models()


def _install_fake_module(monkeypatch, fullname: str, attrs: dict):
    """Register a minimal fake module under ``fullname`` in sys.modules."""
    parts = fullname.split(".")
    for i in range(1, len(parts) + 1):
        sub = ".".join(parts[:i])
        if sub not in sys.modules:
            monkeypatch.setitem(sys.modules, sub, types.ModuleType(sub))
    mod = sys.modules[fullname]
    for k, v in attrs.items():
        monkeypatch.setattr(mod, k, v, raising=False)
    return mod


class TestListModelsFromApi:
    def test_openai(self, monkeypatch):
        items = [_FakeModelItem("gpt-4o"), _FakeModelItem("gpt-3.5-turbo")]
        _install_fake_module(
            monkeypatch, "openai", {"OpenAI": lambda **kw: _FakeClient(items)}
        )
        assert _list_models_from_api("openai") == ["gpt-3.5-turbo", "gpt-4o"]

    def test_openai_error_returns_none(self, monkeypatch):
        def boom(**kw):
            raise RuntimeError("down")

        _install_fake_module(monkeypatch, "openai", {"OpenAI": boom})
        assert _list_models_from_api("openai") is None

    def test_anthropic(self, monkeypatch):
        items = [_FakeModelItem("claude-4"), _FakeModelItem("claude-3-haiku")]
        _install_fake_module(
            monkeypatch, "anthropic", {"Anthropic": lambda: _FakeClient(items)}
        )
        assert _list_models_from_api("anthropic") == [
            "claude-3-haiku",
            "claude-4",
        ]

    def test_anthropic_error_returns_none(self, monkeypatch):
        def boom():
            raise RuntimeError("x")

        _install_fake_module(monkeypatch, "anthropic", {"Anthropic": boom})
        assert _list_models_from_api("anthropic") is None

    def test_openai_compat(self, app_config, monkeypatch):
        app_config.set(
            "openaiCompatible",
            {"vllm": {"base_url": "http://localhost:8000/v1"}},
        )
        items = [_FakeModelItem("model-a"), _FakeModelItem("model-b")]
        _install_fake_module(
            monkeypatch, "openai", {"OpenAI": lambda **kw: _FakeClient(items)}
        )
        assert _list_models_from_api("openai-compat/vllm") == ["model-a", "model-b"]

    def test_openai_compat_endpoint_missing(self, app_config):
        assert _list_models_from_api("openai-compat/ghost") is None

    def test_openai_compat_api_error(self, app_config, monkeypatch):
        app_config.set(
            "openaiCompatible", {"vllm": {"base_url": "http://localhost:8000/v1"}}
        )

        def boom(**kw):
            raise RuntimeError("nope")

        _install_fake_module(monkeypatch, "openai", {"OpenAI": boom})
        assert _list_models_from_api("openai-compat/vllm") is None

    def test_builtin_compat_groq(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "k")
        items = [_FakeModelItem("llama-3.1-70b")]
        _install_fake_module(
            monkeypatch, "openai", {"OpenAI": lambda **kw: _FakeClient(items)}
        )
        assert _list_models_from_api("groq") == ["llama-3.1-70b"]

    def test_builtin_compat_no_api_key(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        assert _list_models_from_api("groq") is None

    def test_builtin_compat_error(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "k")

        def boom(**kw):
            raise RuntimeError("x")

        _install_fake_module(monkeypatch, "openai", {"OpenAI": boom})
        assert _list_models_from_api("deepseek") is None

    def test_google_gla(self, monkeypatch):
        class _Model:
            def __init__(self, name):
                self.name = name

        class _GenaiClient:
            def __init__(self, api_key):
                self._key = api_key

            class models:
                @staticmethod
                def list():
                    return [_Model("models/gemini-pro"), _Model("models/gemini-flash")]

        _install_fake_module(
            monkeypatch,
            "google",
            {"genai": type("M", (), {"Client": _GenaiClient})()},
        )
        monkeypatch.setenv("GOOGLE_API_KEY", "k")
        assert _list_models_from_api("google-gla") == ["gemini-flash", "gemini-pro"]

    def test_google_gla_error_returns_none(self, monkeypatch):
        def boom(**kw):
            raise RuntimeError("x")

        fake = type("M", (), {"Client": boom})
        _install_fake_module(monkeypatch, "google", {"genai": fake})
        assert _list_models_from_api("google-gla") is None

    def test_mistral(self, monkeypatch):
        # Build fake mistralai sub-modules the source imports.
        class _BaseModelCard:
            pass

        class _FTModelCard:
            pass

        class _MistralModel(_BaseModelCard):
            def __init__(self, id):
                self.id = id

        class _Response:
            data = [_MistralModel("mistral-large"), _MistralModel("mistral-small")]

        class _MistralClient:
            def __init__(self, api_key):
                pass

            class models:
                @staticmethod
                def list():
                    return _Response()

        _install_fake_module(
            monkeypatch, "mistralai.client", {"Mistral": _MistralClient}
        )
        _install_fake_module(
            monkeypatch,
            "mistralai.client.models.basemodelcard",
            {"BaseModelCard": _BaseModelCard},
        )
        _install_fake_module(
            monkeypatch,
            "mistralai.client.models.ftmodelcard",
            {"FTModelCard": _FTModelCard},
        )
        monkeypatch.setenv("MISTRAL_API_KEY", "k")
        assert _list_models_from_api("mistral") == ["mistral-large", "mistral-small"]

    def test_mistral_empty_response(self, monkeypatch):
        class _Empty:
            data = None

        class _MistralClient:
            def __init__(self, api_key):
                pass

            class models:
                @staticmethod
                def list():
                    return _Empty()

        _install_fake_module(
            monkeypatch, "mistralai.client", {"Mistral": _MistralClient}
        )
        _install_fake_module(
            monkeypatch,
            "mistralai.client.models.basemodelcard",
            {"BaseModelCard": object},
        )
        _install_fake_module(
            monkeypatch,
            "mistralai.client.models.ftmodelcard",
            {"FTModelCard": object},
        )
        assert _list_models_from_api("mistral") is None

    def test_mistral_error_returns_none(self, monkeypatch):
        def boom(api_key):
            raise RuntimeError("x")

        _install_fake_module(monkeypatch, "mistralai.client", {"Mistral": boom})
        _install_fake_module(
            monkeypatch,
            "mistralai.client.models.basemodelcard",
            {"BaseModelCard": object},
        )
        _install_fake_module(
            monkeypatch,
            "mistralai.client.models.ftmodelcard",
            {"FTModelCard": object},
        )
        assert _list_models_from_api("mistral") is None

    def test_cohere(self, monkeypatch):
        class _Model:
            def __init__(self, name):
                self.name = name

        class _Response:
            models = [_Model("command-r"), _Model("command-r-plus")]

        class _CohereV2:
            def __init__(self, api_key):
                pass

            class models:
                @staticmethod
                def list():
                    return _Response()

        _install_fake_module(monkeypatch, "cohere", {"ClientV2": _CohereV2})
        monkeypatch.setenv("COHERE_API_KEY", "k")
        assert _list_models_from_api("cohere") == ["command-r", "command-r-plus"]

    def test_cohere_empty_response(self, monkeypatch):
        class _Empty:
            models = None

        class _CohereV2:
            def __init__(self, api_key):
                pass

            class models:
                @staticmethod
                def list():
                    return _Empty()

        _install_fake_module(monkeypatch, "cohere", {"ClientV2": _CohereV2})
        assert _list_models_from_api("cohere") is None

    def test_cohere_error_returns_none(self, monkeypatch):
        def boom(api_key):
            raise RuntimeError("x")

        _install_fake_module(monkeypatch, "cohere", {"ClientV2": boom})
        assert _list_models_from_api("cohere") is None

    def test_unknown_provider_returns_none(self):
        assert _list_models_from_api("noprovider") is None


class TestListModelsFromKnown:
    def test_prefix_matches(self):
        models = _list_models_from_known("openai")
        assert all(not m.startswith("openai:") for m in models)
        assert any("gpt" in m for m in models)


class TestListModels:
    def test_ollama_path(self, monkeypatch):
        from oterm.providers import ollama as ollama_mod

        class _M:
            model = "llama3"

        class _Resp:
            models = [_M()]

        monkeypatch.setattr(ollama_mod, "list_models", lambda: _Resp())
        assert list_models("ollama") == ["llama3"]

    def test_ollama_error_returns_empty(self, monkeypatch):
        from oterm.providers import ollama as ollama_mod

        def boom():
            raise RuntimeError("down")

        monkeypatch.setattr(ollama_mod, "list_models", boom)
        assert list_models("ollama") == []

    def test_non_ollama_filters_non_chat_models(self, monkeypatch):
        items = [_FakeModelItem("gpt-4o"), _FakeModelItem("text-embedding-3-small")]
        _install_fake_module(
            monkeypatch, "openai", {"OpenAI": lambda **kw: _FakeClient(items)}
        )
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        models = list_models("openai")
        assert "gpt-4o" in models
        assert "text-embedding-3-small" not in models

    def test_falls_back_to_known_list_when_api_fails(self, monkeypatch):
        def boom(**kw):
            raise RuntimeError("no network")

        _install_fake_module(monkeypatch, "openai", {"OpenAI": boom})
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        models = list_models("openai")
        assert any("gpt" in m for m in models)
