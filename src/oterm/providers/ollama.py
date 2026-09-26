from typing import Any

from ollama import Client, ListResponse, ShowResponse

from oterm.config import envConfig

_MODELFILE_KEYS: dict[str, tuple[str, type]] = {
    "temperature": ("temperature", float),
    "top_p": ("top_p", float),
    "num_predict": ("max_tokens", int),
    "seed": ("seed", int),
}


def ollama_client_host() -> str:
    """OLLAMA_URL stripped of ``/v1`` so the ollama Client can append ``/api/...``.

    The ollama Python client builds endpoints like ``<host>/api/list`` from
    its ``host`` argument. If a user sets OLLAMA_URL to the OpenAI-compat
    base (ending in ``/v1``), passing it through unchanged yields URLs like
    ``host:port/v1/api/list`` which 404.
    """
    return envConfig.OLLAMA_URL.rstrip("/").removesuffix("/v1")


def openai_compat_base_url() -> str:
    """OLLAMA_URL with a single ``/v1`` suffix, regardless of how it was set."""
    return f"{ollama_client_host()}/v1"


def _client() -> Client:
    return Client(host=ollama_client_host(), verify=envConfig.OTERM_VERIFY_SSL)


def list_models() -> ListResponse:
    return _client().list()


def show_model(model: str) -> ShowResponse:
    return _client().show(model)


def parse_modelfile_parameters(params_str: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for line in params_str.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        modelfile_key, raw_value = parts
        mapping = _MODELFILE_KEYS.get(modelfile_key)
        if mapping is None:
            continue
        oterm_key, parser = mapping
        try:
            result[oterm_key] = parser(raw_value)
        except ValueError:
            pass
    return result
