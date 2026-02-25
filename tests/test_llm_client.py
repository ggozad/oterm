import pydantic_ai.models
import pytest
from pydantic_ai import Tool as PydanticTool
from pydantic_ai.exceptions import ModelHTTPError

from oterm.agent import get_agent


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_generate(allow_model_requests, default_model, deterministic_parameters):
    agent = get_agent(model=default_model, parameters=deterministic_parameters)
    result = await agent.run("Please add 42 and 42")
    assert "84" in result.output


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_llm_context(
    allow_model_requests, default_model, deterministic_parameters
):
    agent = get_agent(model=default_model, parameters=deterministic_parameters)
    result = await agent.run("I am testing oterm, a python client for Ollama.")
    history = result.all_messages()
    result = await agent.run(
        "Do you remember what I am testing?", message_history=history
    )
    assert "oterm" in result.output.lower()


@pytest.mark.asyncio
async def test_errors():
    agent = get_agent(model="non-existent-model")
    with pytest.raises(ModelHTTPError):
        with pydantic_ai.models.override_allow_model_requests(True):
            await agent.run("This should fail.")


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_tool_streaming(
    allow_model_requests, default_model, deterministic_parameters
):
    def date_time() -> str:
        """Get the current date and time in ISO format."""
        return "2025-01-01"

    tool = PydanticTool(date_time, takes_ctx=False)
    agent = get_agent(
        model=default_model,
        tools=[tool],
        parameters=deterministic_parameters,
    )
    result = await agent.run(
        "What is the current date in YYYY-MM-DD format? Use the date_time tool to answer."
    )
    assert "2025-01-01" in result.output or (
        "January" in result.output and "2025" in result.output
    )
