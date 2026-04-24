"""Thin wrappers around ollama.Client."""

from oterm.providers import ollama as ollama_mod


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


def test_list_models_uses_env_config(monkeypatch):
    import oterm.config

    monkeypatch.setattr(ollama_mod, "Client", _FakeClient)
    monkeypatch.setattr(oterm.config.envConfig, "OLLAMA_URL", "http://host:123")
    monkeypatch.setattr(oterm.config.envConfig, "OTERM_VERIFY_SSL", False)

    result = ollama_mod.list_models()
    assert result == "list-response"
    assert _FakeClient.last_kwargs == {"host": "http://host:123", "verify": False}


def test_show_model_uses_env_config(monkeypatch):
    monkeypatch.setattr(ollama_mod, "Client", _FakeClient)
    assert ollama_mod.show_model("llama3") == "show-llama3"


def test_pull_model_yields_progress(monkeypatch):
    monkeypatch.setattr(ollama_mod, "Client", _FakeClient)
    result = list(ollama_mod.pull_model("llama3"))
    assert result == ["pull-llama3-0", "pull-llama3-1"]
