from typing import Any

from pydantic_ai import Agent
from pydantic_ai import Tool as PydanticTool
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from oterm.config import envConfig


def _build_model_settings(
    parameters: dict[str, Any] | None,
    thinking: bool,
) -> ModelSettings | None:
    settings: dict[str, Any] = {}
    if parameters:
        for key in ("temperature", "top_p", "max_tokens"):
            if key in parameters:
                settings[key] = parameters[key]
    settings["thinking"] = thinking

    return ModelSettings(**settings)


def get_agent(
    provider: str = "ollama",
    model: str = "",
    system: str | None = None,
    tools: list[PydanticTool] | None = None,
    parameters: dict[str, Any] | None = None,
    thinking: bool = False,
) -> Agent[None, str]:
    if provider == "ollama":
        pydantic_model = OpenAIChatModel(
            model_name=model,
            provider=OllamaProvider(base_url=f"{envConfig.OLLAMA_URL}/v1"),
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
        pydantic_model = f"{provider}:{model}"  # type: ignore[assignment]

    agent: Agent[None, str] = Agent(
        pydantic_model,
        instructions=system,
        tools=tools or [],  # type: ignore[arg-type]
        model_settings=_build_model_settings(parameters, thinking),
    )
    return agent
