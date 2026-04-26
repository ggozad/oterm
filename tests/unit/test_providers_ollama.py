from oterm.providers import ollama as ollama_mod
from oterm.providers.ollama import (
    ollama_client_host,
    openai_compat_base_url,
    parse_ollama_parameters,
)


class _FakeClient:
    last_kwargs: dict = {}

    def __init__(self, host=None, verify=None):
        type(self).last_kwargs = {"host": host, "verify": verify}

    def list(self):
        return "list-response"

    def show(self, model):
        return f"show-{model}"


class TestClientWrappers:
    def test_list_models_uses_env_config(self, monkeypatch):
        import oterm.config

        monkeypatch.setattr(ollama_mod, "Client", _FakeClient)
        monkeypatch.setattr(oterm.config.envConfig, "OLLAMA_URL", "http://host:123")
        monkeypatch.setattr(oterm.config.envConfig, "OTERM_VERIFY_SSL", False)

        result = ollama_mod.list_models()
        assert result == "list-response"
        assert _FakeClient.last_kwargs == {"host": "http://host:123", "verify": False}

    def test_list_models_strips_v1_suffix(self, monkeypatch):
        """OLLAMA_URL set to the OpenAI-compat base must still work for /api/list."""
        import oterm.config

        monkeypatch.setattr(ollama_mod, "Client", _FakeClient)
        monkeypatch.setattr(oterm.config.envConfig, "OLLAMA_URL", "http://h:1/v1")
        monkeypatch.setattr(oterm.config.envConfig, "OTERM_VERIFY_SSL", True)

        ollama_mod.list_models()
        assert _FakeClient.last_kwargs["host"] == "http://h:1"

    def test_show_model_uses_env_config(self, monkeypatch):
        monkeypatch.setattr(ollama_mod, "Client", _FakeClient)
        assert ollama_mod.show_model("llama3") == "show-llama3"


class TestOllamaClientHost:
    def test_passthrough_for_plain_host(self, monkeypatch):
        import oterm.config

        monkeypatch.setattr(oterm.config.envConfig, "OLLAMA_URL", "http://h:1")
        assert ollama_client_host() == "http://h:1"

    def test_strips_v1_suffix(self, monkeypatch):
        import oterm.config

        monkeypatch.setattr(oterm.config.envConfig, "OLLAMA_URL", "http://h:1/v1")
        assert ollama_client_host() == "http://h:1"

    def test_strips_trailing_slash(self, monkeypatch):
        import oterm.config

        monkeypatch.setattr(oterm.config.envConfig, "OLLAMA_URL", "http://h:1/v1/")
        assert ollama_client_host() == "http://h:1"


class TestOpenAICompatBaseUrl:
    def test_appends_v1(self, monkeypatch):
        import oterm.config

        monkeypatch.setattr(oterm.config.envConfig, "OLLAMA_URL", "http://h:1")
        assert openai_compat_base_url() == "http://h:1/v1"

    def test_idempotent_when_already_v1(self, monkeypatch):
        import oterm.config

        monkeypatch.setattr(oterm.config.envConfig, "OLLAMA_URL", "http://h:1/v1")
        assert openai_compat_base_url() == "http://h:1/v1"

    def test_strips_trailing_slash(self, monkeypatch):
        import oterm.config

        monkeypatch.setattr(oterm.config.envConfig, "OLLAMA_URL", "http://h:1/v1/")
        assert openai_compat_base_url() == "http://h:1/v1"


class TestParseOllamaParameters:
    def test_empty_string(self):
        assert parse_ollama_parameters("") == {}

    def test_single_numeric(self):
        assert parse_ollama_parameters("temperature 0.3") == {"temperature": 0.3}

    def test_string_value_literal_eval_fallback(self):
        assert parse_ollama_parameters("mirostat_tau 5") == {"mirostat_tau": 5}

    def test_unknown_key_is_dropped(self):
        assert parse_ollama_parameters("not_a_real_option 1") == {}

    def test_repeated_key_becomes_list(self):
        params = parse_ollama_parameters("stop one\nstop two\nstop three")
        assert params == {"stop": ["one", "two", "three"]}

    def test_value_that_fails_literal_eval_kept_as_string(self):
        params = parse_ollama_parameters("stop abc")
        assert params == {"stop": "abc"}

    def test_blank_lines_ignored(self):
        params = parse_ollama_parameters("\ntemperature 0.1\n\n")
        assert params == {"temperature": 0.1}
