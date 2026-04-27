from io import BytesIO
from pathlib import Path

import pydantic_ai.models
import pytest
import pytest_asyncio
from PIL import Image

setattr(pydantic_ai.models, "ALLOW_MODEL_REQUESTS", False)


@pytest.fixture
def allow_model_requests():
    with pydantic_ai.models.override_allow_model_requests(True):
        yield


@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch) -> Path:
    """Isolate OTERM_DATA_DIR per test and reset the Store singleton."""
    import oterm.config
    import oterm.store.store

    monkeypatch.setattr(oterm.config.envConfig, "OTERM_DATA_DIR", tmp_path)
    monkeypatch.setattr(oterm.store.store.Store, "_store", None)
    return tmp_path


@pytest.fixture
def app_config(tmp_data_dir, monkeypatch):
    """Fresh AppConfig pointing at tmp_data_dir/config.json.

    Also swaps the module-level ``appConfig`` so code reading it sees this one.
    """
    import oterm.config
    from oterm.config import AppConfig

    cfg = AppConfig(path=tmp_data_dir / "config.json")
    monkeypatch.setattr(oterm.config.appConfig, "_data", cfg._data)
    monkeypatch.setattr(oterm.config.appConfig, "_path", cfg._path)
    return cfg


@pytest_asyncio.fixture
async def store(tmp_data_dir):
    from oterm.store.store import Store

    return await Store.get_store()


@pytest.fixture
def chat_model():
    from oterm.types import ChatModel

    return ChatModel(model="test-model", provider="ollama")


@pytest.fixture
def function_model():
    """Factory for ``FunctionModel`` instances with a scripted callable."""
    from pydantic_ai.models.function import FunctionModel

    return FunctionModel


@pytest.fixture
def test_model():
    """Factory for ``TestModel`` instances."""
    from pydantic_ai.models.test import TestModel

    return TestModel


@pytest.fixture(scope="session")
def llama_image() -> bytes:
    buffered = BytesIO()
    image = Image.open("tests/data/lama.jpg")
    image.save(buffered, format="JPEG")
    return buffered.getvalue()


@pytest.fixture(scope="session")
def mcp_server_config() -> dict:
    mcp_server_executable = Path(__file__).parent / "tools" / "mcp_servers.py"
    return {
        "stdio": {
            "command": "mcp",
            "args": ["run", mcp_server_executable.absolute().as_posix()],
        },
        "streamable_http": {
            "url": "http://localhost:8000/mcp",
        },
        "streamable_http_bearer": {
            "url": "http://localhost:8081/mcp",
            "headers": {"Authorization": "Bearer test_token"},
        },
        "ws": {
            "url": "ws://localhost:8000/ws",
        },
    }
