from base64 import b64encode
from io import BytesIO

import pytest
import pytest_asyncio
from PIL import Image

from oterm.ollama import OllamaAPI, OllamaError


@pytest_asyncio.fixture(autouse=True)
async def load_test_models():
    api = OllamaAPI()
    try:
        await api.get_model_info("nous-hermes:13b")
    except OllamaError:
        await api.pull_model("nous-hermes:13b")
    yield


@pytest.fixture(scope="session")
def llama_image():
    buffered = BytesIO()
    image = Image.open("tests/data/lama.jpg")
    image.save(buffered, format="JPEG")
    return b64encode(buffered.getvalue()).decode("utf-8")
