import sys
from pathlib import Path

import aiosqlite
from oterm.store.setup import queries as setup_queries


def get_data_dir() -> Path:
    """
    Get the user data directory for the current system platform.

    Linux: ~/.local/share/oterm
    macOS: ~/Library/Application Support/oterm
    Windows: C:/Users/<USER>/AppData/Roaming/oterm

    :return: User Data Path
    :rtype: str
    """
    home = Path.home()

    system_paths = {
        "win32": home / "AppData/Roaming/oterm",
        "linux": home / ".local/share/oterm",
        "darwin": home / "Library/Application Support/oterm",
    }

    data_path = system_paths[sys.platform]
    return data_path


class Store(object):
    @classmethod
    async def create(cls) -> "Store":
        self = Store()
        data_path = get_data_dir()
        data_path.mkdir(parents=True, exist_ok=True)
        db_path = Path(data_path / "store.db")
        async with aiosqlite.connect(db_path) as connection:
            await setup_queries.create_chat_table(connection)  # type: ignore
            await setup_queries.create_message_table(connection)  # type: ignore

        return self
