import pytest
from mcp import StdioServerParameters
from mcp.types import Prompt, PromptMessage, TextContent
from ollama import Message

from oterm.tools.mcp.client import MCPClient
from oterm.tools.mcp.prompts import MCPPromptCallable, mcp_prompt_to_ollama_messages


@pytest.mark.asyncio
async def test_mcp_simple_string_prompt(mcp_server_config):
    client = MCPClient(
        "test_server",
        StdioServerParameters.model_validate(mcp_server_config["test_server"]),
    )
    await client.initialize()
    prompts = await client.get_available_prompts()
    for prompt in prompts:
        assert Prompt.model_validate(prompt)

    oracle_prompt = [p for p in prompts if p.name == "Oracle prompt"][0]
    assert oracle_prompt.name == "Oracle prompt"
    assert oracle_prompt.description == "Prompt to ask the oracle a question."
    args = oracle_prompt.arguments or []
    assert len(args) == 1
    arg = args[0]
    assert arg.name == "question"
    assert arg.required

    mcpPromptCallable = MCPPromptCallable(oracle_prompt.name, "test_server", client)
    res = await mcpPromptCallable.call(question="What is the best client for Ollama?")

    assert res.messages == [
        PromptMessage(
            role="user",
            content=TextContent(
                type="text",
                text="Oracle: What is the best client for Ollama?",
                annotations=None,
            ),
        ),
    ]

    assert mcp_prompt_to_ollama_messages(res) == [
        Message(role="user", content="Oracle: What is the best client for Ollama?")
    ]

    await client.cleanup()


@pytest.mark.asyncio
async def test_mcp_multiple_messages_prompt(mcp_server_config):
    client = MCPClient(
        "test_server",
        StdioServerParameters.model_validate(mcp_server_config["test_server"]),
    )
    await client.initialize()
    prompts = await client.get_available_prompts()
    for prompt in prompts:
        assert Prompt.model_validate(prompt)

    debug_prompt = [p for p in prompts if p.name == "Debug error"][0]
    assert debug_prompt.name == "Debug error"
    assert debug_prompt.description == "Prompt to debug an error."
    args = debug_prompt.arguments or []
    assert len(args) == 1
    arg = args[0]
    assert arg.name == "error"
    assert arg.required

    mcpPromptCallable = MCPPromptCallable(debug_prompt.name, "test_server", client)
    res = await mcpPromptCallable.call(error="Assertion error")

    assert res.messages == [
        PromptMessage(
            role="user",
            content=TextContent(
                type="text",
                text="I'm seeing this error: Assertion error",
                annotations=None,
            ),
        ),
        PromptMessage(
            role="assistant",
            content=TextContent(
                type="text",
                text="I'll help debug that. What have you tried so far?",
                annotations=None,
            ),
        ),
    ]

    assert mcp_prompt_to_ollama_messages(res) == [
        Message(role="user", content="I'm seeing this error: Assertion error"),
        Message(
            role="assistant",
            content="I'll help debug that. What have you tried so far?",
        ),
    ]

    await client.cleanup()
