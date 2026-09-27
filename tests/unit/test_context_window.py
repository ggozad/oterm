import pytest

from oterm.providers import openai_compat_context_window
from oterm.providers.ollama import running_context_length
from tests._helpers import json_server, refused_url

MODELS = {
    "/v1/models": {
        "object": "list",
        "data": [
            {"id": "embedder", "object": "model", "created": 0, "owned_by": "x"},
            {
                "id": "Custom/Q-27B",
                "object": "model",
                "created": 0,
                "owned_by": "vllm",
                "max_model_len": 262144,
            },
        ],
    }
}


class TestOpenAICompatContextWindow:
    @pytest.fixture
    def endpoint(self, app_config):
        def _set(base_url: str) -> None:
            app_config.set("openaiCompatible", {"local": {"base_url": base_url}})

        return _set

    def test_reads_max_model_len_for_the_model(self, endpoint):
        with json_server(MODELS) as url:
            endpoint(f"{url}/v1")
            assert openai_compat_context_window("local", "Custom/Q-27B") == 262144

    def test_none_when_the_server_does_not_report_it(self, endpoint):
        with json_server(MODELS) as url:
            endpoint(f"{url}/v1")
            assert openai_compat_context_window("local", "embedder") is None

    def test_none_when_the_model_is_not_listed(self, endpoint):
        with json_server(MODELS) as url:
            endpoint(f"{url}/v1")
            assert openai_compat_context_window("local", "other") is None

    def test_none_when_the_server_is_unreachable(self, endpoint):
        endpoint(f"{refused_url()}/v1")
        assert openai_compat_context_window("local", "Custom/Q-27B") is None

    def test_falls_back_to_lm_studio_loaded_context_length(self, endpoint):
        routes = {
            "/v1/models": {
                "object": "list",
                "data": [
                    {"id": "gemma", "object": "model", "created": 0, "owned_by": "x"}
                ],
            },
            "/api/v0/models": {
                "data": [
                    {
                        "id": "gemma",
                        "max_context_length": 262144,
                        "loaded_context_length": 4096,
                    }
                ]
            },
        }
        with json_server(routes) as url:
            endpoint(f"{url}/v1")
            assert openai_compat_context_window("local", "gemma") == 4096

    def test_none_when_lm_studio_has_not_loaded_the_model(self, endpoint):
        routes = {
            "/v1/models": {
                "object": "list",
                "data": [
                    {"id": "gemma", "object": "model", "created": 0, "owned_by": "x"}
                ],
            },
            "/api/v0/models": {"data": [{"id": "gemma", "max_context_length": 262144}]},
        }
        with json_server(routes) as url:
            endpoint(f"{url}/v1")
            assert openai_compat_context_window("local", "gemma") is None

    def test_none_for_an_unconfigured_endpoint(self, app_config):
        assert openai_compat_context_window("ghost", "m") is None


class TestOllamaRunningContextLength:
    @pytest.fixture
    def ollama_at(self, monkeypatch):
        import oterm.config

        def _set(url: str) -> None:
            monkeypatch.setattr(oterm.config.envConfig, "OLLAMA_URL", url)

        return _set

    def test_reads_the_loaded_model_context_length(self, ollama_at):
        ps = {
            "/api/ps": {
                "models": [
                    {
                        "name": "qwen3.8:27b",
                        "model": "qwen3.8:27b",
                        "context_length": 8192,
                    },
                    {
                        "name": "gpt-oss:20b",
                        "model": "gpt-oss:20b",
                        "context_length": 32768,
                    },
                ]
            }
        }
        with json_server(ps) as url:
            ollama_at(url)
            assert running_context_length("gpt-oss:20b") == 32768

    def test_none_when_the_model_is_not_loaded(self, ollama_at):
        with json_server({"/api/ps": {"models": []}}) as url:
            ollama_at(url)
            assert running_context_length("gpt-oss:20b") is None

    def test_gives_up_on_a_hung_server(self, ollama_at, monkeypatch):
        import time

        import oterm.providers

        monkeypatch.setattr(oterm.providers, "LOOKUP_TIMEOUT", 0.2)
        with json_server({"/api/ps": {"models": []}}, delay=2) as url:
            ollama_at(url)
            started = time.monotonic()
            assert running_context_length("gpt-oss:20b") is None
            assert time.monotonic() - started < 1.5

    def test_none_when_ollama_is_unreachable(self, ollama_at):
        ollama_at(refused_url())
        assert running_context_length("gpt-oss:20b") is None
