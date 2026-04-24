from ast import literal_eval
from collections.abc import Iterator
from typing import Any

from ollama import Client, ListResponse, Options, ProgressResponse, ShowResponse

from oterm.config import envConfig


def list_models() -> ListResponse:
    client = Client(host=envConfig.OLLAMA_URL, verify=envConfig.OTERM_VERIFY_SSL)
    return client.list()


def show_model(model: str) -> ShowResponse:
    client = Client(host=envConfig.OLLAMA_URL, verify=envConfig.OTERM_VERIFY_SSL)
    return client.show(model)


def pull_model(model: str) -> Iterator[ProgressResponse]:
    client = Client(host=envConfig.OLLAMA_URL, verify=envConfig.OTERM_VERIFY_SSL)
    stream: Iterator[ProgressResponse] = client.pull(model, stream=True)
    yield from stream


def parse_ollama_parameters(parameter_text: str) -> dict[str, Any]:
    lines = parameter_text.split("\n")
    params: dict[str, Any] = {}
    valid_params = set(Options.model_fields.keys())
    for line in lines:
        if line:
            key, value = line.split(maxsplit=1)
            try:
                value = literal_eval(value)
            except (SyntaxError, ValueError):
                pass
            if key not in valid_params:
                continue
            if key in params:
                if not isinstance(params[key], list):
                    params[key] = [params[key], value]
                else:
                    params[key].append(value)
            else:
                params[key] = value
    return params
