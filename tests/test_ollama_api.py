import pytest
from ollama import ResponseError

from oterm.ollamaclient import OllamaLLM, jsonify_options, parse_ollama_parameters


def test_list():
    llm = OllamaLLM()
    response = llm.list()
    models = response.get("models", [])
    assert [model for model in models if model.model == "llama3.2:latest"]


def test_show():
    llm = OllamaLLM()
    response = llm.show("llama3.2:latest")
    assert response
    assert response.modelfile
    assert response.parameters
    assert response.template
    assert response.details
    assert response.modelinfo
    assert response.capabilities

    assert "tools" in response.capabilities
    assert "completion" in response.capabilities
    params = parse_ollama_parameters(response.parameters)
    assert params.stop == ["<|start_header_id|>", "<|end_header_id|>", "<|eot_id|>"]
    assert params.temperature is None
    json = jsonify_options(params)
    assert json == (
        "{\n"
        '  "stop": [\n'
        '    "<|start_header_id|>",\n'
        '    "<|end_header_id|>",\n'
        '    "<|eot_id|>"\n'
        "  ]\n"
        "}"
    )


def test_pull():
    llm = OllamaLLM()
    stream = llm.pull("llama3.2:latest")
    entries = [entry.status for entry in stream]
    assert "pulling manifest" in entries
    assert "success" in entries

    with pytest.raises(ResponseError) as excinfo:
        stream = llm.pull("non-existing:latest")
        entries = [entry for entry in stream]
        assert excinfo.value == "pull model manifest: file does not exist"
        assert "success" not in entries
