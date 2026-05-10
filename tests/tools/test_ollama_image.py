import base64

import pytest
from ollama import AsyncClient
from ollama._types import GenerateResponse
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.messages import BinaryImage

from oterm.config import envConfig
from oterm.tools.ollama_image import generate_image


def _patch_generate(monkeypatch, response: GenerateResponse, capture: dict):
    async def fake_generate(self, **kwargs):
        capture.update(kwargs)
        return response

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
        png = b"\x89PNG\r\n\x1a\nbytes"
        capture: dict = {}
        _patch_generate(
            monkeypatch,
            GenerateResponse(
                response="", done=True, image=base64.b64encode(png).decode()
            ),
            capture,
        )

        await generate_image(prompt="cat", model="x/flux2-klein")

        assert capture["model"] == "x/flux2-klein"

    async def test_env_var_changes_default_model(self, monkeypatch):
        png = b"bytes"
        capture: dict = {}
        _patch_generate(
            monkeypatch,
            GenerateResponse(
                response="", done=True, image=base64.b64encode(png).decode()
            ),
            capture,
        )
        monkeypatch.setattr(envConfig, "OTERM_OLLAMA_IMAGE_MODEL", "x/flux2-klein")

        await generate_image(prompt="cat")

        assert capture["model"] == "x/flux2-klein"

    async def test_missing_image_raises_model_retry(self, monkeypatch):
        capture: dict = {}
        _patch_generate(
            monkeypatch, GenerateResponse(response="", done=True, image=None), capture
        )

        with pytest.raises(ModelRetry, match="did not return an image"):
            await generate_image(prompt="cat", model="qwen3")

    async def test_empty_image_raises_model_retry(self, monkeypatch):
        capture: dict = {}
        _patch_generate(
            monkeypatch, GenerateResponse(response="", done=True, image=""), capture
        )

        with pytest.raises(ModelRetry, match="qwen3"):
            await generate_image(prompt="cat", model="qwen3")
