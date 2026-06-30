from typing import Any

from ollama import Client, ListResponse, ShowResponse

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


def parse_modelfile_parameters(params_str: str) -> dict[str, Any]:
    _KEY_MAP: dict[str, tuple[str, type]] = {
        "temperature": ("temperature", float),
        "top_p": ("top_p", float),
        "num_predict": ("max_tokens", int),
        "seed": ("seed", int),
    }
    result: dict[str, Any] = {}
    for line in params_str.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        modelfile_key, raw_value = parts
        mapping = _KEY_MAP.get(modelfile_key)
        if mapping is None:
            continue
        oterm_key, parser = mapping
        try:
            result[oterm_key] = parser(raw_value)
        except ValueError:
            pass
    return result
