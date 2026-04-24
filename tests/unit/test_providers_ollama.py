from oterm.providers import ollama as ollama_mod
from oterm.providers.ollama import parse_ollama_parameters


class _FakeClient:
    last_kwargs: dict = {}

    def __init__(self, host=None, verify=None):
        type(self).last_kwargs = {"host": host, "verify": verify}

    def list(self):
        return "list-response"

    def show(self, model):
        return f"show-{model}"

    def pull(self, model, stream=False):
        assert stream is True
        yield f"pull-{model}-0"
        yield f"pull-{model}-1"


class TestClientWrappers:
    def test_list_models_uses_env_config(self, monkeypatch):
        import oterm.config

        monkeypatch.setattr(ollama_mod, "Client", _FakeClient)
        monkeypatch.setattr(oterm.config.envConfig, "OLLAMA_URL", "http://host:123")
        monkeypatch.setattr(oterm.config.envConfig, "OTERM_VERIFY_SSL", False)

        result = ollama_mod.list_models()
        assert result == "list-response"
        assert _FakeClient.last_kwargs == {"host": "http://host:123", "verify": False}

    def test_show_model_uses_env_config(self, monkeypatch):
        monkeypatch.setattr(ollama_mod, "Client", _FakeClient)
        assert ollama_mod.show_model("llama3") == "show-llama3"

    def test_pull_model_yields_progress(self, monkeypatch):
        monkeypatch.setattr(ollama_mod, "Client", _FakeClient)
        result = list(ollama_mod.pull_model("llama3"))
        assert result == ["pull-llama3-0", "pull-llama3-1"]


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
