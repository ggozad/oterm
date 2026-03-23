import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from oterm.minimaxclient import (
    MiniMaxLLM,
    MiniMaxListResponse,
    MiniMaxModel,
    MiniMaxModelInfo,
    MINIMAX_MODELS_INFO,
)


@pytest_asyncio.fixture(autouse=True)
async def load_test_models():
    """Override the conftest autouse fixture that requires Ollama."""
    yield


# ---------- Unit tests for helper types ----------


class TestMiniMaxModel:
    def test_model_attribute(self):
        model = MiniMaxModel(model="MiniMax-M2.7")
        assert model.model == "MiniMax-M2.7"

    def test_size_default(self):
        model = MiniMaxModel(model="MiniMax-M2.7")
        assert model.size == 0

    def test_getitem_size(self):
        model = MiniMaxModel(model="MiniMax-M2.7", size=42)
        assert model["size"] == 42


class TestMiniMaxModelInfo:
    def test_name(self):
        info = MiniMaxModelInfo(name="MiniMax-M2.7", capabilities=["tools", "thinking"])
        assert info.name == "MiniMax-M2.7"

    def test_get_capabilities(self):
        info = MiniMaxModelInfo(name="MiniMax-M2.7", capabilities=["tools", "thinking"])
        assert info.get("capabilities") == ["tools", "thinking"]

    def test_get_system_returns_empty(self):
        info = MiniMaxModelInfo(name="MiniMax-M2.7")
        assert info.get("system", "") == ""

    def test_get_unknown_returns_default(self):
        info = MiniMaxModelInfo(name="MiniMax-M2.7")
        assert info.get("unknown_key", "fallback") == "fallback"


class TestMiniMaxListResponse:
    def test_list_response(self):
        resp = MiniMaxListResponse(models=[MiniMaxModel(model="MiniMax-M2.7")])
        assert len(resp.models) == 1
        assert resp.models[0].model == "MiniMax-M2.7"


# ---------- Unit tests for MiniMaxLLM static methods ----------


class TestMiniMaxLLMList:
    def test_list_returns_all_models(self):
        response = MiniMaxLLM.list()
        assert isinstance(response, MiniMaxListResponse)
        assert len(response.models) == len(MINIMAX_MODELS_INFO)

    def test_list_model_names(self):
        response = MiniMaxLLM.list()
        names = [m.model for m in response.models]
        assert "MiniMax-M2.7" in names
        assert "MiniMax-M2.5" in names
        assert "MiniMax-M2.5-highspeed" in names
        assert "MiniMax-M2.7-highspeed" in names


class TestMiniMaxLLMShow:
    def test_show_known_model(self):
        info = MiniMaxLLM.show("MiniMax-M2.7")
        assert isinstance(info, MiniMaxModelInfo)
        assert info.name == "MiniMax-M2.7"
        assert "tools" in info.get("capabilities", [])
        assert "thinking" in info.get("capabilities", [])

    def test_show_m25_model(self):
        info = MiniMaxLLM.show("MiniMax-M2.5")
        assert info.name == "MiniMax-M2.5"
        assert "tools" in info.get("capabilities", [])
        assert "thinking" not in info.get("capabilities", [])

    def test_show_unknown_model(self):
        info = MiniMaxLLM.show("nonexistent")
        assert info.name == "nonexistent"
        assert info.get("capabilities", []) == []


# ---------- Unit tests for think-tag parsing ----------


class TestParseThinkTags:
    def test_no_think_tags(self):
        thought, text = MiniMaxLLM._parse_think_tags("Hello, world!")
        assert thought == ""
        assert text == "Hello, world!"

    def test_complete_think_tags(self):
        content = "<think>reasoning here</think>actual response"
        thought, text = MiniMaxLLM._parse_think_tags(content)
        assert thought == "reasoning here"
        assert text == "actual response"

    def test_incomplete_think_tag(self):
        content = "<think>still thinking..."
        thought, text = MiniMaxLLM._parse_think_tags(content)
        assert thought == "still thinking..."
        assert text == ""

    def test_empty_think_tags(self):
        content = "<think></think>response only"
        thought, text = MiniMaxLLM._parse_think_tags(content)
        assert thought == ""
        assert text == "response only"


# ---------- Unit tests for temperature clamping ----------


