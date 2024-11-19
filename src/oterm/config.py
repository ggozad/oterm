import json
import os
from pathlib import Path
from typing import Union, get_type_hints

from dotenv import load_dotenv

from oterm.utils import get_default_data_dir

load_dotenv()


class EnvConfigError(Exception):
    pass


def _parse_bool(val: Union[str, bool]) -> bool:
    return val if isinstance(val, bool) else val.lower() in ["true", "yes", "1"]


class EnvConfig:
    """
    Map environment variables to class fields according to these rules:
      - Field won't be parsed unless it has a type annotation
      - Field will be skipped if not in all caps
    """

    ENV: str = "development"
    OLLAMA_HOST: str = "127.0.0.1:11434"
    OLLAMA_URL: str = ""
    OTERM_VERIFY_SSL: bool = True
    OTERM_DATA_DIR: Path = get_default_data_dir()
    OPEN_WEATHER_MAP_API_KEY: str = ""

    def __init__(self, env):
        for field in self.__annotations__:
            if not field.isupper():
                continue

            # Raise EnvConfigError if required field not supplied
            default_value = getattr(self, field, None)
            if default_value is None and env.get(field) is None:
                raise EnvConfigError("The {} field is required".format(field))

            # Cast env var value to expected type and raise AppConfigError on failure
            try:
                var_type = get_type_hints(EnvConfig)[field]
                if var_type is bool:
                    value = _parse_bool(env.get(field, default_value))
                elif var_type == list[str]:
                    value = env.get(field)
                    if value is None:
                        value = default_value
                    else:
                        value = json.loads(value)
                else:
                    value = var_type(env.get(field, default_value))
                self.__setattr__(field, value)
            except ValueError:
                raise EnvConfigError(
                    'Unable to cast value of "{}" to type "{}" for "{}" field'.format(
                        env[field], var_type, field  # type: ignore
                    )
                )
        if self.OLLAMA_URL == "":
            self.OLLAMA_URL = f"http://{self.OLLAMA_HOST}"

    def __repr__(self):
        return str(self.__dict__)


# Expose EnvConfig object for app to import
envConfig = EnvConfig(os.environ)


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
            with open(self._path, "r") as f:
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
