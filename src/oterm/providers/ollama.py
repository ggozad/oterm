from ast import literal_eval
from typing import Any

from ollama import Client, ListResponse, Options, ShowResponse

from oterm.config import envConfig


def openai_compat_base_url() -> str:
    """OLLAMA_URL with a single ``/v1`` suffix, regardless of how it was set."""
    base = envConfig.OLLAMA_URL.rstrip("/")
    if base.endswith("/v1"):
        return base
    return f"{base}/v1"


def ollama_client_host() -> str:
    """OLLAMA_URL stripped of ``/v1`` so the ollama Client can append ``/api/...``.

    The ollama Python client builds endpoints like ``<host>/api/list`` from
    its ``host`` argument. If a user sets OLLAMA_URL to the OpenAI-compat
    base (ending in ``/v1``), passing it through unchanged yields URLs like
    ``host:port/v1/api/list`` which 404.
    """
    base = envConfig.OLLAMA_URL.rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    return base


def list_models() -> ListResponse:
    client = Client(host=ollama_client_host(), verify=envConfig.OTERM_VERIFY_SSL)
    return client.list()


def show_model(model: str) -> ShowResponse:
    client = Client(host=ollama_client_host(), verify=envConfig.OTERM_VERIFY_SSL)
    return client.show(model)


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
