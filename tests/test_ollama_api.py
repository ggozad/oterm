import pytest
from ollama import ResponseError

from oterm.providers import ollama
from oterm.providers.ollama import parse_ollama_parameters


def test_list():
    response = ollama.list_models()
    models = response.models
    assert [model for model in models if model.model == "gpt-oss:latest"]


def test_show():
    response = ollama.show_model("gpt-oss:latest")
    assert response
    assert response.modelfile
    assert response.details
    assert response.modelinfo

    assert response.capabilities is not None
    assert "tools" in response.capabilities
    assert "completion" in response.capabilities

    if response.parameters:
        params = parse_ollama_parameters(response.parameters)
        assert params  # Non-empty dict


def test_pull():
    stream = ollama.pull_model("gpt-oss:latest")
    entries = [entry.status for entry in stream]
    assert "pulling manifest" in entries
    assert "success" in entries

    with pytest.raises(ResponseError) as excinfo:
        stream = ollama.pull_model("non-existing:latest")
        entries = [entry for entry in stream]
        assert excinfo.value == "pull model manifest: file does not exist"
        assert "success" not in entries
