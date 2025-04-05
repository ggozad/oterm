from collections.abc import AsyncGenerator
from io import BytesIO
from pathlib import Path

import ollama
import pytest
import pytest_asyncio
from mcp import StdioServerParameters
from PIL import Image

from oterm.tools.mcp.client import MCPClient


@pytest_asyncio.fixture(autouse=True)
async def load_test_models():
    try:
        ollama.show("llama3.2")
    except ollama.ResponseError:
        ollama.pull("llama3.2")
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
        "test_server": {
            "command": "mcp",
            "args": ["run", mcp_server_executable.absolute().as_posix()],
        }
    }


@pytest_asyncio.fixture(scope="function")
async def mcp_client(mcp_server_config) -> AsyncGenerator[MCPClient, None]:
    client = MCPClient(
        "test_server",
        StdioServerParameters.model_validate(mcp_server_config["test_server"]),
    )
    await client.initialize()

    yield client
    await client.cleanup()
