import pytest_asyncio

from oterm.ollama import OllamaAPI, OllamaError


@pytest_asyncio.fixture(autouse=True)
async def load_test_models():
    api = OllamaAPI()
    try:
        await api.get_model_info("nous-hermes:13b")
    except OllamaError:
        await api.pull_model("nous-hermes:13b")
    yield
