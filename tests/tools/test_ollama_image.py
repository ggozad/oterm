import base64

import pytest
from ollama import AsyncClient, RequestError, ResponseError
from ollama._types import GenerateResponse
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.messages import BinaryImage

from oterm.config import envConfig
from oterm.log import log_lines
from oterm.tools.ollama_image import generate_image


def _patch_generate(monkeypatch, response: GenerateResponse, capture: dict):
    async def fake_generate(self, **kwargs):
        capture.update(kwargs)
        return response

    monkeypatch.setattr(AsyncClient, "generate", fake_generate)


def _patch_generate_raises(monkeypatch, exc: Exception):
    async def fake_generate(self, **kwargs):
        raise exc

    monkeypatch.setattr(AsyncClient, "generate", fake_generate)


class TestGenerateImage:
    async def test_returns_binary_image_with_decoded_bytes(self, monkeypatch):
        png = b"\x89PNG\r\n\x1a\nfake-bytes"
        b64 = base64.b64encode(png).decode()
        capture: dict = {}
        _patch_generate(
            monkeypatch, GenerateResponse(response="", done=True, image=b64), capture
        )

        result = await generate_image(prompt="a red square")

        assert isinstance(result, BinaryImage)
        assert result.data == png
        assert result.media_type == "image/png"
        assert capture["prompt"] == "a red square"
        assert capture["model"] == envConfig.OTERM_OLLAMA_IMAGE_MODEL

    async def test_model_argument_overrides_default(self, monkeypatch):
        capture: dict = {}
        _patch_generate(
            monkeypatch,
            GenerateResponse(
                response="", done=True, image=base64.b64encode(b"x").decode()
            ),
            capture,
        )

        await generate_image(prompt="cat", model="x/flux2-klein")

        assert capture["model"] == "x/flux2-klein"

    async def test_missing_image_logs_and_raises_model_retry(self, monkeypatch):
        _patch_generate(
            monkeypatch,
            GenerateResponse(response="hi", done=True, image=None),
            {},
        )
        log_lines.clear()

        with pytest.raises(ModelRetry, match="did not return an image"):
            await generate_image(prompt="cat", model="qwen3")

        messages = [m for _, m in log_lines]
        assert any("qwen3" in m and "no image" in m.lower() for m in messages)

    async def test_response_error_is_logged_and_re_raised_as_retry(self, monkeypatch):
        _patch_generate_raises(monkeypatch, ResponseError("model not found", 404))
        log_lines.clear()

        with pytest.raises(ModelRetry, match="model not found"):
            await generate_image(prompt="cat", model="bogus")

        messages = [m for _, m in log_lines]
        assert any("bogus" in m and "404" in m for m in messages)

    async def test_request_error_is_logged_and_re_raised_as_retry(self, monkeypatch):
        _patch_generate_raises(monkeypatch, RequestError("connection refused"))
        log_lines.clear()

        with pytest.raises(ModelRetry, match="Could not reach Ollama"):
            await generate_image(prompt="cat", model="x/z-image-turbo")

        messages = [m for _, m in log_lines]
        assert any("connection refused" in m for m in messages)
