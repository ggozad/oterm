from oterm.ollamaclient import OllamaLLM, parse_ollama_parameters


def test_list():
    llm = OllamaLLM()
    response = llm.list()
    models = response.get("models", [])
    assert [model for model in models if model.model == "llama3.2:latest"]


def test_show():
    llm = OllamaLLM()
    response = llm.show("llama3.2")
    assert response
    assert response.modelfile
    assert response.parameters
    assert response.template
    assert response.details
    assert response.modelinfo

    params = parse_ollama_parameters(response.parameters)
    assert params.stop == ["<|start_header_id|>", "<|end_header_id|>", "<|eot_id|>"]
    assert params.temperature is None


def test_pull():
    llm = OllamaLLM()
    stream = llm.pull("llama3.2:latest")
    entries = [entry for entry in stream]
    assert "pulling manifest" in entries
    assert "success" in entries

    stream = llm.pull("non-existing:latest")
    entries = [entry for entry in stream]
    assert {
        "status": "error",
        "message": "pull model manifest: file does not exist",
    } in entries
    assert "success" not in entries
