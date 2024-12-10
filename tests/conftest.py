from io import BytesIO

import ollama
import pytest
import pytest_asyncio
from PIL import Image


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
