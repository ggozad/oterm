import inspect
import json
from collections.abc import AsyncGenerator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx

from oterm.config import envConfig
from oterm.log import log
from oterm.types import ToolCall


@dataclass
class MiniMaxModel:
    """Compatible with ollama Model for UI usage."""

    model: str
    size: int = 0

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


@dataclass
class MiniMaxModelInfo:
    """Compatible with ollama ShowResponse for UI usage."""

    name: str
    parameters: str = ""
    capabilities: list[str] = field(default_factory=list)

    def get(self, key: str, default: Any = None) -> Any:
        if key == "system":
            return ""
        if key == "capabilities":
            return self.capabilities
        if key == "parameters":
            return self.parameters
        return default


@dataclass
class MiniMaxListResponse:
    """Compatible with ollama ListResponse for UI usage."""

    models: list[MiniMaxModel] = field(default_factory=list)


MINIMAX_MODELS_INFO: list[dict[str, Any]] = [
    {
        "name": "MiniMax-M2.7",
        "capabilities": ["tools", "thinking"],
        "context_length": 1048576,
    },
    {
        "name": "MiniMax-M2.7-highspeed",
        "capabilities": ["tools", "thinking"],
        "context_length": 1048576,
    },
    {
        "name": "MiniMax-M2.5",
        "capabilities": ["tools"],
        "context_length": 204800,
    },
    {
        "name": "MiniMax-M2.5-highspeed",
        "capabilities": ["tools"],
        "context_length": 204800,
    },
]


