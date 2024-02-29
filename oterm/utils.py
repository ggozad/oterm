import sys
from pathlib import Path


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
