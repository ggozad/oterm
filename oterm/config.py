import json
import os
from typing import Union, get_type_hints

from dotenv import load_dotenv

load_dotenv()


class AppConfigError(Exception):
    pass


def _parse_bool(val: Union[str, bool]) -> bool:
    return val if isinstance(val, bool) else val.lower() in ["true", "yes", "1"]


class AppConfig:
    """
    Map environment variables to class fields according to these rules:
      - Field won't be parsed unless it has a type annotation
      - Field will be skipped if not in all caps
    """

    ENV: str = "development"
    OLLAMA_HOST: str = "0.0.0.0:11434"
    OLLAMA_URL: str = ""
    OTERM_VERIFY_SSL: bool = True

    def __init__(self, env):
        for field in self.__annotations__:
            if not field.isupper():
                continue

            # Raise AppConfigError if required field not supplied
            default_value = getattr(self, field, None)
            if default_value is None and env.get(field) is None:
                raise AppConfigError("The {} field is required".format(field))

            # Cast env var value to expected type and raise AppConfigError on failure
            try:
                var_type = get_type_hints(AppConfig)[field]
                if var_type == bool:
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
                raise AppConfigError(
                    'Unable to cast value of "{}" to type "{}" for "{}" field'.format(
                        env[field], var_type, field  # type: ignore
                    )
                )
        if self.OLLAMA_URL == "":
            self.OLLAMA_URL = f"http://{self.OLLAMA_HOST}/api"

    def __repr__(self):
        return str(self.__dict__)


# Expose Config object for app to import
Config = AppConfig(os.environ)
