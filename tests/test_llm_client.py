import pytest
from ollama import ResponseError

from oterm.ollamaclient import OllamaLLM
from oterm.tools.date_time import DateTimeTool


@pytest.mark.asyncio
async def test_generate(default_model):
    llm = OllamaLLM(model=default_model)
    res = await llm.completion(prompt="Please add 42 and 42")
    assert "84" in res


@pytest.mark.asyncio
async def test_llm_context(default_model):
    llm = OllamaLLM(model=default_model)
    await llm.completion("I am testing oterm, a python client for Ollama.")
    # There should now be a context saved for the conversation.
    res = await llm.completion("Do you remember what I am testing?")
    assert "oterm" in res.lower()


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
async def test_iterator(default_model):
    llm = OllamaLLM(model=default_model)
    response = ""
    async for _, text in llm.stream("Please add 2 and 2"):
        response = text
    assert "4" in response


@pytest.mark.asyncio
async def test_tool_streaming(default_model):
    llm = OllamaLLM(
        model=default_model,
        tool_defs=[
            {"tool": DateTimeTool, "callable": lambda: "2025-01-01"},
        ],
    )
    response = ""
    async for _, text in llm.stream(
        "What is the current date in YYYY-MM-DD format?. Use the date_time tool to answer."
    ):
        response = text
    assert "2025-01-01" in response
