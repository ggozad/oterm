from mcp import GetPromptResult
from textual import log

from oterm.tools.mcp.client import MCPClient


class MCPPromptCallable:
    def __init__(self, name: str, server_name: str, client: MCPClient):
        self.name = name
        self.server_name = server_name
        self.client = client

    async def call(self, **kwargs) -> GetPromptResult:
        log.info(f"Calling Prompt {self.name} in {self.server_name} with {kwargs}")
        res = await self.client.call_prompt(self.name, kwargs)
        log.info(f"Prompt {self.name} returned {res}")
        return res
