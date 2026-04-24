from unittest.mock import MagicMock

from mcp.types import (
    CreateMessageRequestParams,
    CreateMessageResult,
    ModelHint,
    ModelPreferences,
    SamplingMessage,
    TextContent,
)

from oterm.tools.mcp import sampling as sampling_mod
from oterm.tools.mcp.sampling import sampling_handler, search_model


class _FakeModel:
    def __init__(self, model: str):
        self.model = model


class _FakeListResponse:
    def __init__(self, models):
        self.models = models


class TestSearchModel:
    def test_closest_match_returned(self, monkeypatch):
        monkeypatch.setattr(
            sampling_mod.ollama,
            "list_models",
            lambda: _FakeListResponse(
                [_FakeModel("llama3"), _FakeModel("mistral:latest")]
            ),
        )
        match = search_model([ModelHint(name="mistral")])
        assert match is not None
        assert match.model == "mistral:latest"

    def test_no_match_returns_none(self, monkeypatch):
        monkeypatch.setattr(
            sampling_mod.ollama,
            "list_models",
            lambda: _FakeListResponse([]),
        )
        assert search_model([ModelHint(name="does-not-exist")]) is None


class _FakeAgent:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.prompt = None

    def run_stream(self, prompt):
        self.prompt = prompt
        return self  # acts as its own async context manager

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def stream_text(self):
        yield self.response_text


class TestSamplingHandler:
    async def test_uses_hinted_model_and_streams_response(self, monkeypatch):
        monkeypatch.setattr(
            sampling_mod.ollama,
            "list_models",
            lambda: _FakeListResponse(
                [_FakeModel("llama3"), _FakeModel("mistral:latest")]
            ),
        )

        captured = {}
        fake_agent = _FakeAgent("the answer")

        def fake_get_agent(*, model, system, parameters):
            captured["model"] = model
            captured["system"] = system
            captured["parameters"] = parameters
            return fake_agent

        monkeypatch.setattr(sampling_mod, "get_agent", fake_get_agent)

        params = CreateMessageRequestParams(
            messages=[
                SamplingMessage(
                    role="user",
                    content=TextContent(type="text", text="hello"),
                )
            ],
            maxTokens=50,
            modelPreferences=ModelPreferences(hints=[ModelHint(name="mistral")]),
            systemPrompt="be brief",
            temperature=0.1,
        )

        result = await sampling_handler(params.messages, params, MagicMock())

        assert isinstance(result, CreateMessageResult)
        assert isinstance(result.content, TextContent)
        assert result.content.text == "the answer"
        assert captured["model"] == "mistral:latest"
        assert captured["system"] == "be brief"
        assert captured["parameters"] == {"temperature": 0.1}
        assert fake_agent.prompt is not None
        assert "user: hello" in fake_agent.prompt

    async def test_falls_back_to_default_without_hints(self, monkeypatch):
        monkeypatch.setattr(
            sampling_mod.ollama,
            "list_models",
            lambda: _FakeListResponse([]),
        )

        captured = {}

        def fake_get_agent(*, model, system, parameters):
            captured["model"] = model
            return _FakeAgent("x")

        monkeypatch.setattr(sampling_mod, "get_agent", fake_get_agent)

        params = CreateMessageRequestParams(
            messages=[
                SamplingMessage(role="user", content=TextContent(type="text", text="q"))
            ],
            maxTokens=10,
        )
        await sampling_handler(params.messages, params, MagicMock())
        assert captured["model"] == sampling_mod._DEFAULT_MODEL
