import json
import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

from oterm.utils import get_default_data_dir

load_dotenv()


class EnvConfig(BaseModel):
    ENV: str = "development"
    OLLAMA_HOST: str = "127.0.0.1:11434"
    OLLAMA_URL: str = ""
    OTERM_VERIFY_SSL: bool = True
    OTERM_DATA_DIR: Path = get_default_data_dir()
    OPEN_WEATHER_MAP_API_KEY: str = ""


envConfig = EnvConfig.model_validate(os.environ)
if envConfig.OLLAMA_URL == "":
    envConfig.OLLAMA_URL = f"http://{envConfig.OLLAMA_HOST}"


class AppConfig:
    def __init__(self, path: Path | None = None):
        if path is None:
            path = envConfig.OTERM_DATA_DIR / "config.json"
        self._path = path
        self._data = {
            "theme": "textual-dark",
            "splash-screen": True,
        }
        try:
            with open(self._path) as f:
                saved = json.load(f)
                self._data = self._data | saved
        except FileNotFoundError:
            Path.mkdir(self._path.parent, parents=True, exist_ok=True)
            self.save()

    def set(self, key, value):
        self._data[key] = value
        self.save()

    def get(self, key):
        return self._data.get(key)

    def save(self):
        with open(self._path, "w") as f:
            json.dump(self._data, f)


# Expose AppConfig object for app to import
appConfig = AppConfig()
