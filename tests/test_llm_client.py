import pytest
from ollama import ResponseError

from oterm.ollamaclient import OllamaLLM


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
    res = await llm.completion("Do you remember what I am testing?")
    assert "oterm" in res


@pytest.mark.asyncio
async def test_multi_modal_llm(llama_image):
    llm = OllamaLLM(model="llava")
    res = await llm.completion("Describe this image", images=[llama_image])
    assert "llama" in res or "animal" in res


@pytest.mark.asyncio
async def test_errors():
    llm = OllamaLLM(model="non-existent-model")
    try:
        await llm.completion("This should fail.")
    except ResponseError as e:
        assert 'model "non-existent-model" not found' in str(e)


@pytest.mark.asyncio
async def test_iterator():
    llm = OllamaLLM()
    response = ""
    async for text in llm.stream("Please add 2 and 2"):
        response = text
    assert "4" in response
