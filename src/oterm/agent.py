import os
from typing import Any

from pydantic_ai import Agent
from pydantic_ai import Tool as PydanticTool
from pydantic_ai.capabilities import AbstractCapability, NativeTool
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIResponsesModel
from pydantic_ai.native_tools import ImageGenerationTool
from pydantic_ai.profiles import ModelProfile, merge_profile
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings
from pydantic_ai.toolsets import AbstractToolset

from oterm.config import envConfig
from oterm.providers import (
    BUILTIN_OPENAI_COMPAT,
    UNRESOLVED_API_KEY,
    openai_compat_endpoint,
)
from oterm.providers.capabilities import get_capabilities
from oterm.providers.ollama import openai_compat_base_url
from oterm.providers.settings import get_supported_setting_keys


def _build_model_settings(
    parameters: dict[str, Any] | None,
    thinking: bool,
    provider: str,
) -> ModelSettings:
    settings: dict[str, Any] = {}
    if parameters:
        supported = get_supported_setting_keys(provider)
        for key, value in parameters.items():
            if key in supported:
                settings[key] = value
    settings["thinking"] = thinking

    # Anthropic rejects temperature / top_p when extended thinking is on
    # (must be temperature=1 and top_p>=0.95). pydantic-ai only auto-drops
    # these for Opus 4.7+, so handle every other thinking-capable Anthropic
    # model here. Anthropic also requires max_tokens > thinking.budget_tokens.
    if thinking and provider == "anthropic":
        settings.pop("temperature", None)
        settings.pop("top_p", None)
        # pydantic-ai's thinking=True budget of 10000, plus 4096 for the answer.
        min_max_tokens = 14096
        if settings.get("max_tokens", 0) < min_max_tokens:
            settings["max_tokens"] = min_max_tokens

    # pydantic-ai drops `thinking` for model names its profiles don't recognise,
    # which is most models behind OpenAI-compatible servers. vLLM and oMLX read
    # this chat-template switch instead; servers that don't know it ignore it.
    if not thinking and provider.startswith("openai-compat/"):
        settings["extra_body"] = {
            **(settings.get("extra_body") or {}),
            "chat_template_kwargs": {"enable_thinking": False},
        }

    return ModelSettings(**settings)


def get_agent(
    provider: str = "ollama",
    model: str = "",
    system: str | None = None,
    tools: list[PydanticTool] | None = None,
    toolsets: list[AbstractToolset[None]] | None = None,
    capabilities: list[AbstractCapability[None]] | None = None,
    parameters: dict[str, Any] | None = None,
    thinking: bool = False,
) -> Agent[None, str]:
    pydantic_model: OpenAIChatModel | OpenAIResponsesModel | str
    capabilities = list(capabilities) if capabilities else []
    if provider == "ollama":
        ollama_provider = OllamaProvider(
            base_url=openai_compat_base_url(),
            api_key=envConfig.OLLAMA_API_KEY or "ollama",
        )
        # Ollama's pydantic-ai profiles don't mark thinking-capable models as
        # supporting thinking, so the unified `thinking` setting is dropped
        # before the request and thinking can't be turned off. Ollama itself
        # reports the capability, so trust that and let the setting through.
        profile = ollama_provider.model_profile(model)
        if profile is not None and get_capabilities(provider, model).supports_thinking:
            profile = merge_profile(profile, ModelProfile(supports_thinking=True))
        pydantic_model = OpenAIChatModel(
            model_name=model,
            provider=ollama_provider,
            profile=profile,
        )
    elif provider == "openai-responses":
        pydantic_model = OpenAIResponsesModel(model_name=model)
        capabilities.append(NativeTool(ImageGenerationTool()))
    elif provider.startswith("openai-compat/"):
        endpoint_name = provider.removeprefix("openai-compat/")
        endpoint = openai_compat_endpoint(endpoint_name)
        if endpoint is None:
            raise ValueError(
                f"OpenAI-compatible endpoint {endpoint_name!r} is not configured. "
                f"Add it to the `openaiCompatible` section of your config.json."
            )
        base_url, api_key = endpoint
        pydantic_model = OpenAIChatModel(
            model_name=model,
            provider=OpenAIProvider(
                base_url=base_url,
                api_key=api_key,
            ),
        )
    elif provider == "grok":
        base_url, env_var = BUILTIN_OPENAI_COMPAT["grok"]
        pydantic_model = OpenAIChatModel(
            model_name=model,
            provider=OpenAIProvider(
                base_url=base_url,
                api_key=os.getenv(env_var) or UNRESOLVED_API_KEY,
            ),
        )
    else:
        pydantic_model = f"{provider}:{model}"

    agent: Agent[None, str] = Agent(
        pydantic_model,
        instructions=system,
        tools=tools or [],
        toolsets=toolsets or [],
        capabilities=capabilities,
        model_settings=_build_model_settings(parameters, thinking, provider),
    )
    return agent
