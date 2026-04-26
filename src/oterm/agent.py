from typing import Any

from pydantic_ai import Agent
from pydantic_ai import Tool as PydanticTool
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings
from pydantic_ai.toolsets import AbstractToolset

from oterm.providers.ollama import openai_compat_base_url


def _build_model_settings(
    parameters: dict[str, Any] | None,
    thinking: bool,
    provider: str,
) -> ModelSettings:
    settings: dict[str, Any] = {}
    if parameters:
        for key in ("temperature", "top_p", "max_tokens"):
            if key in parameters:
                settings[key] = parameters[key]
    settings["thinking"] = thinking

    # Anthropic rejects temperature / top_p when extended thinking is on
    # (must be temperature=1 and top_p>=0.95). pydantic-ai only auto-drops
    # these for Opus 4.7+, so handle every other thinking-capable Anthropic
    # model here. Anthropic also requires max_tokens > thinking.budget_tokens
    # (pydantic-ai uses 10000 for thinking=True), so bump it if needed.
    if thinking and provider == "anthropic":
        settings.pop("temperature", None)
        settings.pop("top_p", None)
        # 10000 (pydantic-ai's default thinking.budget_tokens) + 4096 output buffer.
        min_max_tokens = 14096
        if settings.get("max_tokens", 0) < min_max_tokens:
            settings["max_tokens"] = min_max_tokens

    return ModelSettings(**settings)


def get_agent(
    provider: str = "ollama",
    model: str = "",
    system: str | None = None,
    tools: list[PydanticTool] | None = None,
    toolsets: list[AbstractToolset[None]] | None = None,
    parameters: dict[str, Any] | None = None,
    thinking: bool = False,
) -> Agent[None, str]:
    pydantic_model: OpenAIChatModel | str
    if provider == "ollama":
        pydantic_model = OllamaModel(
            model_name=model,
            provider=OllamaProvider(base_url=openai_compat_base_url()),
        )
    elif provider.startswith("openai-compat/"):
        from oterm.providers import (
            UNRESOLVED_API_KEY,
            _resolve_api_key,
            get_openai_compatible_providers,
        )

        endpoint_name = provider.removeprefix("openai-compat/")
        config = get_openai_compatible_providers().get(endpoint_name)
        if config is None:
            raise ValueError(
                f"OpenAI-compatible endpoint {endpoint_name!r} is not configured. "
                f"Add it to the `openaiCompatible` section of your config.json."
            )
        api_key = _resolve_api_key(config.get("api_key")) or UNRESOLVED_API_KEY
        pydantic_model = OpenAIChatModel(
            model_name=model,
            provider=OpenAIProvider(
                base_url=config["base_url"],
                api_key=api_key,
            ),
        )
    else:
        pydantic_model = f"{provider}:{model}"

    agent: Agent[None, str] = Agent(
        pydantic_model,
        instructions=system,
        tools=tools or [],
        toolsets=toolsets or [],
        model_settings=_build_model_settings(parameters, thinking, provider),
    )
    return agent
