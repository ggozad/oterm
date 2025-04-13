from typing import Any

from mcp import ClientSession
from mcp.client.session import SamplingFnT
from mcp.shared.context import RequestContext
from mcp.types import (
    CreateMessageRequestParams,
    CreateMessageResult,
    ErrorData,
    TextContent,
)
from ollama import (
    Message,
)

from oterm.log import log
from oterm.ollamaclient import OllamaLLM

_DEFAULT_MODEL = "llama3.2"


class SamplingHandler(SamplingFnT):
    async def __call__(
        self,
        context: RequestContext[ClientSession, Any],
        params: CreateMessageRequestParams,
    ) -> CreateMessageResult | ErrorData:
        """Handle sampling messages.

        Args:
            context: The request context.
            params: The parameters for the message.

        Returns:
            The result of the sampling.
        """
        log.info("Request for sampling", params.model_dump_json())
        messages = [
            Message(role=msg.role, content=msg.content.text)
            for msg in params.messages
            if type(msg.content) is TextContent
        ]
        client = OllamaLLM(
            model=_DEFAULT_MODEL,
            history=messages,
        )
        response = await client.completion()

        return CreateMessageResult(
            content=TextContent(text=response, type="text"),
            role="user",
            model="llama3.2",
        )
