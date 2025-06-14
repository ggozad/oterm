import pytest
from ollama import ResponseError

from oterm.ollamaclient import OllamaLLM
from oterm.tools.date_time import DateTimeTool


@pytest.mark.asyncio
async def test_generate(default_model):
    llm = OllamaLLM(model=default_model)
    res = ""
    async for _, text in llm.stream(prompt="Please add 42 and 42"):
        res = text
    assert "84" in res


@pytest.mark.asyncio
async def test_llm_context(default_model):
    llm = OllamaLLM(model=default_model)
    async for _, _ in llm.stream("I am testing oterm, a python client for Ollama."):
        pass
    # There should now be a context saved for the conversation.
    res = ""
    async for _, text in llm.stream("Do you remember what I am testing?"):
        res = text
    assert "oterm" in res.lower()


@pytest.mark.asyncio
async def test_multi_modal_llm(llama_image):
    llm = OllamaLLM(model="llava")
    res = ""
    async for _, text in llm.stream("Describe this image", images=[llama_image]):
        res = text
    assert "llama" in res or "animal" in res


@pytest.mark.asyncio
async def test_errors():
    llm = OllamaLLM(model="non-existent-model")
    try:
        async for _, _ in llm.stream("This should fail."):
            pass
    except ResponseError as e:
        assert 'model "non-existent-model" not found' in str(e)


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
    assert "2025-01-01" in response or ("January" in response and "2025" in response)
