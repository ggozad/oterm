import pytest
from mcp.types import ImageContent, Prompt, PromptMessage, TextContent

from oterm.tools.mcp.prompts import (
    MCPPromptCallable,
    available_prompt_calls,
    available_prompt_defs,
    mcp_prompt_to_messages,
)


def test_mcp_prompt_to_messages_handles_image_content():
    messages = [
        PromptMessage(
            role="user", content=TextContent(type="text", text="describe this")
        ),
        PromptMessage(
            role="user",
            content=ImageContent(type="image", data="b64", mimeType="image/png"),
        ),
    ]
    assert mcp_prompt_to_messages(messages) == [
        {"role": "user", "content": "describe this"},
        {"role": "user", "images": ["b64"]},
    ]


def test_available_prompt_calls_flattens_registry(monkeypatch):
    monkeypatch.setitem(
        available_prompt_defs, "s1", [{"prompt": "a", "callable": None}]
    )
    monkeypatch.setitem(
        available_prompt_defs, "s2", [{"prompt": "b", "callable": None}]
    )
    flat = available_prompt_calls()
    prompts = {call["prompt"] for call in flat}
    assert {"a", "b"}.issubset(prompts)


@pytest.mark.asyncio
async def test_mcp_simple_string_prompt(mcp_client):
    prompts = await mcp_client.get_available_prompts()
    for prompt in prompts:
        assert Prompt.model_validate(prompt)

    oracle_prompt = [p for p in prompts if p.name == "oracle_prompt"][0]
    assert oracle_prompt.name == "oracle_prompt"
    assert oracle_prompt.description == "Prompt to ask the oracle a question."
    args = oracle_prompt.arguments or []
    assert len(args) == 1
    arg = args[0]
    assert arg.name == "question"
    assert arg.required

    mcpPromptCallable = MCPPromptCallable(oracle_prompt.name, "test_server", mcp_client)
    res = await mcpPromptCallable.call(question="What is the best client for Ollama?")

    assert res == [
        PromptMessage(
            role="user",
            content=TextContent(
                type="text",
                text="Oracle: What is the best client for Ollama?",
                annotations=None,
            ),
        ),
    ]

    assert mcp_prompt_to_messages(res) == [
        {"role": "user", "content": "Oracle: What is the best client for Ollama?"}
    ]


@pytest.mark.asyncio
async def test_mcp_multiple_messages_prompt(mcp_client):
    prompts = await mcp_client.get_available_prompts()
    for prompt in prompts:
        assert Prompt.model_validate(prompt)

    debug_prompt = [p for p in prompts if p.name == "debug_error"][0]
    assert debug_prompt.name == "debug_error"
    assert debug_prompt.description == "Prompt to debug an error."
    args = debug_prompt.arguments or []
    assert len(args) == 2
    arg = args[0]
    assert arg.name == "error"
    assert arg.required

    arg = args[1]
    assert arg.name == "language"
    assert arg.required == False  # noqa

    mcpPromptCallable = MCPPromptCallable(debug_prompt.name, "test_server", mcp_client)
    res = await mcpPromptCallable.call(error="Assertion error")

    assert res == [
        PromptMessage(
            role="user",
            content=TextContent(
                type="text",
                text="I'm seeing this python error: Assertion error",
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

    assert mcp_prompt_to_messages(res) == [
        {"role": "user", "content": "I'm seeing this python error: Assertion error"},
        {
            "role": "assistant",
            "content": "I'll help debug that. What have you tried so far?",
        },
    ]
