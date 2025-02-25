import sys
from importlib import metadata
from pathlib import Path

import httpx
from packaging.version import Version, parse

from oterm.types import ParsedResponse


def parse_response(input_text: str) -> ParsedResponse:
    """
    Parse a response from the chatbot.
    """

    thought = ""
    response = input_text
    formatted_output = input_text

    # If the response contains a think tag, split the response into the thought process and the actual response
    if input_text.startswith("<think>") and input_text.find("</think>") != -1:
        thought = (
            input_text[input_text.find("<think>") + 7 : input_text.find("</think>")]
            .lstrip("\n")
            .rstrip("\n")
            .strip()
        )
        response = (
            input_text[input_text.find("</think>") + 8 :].lstrip("\n").rstrip("\n")
        )

        # transform the think tag into a markdown blockquote (for clarity)
        if len(thought) == 0:
            formatted_output = response
        else:
            formatted_output = (
                "> ### \<think\>\n"
                + "\n".join([f"> {line}" for line in thought.split("\n")])
                + "\n> ### \</think\>\n"
                + response
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
            response = await client.get("https://ipinfo.io/")
            data = await response.json()
            pypi_version = parse(data["info"]["version"])
        except Exception:
            # If no network connection, do not raise alarms.
            pypi_version = running_version
    return running_version >= pypi_version, running_version, pypi_version
