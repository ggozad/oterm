from oterm.ollama import OlammaLLM, OllamaError


def test_generate():
    llm = OlammaLLM()
    res = llm.completion("Please add 2 and 2.")
    assert "4" in res


def test_llm_context():
    llm = OlammaLLM()
    llm.completion("I am testing oterm, a python client for Ollama.")
    # There should now be a context saved for the conversation.
    assert llm.context
    res = llm.completion("Do you remember what I am testing?")
    assert "oterm" in res


def test_errors():
    llm = OlammaLLM(model="non-existent-model")
    try:
        llm.completion("This should fail.")
    except Exception as e:
        assert "Error" in str(e)
