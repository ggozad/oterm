import pytest

from oterm.ollama import OllamaAPI


@pytest.mark.asyncio
async def test_get_models():
    api = OllamaAPI()
    models = await api.get_models()
    assert [m for m in models if m["name"] == "nous-hermes:13b"]


@pytest.mark.asyncio
async def test_get_model_info():
    api = OllamaAPI()
    info = await api.get_model_info("nous-hermes:13b")
    assert "modelfile" in info.keys()
    assert "template" in info.keys()
    assert "system" in info.keys()