class TestTemperatureClamping:
    def test_temperature_from_dict(self):
        llm = MiniMaxLLM(options={"temperature": 0.7})
        assert llm._get_temperature() == 0.7

    def test_temperature_clamped_high(self):
        llm = MiniMaxLLM(options={"temperature": 2.0})
        assert llm._get_temperature() == 1.0

    def test_temperature_clamped_low(self):
        llm = MiniMaxLLM(options={"temperature": -1.0})
        assert llm._get_temperature() == 0.0

    def test_temperature_none(self):
        llm = MiniMaxLLM(options={})
        assert llm._get_temperature() is None

    def test_temperature_from_options_object(self):
        from ollama import Options

        llm = MiniMaxLLM(options=Options(temperature=0.5))
        assert llm._get_temperature() == 0.5


# ---------- Unit tests for initialization ----------


class TestMiniMaxLLMInit:
    def test_default_model(self):
        llm = MiniMaxLLM()
        assert llm.model == "MiniMax-M2.7"

    def test_system_prompt_in_history(self):
        llm = MiniMaxLLM(system="You are helpful.")
        assert llm.history[0]["role"] == "system"
        assert llm.history[0]["content"] == "You are helpful."

    def test_history_from_dicts(self):
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        llm = MiniMaxLLM(history=history)
        assert len(llm.history) == 2
        assert llm.history[0]["content"] == "Hello"

    def test_history_from_ollama_messages(self):
        from ollama import Message

        msgs = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi!"),
        ]
        llm = MiniMaxLLM(history=msgs)
        assert len(llm.history) == 2
        assert llm.history[0]["role"] == "user"
        assert llm.history[1]["content"] == "Hi!"

    def test_tool_defs_conversion(self):
        from ollama import Tool

        tool = Tool(
            type="function",
            function=Tool.Function(
                name="get_time",
                description="Get current time",
                parameters=Tool.Function.Parameters(
                    type="object",
                    properties={
                        "timezone": Tool.Function.Parameters.Property(
                            type="string", description="Timezone"
                        )
                    },
                ),
            ),
        )
        llm = MiniMaxLLM(tool_defs=[{"tool": tool, "callable": lambda: "now"}])
        assert len(llm.tools) == 1
        assert llm.tools[0]["type"] == "function"


# ---------- Unit tests for streaming (mocked HTTP) ----------


def _make_sse_lines(chunks: list[dict]) -> list[str]:
    """Helper to create SSE lines from chunk dicts."""
    lines = []
    for chunk in chunks:
        lines.append(f"data: {json.dumps(chunk)}")
    lines.append("data: [DONE]")
    return lines


async def _async_iter(items):
    """Convert a list to an async iterator."""
    for item in items:
        yield item


