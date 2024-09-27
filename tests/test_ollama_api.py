from oterm.ollamaclient import OllamaLLM, parse_ollama_parameters


def test_list():
    llm = OllamaLLM()
    response = llm.list()
    models = response.get("models", [])
    found = [model for model in models if model["name"] == "llama3.1:latest"]
    assert found


def test_show():
    llm = OllamaLLM()
    response = llm.show("llama3.1")
    print(response.keys())
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
