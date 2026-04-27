from oterm.providers import ollama as ollama_mod
from oterm.providers.ollama import (
    ollama_client_host,
    openai_compat_base_url,
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
