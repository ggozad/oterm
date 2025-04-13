from difflib import get_close_matches
from typing import Any

from mcp import ClientSession
from mcp.client.session import SamplingFnT
from mcp.shared.context import RequestContext
from mcp.types import (
    CreateMessageRequestParams,
    CreateMessageResult,
    ErrorData,
    ModelHint,
    TextContent,
)
from ollama import ListResponse, Message, Options

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
        system = params.systemPrompt
        options = Options(temperature=params.temperature, stop=params.stopSequences)
        model = _DEFAULT_MODEL
        if params.modelPreferences and params.modelPreferences.hints:
            model_hints = params.modelPreferences.hints
            model_from_hints = await self.search_model(model_hints)
            if model_from_hints:
                model = model_from_hints.model or _DEFAULT_MODEL
        client = OllamaLLM(
            model=model,
            system=system,
            history=messages,
            options=options,
        )
        response = await client.completion()

        return CreateMessageResult(
            content=TextContent(text=response, type="text"),
            role="user",
            model=model,
        )

    async def search_model(self, hints: list[ModelHint]) -> ListResponse.Model | None:
        """
        Fuzzy search for a model.
        """
        log.info("Searching for model based on hints", [h.name for h in hints])
        available_models = OllamaLLM.list().models
        available_model_names = [
            model.model for model in available_models if model.model
        ]

        hint = " ".join([h.name for h in hints if h.name])
        matches = get_close_matches(hint, available_model_names, n=1, cutoff=0.1)
        if matches:
            # Return the first matching model
            for model in available_models:
                if model.model == matches[0]:
                    log.info("Found matching model", model.model)
                    return model

        # If no matches are found, return None
        log.warning("No matching model found for the provided hints.")
        return None
