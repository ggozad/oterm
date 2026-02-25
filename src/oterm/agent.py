from typing import Any

from pydantic_ai import Agent
from pydantic_ai import Tool as PydanticTool
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.settings import ModelSettings

from oterm.config import envConfig

NO_THINK_SUFFIX = "/no_think"


def _build_model_settings(
    parameters: dict[str, Any] | None,
) -> ModelSettings | None:
    if not parameters:
        return None

    settings: dict[str, Any] = {}
    if "temperature" in parameters:
        settings["temperature"] = parameters["temperature"]
    if "top_p" in parameters:
        settings["top_p"] = parameters["top_p"]
    if "num_predict" in parameters:
        settings["max_tokens"] = parameters["num_predict"]
    if "max_tokens" in parameters:
        settings["max_tokens"] = parameters["max_tokens"]

    return ModelSettings(**settings) if settings else None


def _apply_thinking_mode(
    provider: str,
    system: str | None,
    thinking: bool,
) -> str:
    effective_system = system or ""

    if provider == "ollama":
        if not thinking and effective_system:
            effective_system = f"{effective_system}{NO_THINK_SUFFIX}"

    return effective_system


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
    else:
        pydantic_model = f"{provider}:{model}"  # type: ignore[assignment]

    effective_settings = _build_model_settings(parameters)
    effective_system = _apply_thinking_mode(provider, system, thinking)

    agent: Agent[None, str] = Agent(
        pydantic_model,
        instructions=effective_system,
        tools=tools or [],  # type: ignore[arg-type]
        model_settings=effective_settings,
    )
    return agent
