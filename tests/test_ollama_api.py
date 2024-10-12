from oterm.ollamaclient import OllamaLLM, parse_ollama_parameters


def test_list():
    llm = OllamaLLM()
    response = llm.list()
    models = response.get("models", [])
    found = [model for model in models if model["name"] == "llama3.2:latest"]
    assert found


def test_show():
    llm = OllamaLLM()
    response = llm.show("llama3.2")
    for key in [
        "modelfile",
        "parameters",
        "template",
        "details",
        "model_info",
    ]:
        assert key in response.keys()

    try:
        parse_ollama_parameters(response["parameters"])
    except Exception as e:
        assert False, "Failed to parse parameters: " + str(e)


def test_pull():
    llm = OllamaLLM()
    stream = llm.pull("llama3.2:latest")
    entries = [entry for entry in stream]
    assert {"status": "pulling manifest"} in entries
    assert {"status": "success"} in entries

    stream = llm.pull("non-existing:latest")
    entries = [entry for entry in stream]
    assert {
        "status": "error",
        "message": "pull model manifest: file does not exist",
    } in entries
    assert {"status": "success"} not in entries
