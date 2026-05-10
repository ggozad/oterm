import base64

from ollama import AsyncClient
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.messages import BinaryImage

from oterm.config import envConfig
from oterm.providers.ollama import ollama_client_host


async def generate_image(prompt: str, model: str | None = None) -> BinaryImage:
    """Generate an image from a text prompt using an Ollama image-generation model.

    Use this when the user asks to create, draw, render, or visualize an image.

    Args:
        prompt: A descriptive prompt for the image to generate.
        model: Optional Ollama image model name. Defaults to OTERM_OLLAMA_IMAGE_MODEL.
    """
    chosen = model or envConfig.OTERM_OLLAMA_IMAGE_MODEL
    client = AsyncClient(host=ollama_client_host(), verify=envConfig.OTERM_VERIFY_SSL)
    response = await client.generate(model=chosen, prompt=prompt)
    if not response.image:
        raise ModelRetry(
            f"Model {chosen!r} did not return an image. "
            "Pick an Ollama image-generation model (e.g. 'x/z-image-turbo')."
        )
    return BinaryImage(data=base64.b64decode(response.image), media_type="image/png")
