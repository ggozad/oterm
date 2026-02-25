import logging
import os
from collections.abc import AsyncGenerator
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any

import ollama
import pydantic_ai.models
import pytest
import pytest_asyncio
from mcp import StdioServerParameters
from PIL import Image

from oterm.tools.mcp.client import MCPClient

if TYPE_CHECKING:
    from vcr import VCR

setattr(pydantic_ai.models, "ALLOW_MODEL_REQUESTS", False)
logging.getLogger("vcr.cassette").setLevel(logging.WARNING)

DEFAULT_MODEL = "gpt-oss"


@pytest_asyncio.fixture(autouse=True)
async def load_test_models():
    try:
        ollama.show(DEFAULT_MODEL)
    except ollama.ResponseError:
        ollama.pull(DEFAULT_MODEL)
    yield


@pytest.fixture(scope="session")
def default_model() -> str:
    return DEFAULT_MODEL


@pytest.fixture(scope="session")
def deterministic_parameters() -> dict[str, Any]:
    """Parameters for deterministic test responses."""
    return {"temperature": 0.0}


@pytest.fixture
def allow_model_requests():
    with pydantic_ai.models.override_allow_model_requests(True):
        yield


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
            "auth": {
                "type": "bearer",
                "token": "test_token",
            },
        },
        "ws": {
            "url": "ws://localhost:8000/ws",
        },
    }


@pytest_asyncio.fixture(scope="function")
async def mcp_client(mcp_server_config) -> AsyncGenerator[MCPClient, None]:
    client = MCPClient(
        "test_server",
        StdioServerParameters.model_validate(mcp_server_config["stdio"]),
    )
    await client.initialize()

    yield client
    await client.teardown()


@pytest.fixture(autouse=True)
def set_mock_api_keys(monkeypatch):
    """Set mock API keys for providers that require them during VCR playback."""
    if not os.getenv("OPENAI_API_KEY"):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-mock-key-for-vcr-playback")
    if not os.getenv("ANTHROPIC_API_KEY"):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-mock-key-for-vcr-playback")
    if not os.getenv("GROQ_API_KEY"):
        monkeypatch.setenv("GROQ_API_KEY", "mock-groq-key-for-vcr-playback")
    if not os.getenv("GOOGLE_API_KEY"):
        monkeypatch.setenv("GOOGLE_API_KEY", "mock-google-key-for-vcr-playback")


def pytest_recording_configure(config: Any, vcr: "VCR"):
    from . import json_body_serializer

    vcr.register_serializer("yaml", json_body_serializer)


@pytest.fixture(scope="module")
def vcr_config():
    return {
        "ignore_localhost": False,
        "filter_headers": ["authorization", "x-api-key"],
        "decode_compressed_response": True,
    }
