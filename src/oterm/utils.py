import asyncio
import sys
from collections.abc import Callable
from functools import wraps
from importlib import metadata
from pathlib import Path

import httpx
from packaging.version import Version, parse

from oterm.types import ParsedResponse


def debounce(wait: float) -> Callable:
    """
    A decorator to debounce a function, ensuring it is called only after a specified delay
    and always executes after the last call.

    Args:
        wait (float): The debounce delay in seconds.

    Returns:
        Callable: The decorated function.
    """

    def decorator(func: Callable) -> Callable:
        last_call = None
        task = None

        @wraps(func)
        async def debounced(*args, **kwargs):
            nonlocal last_call, task
            last_call = asyncio.get_event_loop().time()

            if task:
                task.cancel()

            async def call_func():
                await asyncio.sleep(wait)
                if asyncio.get_event_loop().time() - last_call >= wait:  # type: ignore
                    await func(*args, **kwargs)

            task = asyncio.create_task(call_func())

        return debounced

    return decorator


def parse_response(input_text: str) -> ParsedResponse:
    """
    Parse a response from the chatbot.
    """

    thought = ""
    response = input_text
    formatted_output = input_text

    # If the response contains a think tag, split the response into the thought process and the actual response
    thought_end = input_text.find("</think>")
    if input_text.startswith("<think>") and thought_end != -1:
        thought = input_text[7:thought_end].lstrip("\n").rstrip("\n").strip()
        response = input_text[thought_end + 8 :].lstrip("\n").rstrip("\n")
        # transform the think tag into a markdown blockquote (for clarity)
        if thought.strip():
            thought = "\n".join([f"> {line}" for line in thought.split("\n")])
            formatted_output = (
                "> ### <thought\\>\n" + thought + "\n> ### </thought\\>\n" + response
            )

    return ParsedResponse(
        thought=thought, response=response, formatted_output=formatted_output
    )


def get_default_data_dir() -> Path:
    """
    Get the user data directory for the current system platform.

    Linux: ~/.local/share/oterm
    macOS: ~/Library/Application Support/oterm
    Windows: C:/Users/<USER>/AppData/Roaming/oterm

    :return: User Data Path
    :rtype: Path
    """
    home = Path.home()

    system_paths = {
        "win32": home / "AppData/Roaming/oterm",
        "linux": home / ".local/share/oterm",
        "darwin": home / "Library/Application Support/oterm",
    }

    data_path = system_paths[sys.platform]
    return data_path


def semantic_version_to_int(version: str) -> int:
    """
    Convert a semantic version string to an integer.

    :param version: Semantic version string
    :type version: str
    :return: Integer representation of semantic version
    :rtype: int
    """
    major, minor, patch = version.split(".")
    major = int(major) << 16
    minor = int(minor) << 8
    patch = int(patch)
    return major + minor + patch


def int_to_semantic_version(version: int) -> str:
    """
    Convert an integer to a semantic version string.

    :param version: Integer representation of semantic version
    :type version: int
    :return: Semantic version string
    :rtype: str
    """
    major = version >> 16
    minor = (version >> 8) & 255
    patch = version & 255
    return f"{major}.{minor}.{patch}"


async def is_up_to_date() -> tuple[bool, Version, Version]:
    """
    Checks whether oterm is current.

    :return: A tuple containing a boolean indicating whether oterm is current, the running version and the latest version
    :rtype: tuple[bool, Version, Version]
    """

    async with httpx.AsyncClient() as client:
        running_version = parse(metadata.version("oterm"))
        try:
            response = await client.get("https://pypi.org/pypi/oterm/json")
            data = response.json()
            pypi_version = parse(data["info"]["version"])
        except Exception:
            # If no network connection, do not raise alarms.
            pypi_version = running_version
    return running_version >= pypi_version, running_version, pypi_version


async def check_ollama() -> bool:
    """
    Check if the Ollama server is up and running
    """
    from oterm.config import envConfig

    up = False
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(envConfig.OLLAMA_URL)
            up = response.status_code == 200
    except httpx.HTTPError:
        up = False
    finally:
        if not up:
            from oterm.app.oterm import app

            app.notify(
                f"The Ollama server is not reachable at {envConfig.OLLAMA_URL}, please check your connection or set the OLLAMA_URL environment variable. oterm will now quit.",
                severity="error",
                timeout=10,
            )

            async def quit():
                await asyncio.sleep(10.0)
                try:
                    from oterm.tools.mcp.setup import teardown_mcp_servers

                    await teardown_mcp_servers()
                    exit()

                except Exception:
                    pass

            asyncio.create_task(quit())
    return up
