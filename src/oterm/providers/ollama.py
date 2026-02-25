from collections.abc import Iterator

from ollama import Client, ListResponse, ProgressResponse, ShowResponse

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
