import base64

from ollama import AsyncClient, RequestError, ResponseError
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.messages import BinaryImage

from oterm.config import envConfig
from oterm.log import log
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
    try:
        response = await client.generate(model=chosen, prompt=prompt)
    except ResponseError as exc:
        log.error(
            f"Ollama refused generate_image (model={chosen!r}, "
            f"status={exc.status_code}): {exc.error}"
        )
        raise ModelRetry(
            f"Ollama returned an error for model {chosen!r}: {exc.error}"
        ) from exc
    except RequestError as exc:
        log.error(f"Ollama request error for generate_image (model={chosen!r}): {exc}")
        raise ModelRetry(f"Could not reach Ollama for model {chosen!r}: {exc}") from exc
    except Exception as exc:  # pragma: no cover
        log.error(f"generate_image failed (model={chosen!r}): {exc!r}")
        raise

    if not response.image:
        log.error(
            f"generate_image got no image bytes from Ollama (model={chosen!r}, "
            f"done={response.done}, response_text={response.response!r})"
        )
        raise ModelRetry(
            f"Model {chosen!r} did not return an image. "
            "Pick an Ollama image-generation model (e.g. 'x/z-image-turbo')."
        )
    return BinaryImage(data=base64.b64decode(response.image), media_type="image/png")