class MiniMaxLLM:
    def __init__(
        self,
        model: str = "MiniMax-M2.7",
        system: str | None = None,
        history: Sequence[Mapping[str, Any] | Any] = [],
        format: str = "",
        options: Any = None,
        keep_alive: int = 5,
        tool_defs: Sequence[ToolCall] = [],
        thinking: bool = False,
    ):
        self.model = model
        self.system = system
        self.history: list[dict[str, Any]] = []
        self.format = format
        self.keep_alive = keep_alive
        self.options = options
        self.tool_defs = tool_defs
        self.tools = self._convert_tools(tool_defs)
        self.thinking = thinking

        if system:
            self.history.append({"role": "system", "content": system})

        for msg in history:
            self.history.append(self._to_dict(msg))

    @staticmethod
    def _to_dict(msg: Any) -> dict[str, Any]:
        """Convert an ollama Message or dict to a plain dict."""
        if isinstance(msg, dict):
            return dict(msg)
        return {"role": getattr(msg, "role", "user"), "content": getattr(msg, "content", "") or ""}

    @staticmethod
    def _convert_tools(tool_defs: Sequence[ToolCall]) -> list[dict[str, Any]]:
        """Convert ollama tool definitions to OpenAI function-calling format."""
        tools: list[dict[str, Any]] = []
        for td in tool_defs:
            tool = td["tool"]
            if hasattr(tool, "model_dump"):
                tool_dict = tool.model_dump()
            else:
                tool_dict = dict(tool)
            tools.append(
                {
                    "type": "function",
                    "function": tool_dict.get("function", tool_dict),
                }
            )
        return tools

    def _get_temperature(self, additional_options: Any = None) -> float | None:
        """Extract and clamp temperature from options."""
        temp = None
        if self.options is not None:
            if isinstance(self.options, dict):
                temp = self.options.get("temperature")
            elif hasattr(self.options, "temperature"):
                temp = self.options.temperature

        if additional_options is not None:
            if isinstance(additional_options, dict):
                t = additional_options.get("temperature")
            elif hasattr(additional_options, "temperature"):
                t = additional_options.temperature
            else:
                t = None
            if t is not None:
                temp = t

        if temp is not None:
            return max(0.0, min(float(temp), 1.0))
        return None

    async def stream(
        self,
        prompt: str = "",
        images: list[Any] = [],
        additional_options: Any = None,
        tool_call_messages: list[dict[str, Any]] = [],
    ) -> AsyncGenerator[tuple[str, str], Any]:
        """Stream a chat response from the MiniMax API.

        Yields (thought, text) tuples to stay compatible with OllamaLLM.
        """
        if prompt:
            self.history.append({"role": "user", "content": prompt})

        messages = self.history + tool_call_messages

        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }

        temp = self._get_temperature(additional_options)
        if temp is not None:
            body["temperature"] = temp

        if self.format == "json":
            body["response_format"] = {"type": "json_object"}

        if self.tools:
            body["tools"] = self.tools

        headers = {
            "Authorization": f"Bearer {envConfig.MINIMAX_API_KEY}",
            "Content-Type": "application/json",
        }

        raw_content = ""
        thought = ""
        text = ""
        pending_tool_calls: list[dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{envConfig.MINIMAX_BASE_URL}/chat/completions",
                json=body,
                headers=headers,
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue

                    choices = chunk.get("choices", [])
                    if not choices:
                        continue

                    delta = choices[0].get("delta", {})
                    content = delta.get("content", "") or ""

                    # Accumulate tool calls
                    if delta.get("tool_calls"):
                        for tc in delta["tool_calls"]:
                            idx = tc.get("index", 0)
                            while len(pending_tool_calls) <= idx:
                                pending_tool_calls.append(
                                    {"id": "", "function": {"name": "", "arguments": ""}}
                                )
                            if tc.get("id"):
                                pending_tool_calls[idx]["id"] = tc["id"]
                            func = tc.get("function", {})
                            if func.get("name"):
                                pending_tool_calls[idx]["function"]["name"] = func["name"]
                            if func.get("arguments"):
                                pending_tool_calls[idx]["function"]["arguments"] += func[
                                    "arguments"
                                ]

                    if content:
                        raw_content += content
                        thought, text = self._parse_think_tags(raw_content)
                        yield thought, text

        # Handle tool calls after streaming completes
        if pending_tool_calls:
            tool_messages: list[dict[str, Any]] = [
                {
                    "role": "assistant",
                    "content": text or None,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": tc["function"],
                        }
                        for tc in pending_tool_calls
                    ],
                }
            ]

            if thought:
                tool_messages.insert(0, {"role": "assistant", "content": f"<think>{thought}</think>"})

            for tc in pending_tool_calls:
                tool_name = tc["function"]["name"]
                try:
                    tool_args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    tool_args = {}

                for tool_def in self.tool_defs:
                    td_name = tool_def["tool"]
                    if hasattr(td_name, "model_dump"):
                        td_name = td_name.model_dump()
                    if isinstance(td_name, dict):
                        td_name = td_name.get("function", {}).get("name", "")
                    else:
                        td_name = ""

                    if td_name == tool_name:
                        tool_callable = tool_def["callable"]
                        try:
                            log.debug(f"Calling tool: {tool_name} with {tool_args}")
                            if inspect.iscoroutinefunction(tool_callable):
                                tool_response = await tool_callable(**tool_args)
                            else:
                                tool_response = tool_callable(**tool_args)

                            log.debug(f"Tool response: {tool_response}")
                            tool_messages.append(
                                {
                                    "role": "tool",
                                    "content": str(tool_response),
                                    "tool_call_id": tc["id"],
                                }
                            )
                        except Exception as e:
                            log.error(f"Error calling tool {tool_name}: {e}")
                            return

            async for thought_chunk, text_chunk in self.stream(
                tool_call_messages=tool_messages,
                additional_options=additional_options,
            ):
                yield thought_chunk, text_chunk
                text = text_chunk
                thought = thought_chunk

        elif text:
            self.history.append({"role": "assistant", "content": text})

    @staticmethod
    def _parse_think_tags(content: str) -> tuple[str, str]:
        """Parse <think>...</think> tags from content, returning (thought, text)."""
        if not content.startswith("<think>"):
            return "", content

        end_idx = content.find("</think>")
        if end_idx == -1:
            # Still inside thinking — all content is thought
            return content[7:], ""

        thought = content[7:end_idx]
        text = content[end_idx + 8 :]
        return thought, text

    @staticmethod
    def list() -> MiniMaxListResponse:
        """Return available MiniMax models."""
        models = [MiniMaxModel(model=m["name"]) for m in MINIMAX_MODELS_INFO]
        return MiniMaxListResponse(models=models)

    @staticmethod
    def show(model: str) -> MiniMaxModelInfo:
        """Return model details."""
        for m in MINIMAX_MODELS_INFO:
            if m["name"] == model:
                return MiniMaxModelInfo(
                    name=m["name"],
                    capabilities=m.get("capabilities", []),
                )
        return MiniMaxModelInfo(name=model)