def _mock_streaming_client(sse_lines: list[str]):
    """Create a properly mocked httpx AsyncClient for streaming."""
    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.aiter_lines = MagicMock(return_value=_async_iter(sse_lines))
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    mock_client = AsyncMock()
    mock_client.stream = MagicMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestMiniMaxLLMStream:
    @pytest.mark.asyncio
    async def test_stream_basic(self):
        chunks = [
            {
                "choices": [
                    {"delta": {"content": "Hello"}, "index": 0, "finish_reason": None}
                ]
            },
            {
                "choices": [
                    {"delta": {"content": " world"}, "index": 0, "finish_reason": "stop"}
                ]
            },
        ]
        mock_client = _mock_streaming_client(_make_sse_lines(chunks))

        with patch("oterm.minimaxclient.httpx.AsyncClient", return_value=mock_client):
            with patch("oterm.minimaxclient.envConfig") as mock_config:
                mock_config.MINIMAX_API_KEY = "test-key"
                mock_config.MINIMAX_BASE_URL = "https://api.minimax.io/v1"

                llm = MiniMaxLLM(model="MiniMax-M2.7")
                result_text = ""
                async for thought, text in llm.stream("Hi"):
                    result_text = text

                assert "Hello world" in result_text
                assert len(llm.history) >= 2  # user + assistant

    @pytest.mark.asyncio
    async def test_stream_with_thinking(self):
        chunks = [
            {
                "choices": [
                    {
                        "delta": {"content": "<think>Let me think</think>The answer"},
                        "index": 0,
                        "finish_reason": "stop",
                    }
                ]
            },
        ]
        mock_client = _mock_streaming_client(_make_sse_lines(chunks))

        with patch("oterm.minimaxclient.httpx.AsyncClient", return_value=mock_client):
            with patch("oterm.minimaxclient.envConfig") as mock_config:
                mock_config.MINIMAX_API_KEY = "test-key"
                mock_config.MINIMAX_BASE_URL = "https://api.minimax.io/v1"

                llm = MiniMaxLLM(model="MiniMax-M2.7", thinking=True)
                result_thought = ""
                result_text = ""
                async for thought, text in llm.stream("What is 1+1?"):
                    result_thought = thought
                    result_text = text

                assert result_thought == "Let me think"
                assert result_text == "The answer"

    @pytest.mark.asyncio
    async def test_stream_json_format(self):
        chunks = [
            {
                "choices": [
                    {
                        "delta": {"content": '{"answer": 42}'},
                        "index": 0,
                        "finish_reason": "stop",
                    }
                ]
            },
        ]
        mock_client = _mock_streaming_client(_make_sse_lines(chunks))

        with patch("oterm.minimaxclient.httpx.AsyncClient", return_value=mock_client):
            with patch("oterm.minimaxclient.envConfig") as mock_config:
                mock_config.MINIMAX_API_KEY = "test-key"
                mock_config.MINIMAX_BASE_URL = "https://api.minimax.io/v1"

                llm = MiniMaxLLM(model="MiniMax-M2.7", format="json")
                result_text = ""
                async for _, text in llm.stream("Give me JSON"):
                    result_text = text

                # Verify JSON format was requested
                call_args = mock_client.stream.call_args
                body = call_args.kwargs.get("json", {})
                assert body.get("response_format") == {"type": "json_object"}

    @pytest.mark.asyncio
    async def test_stream_temperature_clamping(self):
        chunks = [
            {
                "choices": [
                    {
                        "delta": {"content": "ok"},
                        "index": 0,
                        "finish_reason": "stop",
                    }
                ]
            },
        ]
        mock_client = _mock_streaming_client(_make_sse_lines(chunks))

        with patch("oterm.minimaxclient.httpx.AsyncClient", return_value=mock_client):
            with patch("oterm.minimaxclient.envConfig") as mock_config:
                mock_config.MINIMAX_API_KEY = "test-key"
                mock_config.MINIMAX_BASE_URL = "https://api.minimax.io/v1"

                llm = MiniMaxLLM(
                    model="MiniMax-M2.7", options={"temperature": 5.0}
                )
                async for _, _ in llm.stream("test"):
                    pass

                call_args = mock_client.stream.call_args
                body = call_args.kwargs.get("json", {})
                assert body.get("temperature") == 1.0


# ---------- Integration tests (require MINIMAX_API_KEY) ----------


class TestMiniMaxIntegration:
    @pytest.fixture
    def api_key(self):
        import os

        key = os.environ.get("MINIMAX_API_KEY", "")
        if not key:
            pytest.skip("MINIMAX_API_KEY not set")
        return key

    @pytest.mark.asyncio
    async def test_live_stream(self, api_key):
        llm = MiniMaxLLM(
            model="MiniMax-M2.5-highspeed",
            options={"temperature": 0.0},
        )
        result = ""
        async for _, text in llm.stream("What is 2+2? Answer with just the number."):
            result = text
        assert "4" in result

    @pytest.mark.asyncio
    async def test_live_conversation_context(self, api_key):
        llm = MiniMaxLLM(
            model="MiniMax-M2.5-highspeed",
            options={"temperature": 0.0},
        )
        async for _, _ in llm.stream("My name is oterm. Remember it."):
            pass
        result = ""
        async for _, text in llm.stream("What is my name?"):
            result = text
        assert "oterm" in result.lower()

    @pytest.mark.asyncio
    async def test_live_system_prompt(self, api_key):
        llm = MiniMaxLLM(
            model="MiniMax-M2.5-highspeed",
            system="You are a pirate. Always say 'Arrr' in your response.",
            options={"temperature": 0.0},
        )
        result = ""
        async for _, text in llm.stream("Hello"):
            result = text
        assert "arrr" in result.lower() or "arr" in result.lower()
