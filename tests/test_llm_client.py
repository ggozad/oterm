import pytest

from oterm.ollama import OllamaError, OllamaLLM


@pytest.mark.asyncio
async def test_generate():
    llm = OllamaLLM()
    res = await llm.completion("Please add 2 and 2")
    assert "4" in res


@pytest.mark.asyncio
async def test_llm_context():
    llm = OllamaLLM()
    await llm.completion("I am testing oterm, a python client for Ollama.")
    # There should now be a context saved for the conversation.
    assert llm.context
    res = await llm.completion("Do you remember what I am testing?")
    assert "oterm" in res


@pytest.mark.asyncio
async def test_errors():
    llm = OllamaLLM(model="non-existent-model")
    try:
        await llm.completion("This should fail.")
    except OllamaError as e:
        assert "no such file or directory" in str(e)


@pytest.mark.asyncio
async def test_iterator():
    llm = OllamaLLM()
    response = ""
    async for text in llm.stream("Please add 2 and 2"):
        response = text
    assert "4" in response
