import itertools

from mcp.types import ImageContent, PromptMessage, TextContent
from ollama import Message

from oterm.log import log
from oterm.tools.mcp.client import MCPClient
from oterm.types import PromptCall

available_prompt_defs: dict[str, list[PromptCall]] = {}


def available_prompt_calls() -> list[PromptCall]:
    """Return a list of all available prompt calls."""
    return list(itertools.chain.from_iterable(available_prompt_defs.values()))


class MCPPromptCallable:
    def __init__(self, name: str, server_name: str, client: MCPClient):
        self.name = name
        self.server_name = server_name
        self.client = client

    async def call(self, **kwargs) -> list[PromptMessage]:
        log.info(f"Calling Prompt {self.name} in {self.server_name} with {kwargs}")
        res = await self.client.call_prompt(self.name, kwargs)
        log.info(f"Prompt {self.name} returned {res}")
        return res


def mcp_prompt_to_ollama_messages(mcp_prompt: list[PromptMessage]) -> list[Message]:
    """Convert an MCP prompt to Ollama messages"""

    messages: list[Message] = []
    for m in mcp_prompt:
        if isinstance(m.content, TextContent):
            messages.append(Message(role=m.role, content=m.content.text))
        elif isinstance(m.content, ImageContent):
            messages.append(Message(role=m.role, images=[m.content.data]))  # type: ignore

    return messages
