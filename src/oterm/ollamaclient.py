import inspect
import json
from ast import literal_eval
from collections.abc import AsyncGenerator, AsyncIterator, Iterator, Mapping, Sequence
from pathlib import Path
from typing import (
    Any,
    Literal,
)

from ollama import (
    AsyncClient,
    ChatResponse,
    Client,
    ListResponse,
    Message,
    Options,
    ProgressResponse,
    ShowResponse,
)
from pydantic.json_schema import JsonSchemaValue

from oterm.config import envConfig
from oterm.log import log
from oterm.types import ToolCall


def parse_format(format_text: str) -> JsonSchemaValue | Literal["", "json"]:
    try:
        jsn = json.loads(format_text)
        if isinstance(jsn, dict):
            return jsn
    except json.JSONDecodeError:
        if format_text in ("", "json"):
            return format_text
    raise Exception(f"Invalid Ollama format: '{format_text}'")


class OllamaLLM:
    def __init__(
        self,
        model="llama3.2",
        system: str | None = None,
        history: Sequence[Mapping[str, Any] | Message] = [],
        format: str = "",
        options: Options = Options(),
        keep_alive: int = 5,
        tool_defs: Sequence[ToolCall] = [],
    ):
        self.model = model
        self.system = system
        self.history = list(history)
        self.format = format
        self.keep_alive = keep_alive
        self.options = options
        self.tool_defs = tool_defs
        self.tools = [tool["tool"] for tool in tool_defs]

        if system:
            system_prompt: Message = Message(role="system", content=system)
            self.history = [system_prompt] + self.history

    async def completion(
        self,
        prompt: str = "",
        images: list[Path | bytes | str] = [],
        tool_call_messages=[],
    ) -> str:
        client = AsyncClient(
            host=envConfig.OLLAMA_URL, verify=envConfig.OTERM_VERIFY_SSL
        )
        if prompt:
            user_prompt: Message = Message(role="user", content=prompt)
            if images:
                # This is a bug in Ollama the images should be a list of Image objects
                # user_prompt.images = [Image(value=image) for image in images]
                user_prompt.images = images  # type: ignore
            self.history.append(user_prompt)
        response: ChatResponse = await client.chat(
            model=self.model,
            messages=self.history + tool_call_messages,
            keep_alive=f"{self.keep_alive}m",
            options=self.options,
            format=parse_format(self.format),
            tools=self.tools,
        )
        message = response.message
        tool_calls = message.tool_calls
        if tool_calls:
            tool_messages = [message]
            for tool_call in tool_calls:
                tool_name = tool_call["function"]["name"]
                for tool_def in self.tool_defs:
                    if tool_def["tool"]["function"]["name"] == tool_name:
                        tool_callable = tool_def["callable"]
                        tool_arguments = tool_call["function"]["arguments"]
                        try:
                            log.debug(
                                f"Calling tool: {tool_name} with {tool_arguments}"
                            )
                            if inspect.iscoroutinefunction(tool_callable):
                                tool_response = await tool_callable(**tool_arguments)  # type: ignore
                            else:
                                tool_response = tool_callable(**tool_arguments)  # type: ignore
                            log.debug(f"Tool response: {tool_response}", tool_response)
                        except Exception as e:
                            log.error(f"Error calling tool {tool_name}", e)
                            tool_response = str(e)
                        tool_messages.append(
                            {  # type: ignore
                                "role": "tool",
                                "content": tool_response,
                                "name": tool_name,
                            }
                        )
            return await self.completion(
                tool_call_messages=tool_messages,
            )

        self.history.append(message)
        text_response = message.content
        return text_response or ""

    async def stream(
        self,
        prompt: str,
        images: list[Path | bytes | str] = [],
        additional_options: Options = Options(),
        tool_defs: Sequence[ToolCall] = [],
    ) -> AsyncGenerator[str, Any]:
        # stream() should not be called with tools till Ollama supports streaming with tools.
        # See https://github.com/ollama/ollama-python/issues/279
        if tool_defs:
            raise NotImplementedError(
                "stream() should not be called with tools till Ollama supports streaming with tools."
            )

        client = AsyncClient(
            host=envConfig.OLLAMA_URL, verify=envConfig.OTERM_VERIFY_SSL
        )
        user_prompt: Message = Message(role="user", content=prompt)
        if images:
            user_prompt.images = images  # type: ignore

        self.history.append(user_prompt)
        options = {
            k: v for k, v in self.options.model_dump().items() if v is not None
        } | {k: v for k, v in additional_options.model_dump().items() if v is not None}

        stream: AsyncIterator[ChatResponse] = await client.chat(
            model=self.model,
            messages=self.history,
            stream=True,
            options=options,
            keep_alive=f"{self.keep_alive}m",
            format=parse_format(self.format),
            tools=self.tools,
        )
        text = ""
        async for response in stream:
            text = text + response.message.content if response.message.content else text
            yield text

        self.history.append(Message(role="assistant", content=text))

    @staticmethod
    def list() -> ListResponse:
        client = Client(host=envConfig.OLLAMA_URL, verify=envConfig.OTERM_VERIFY_SSL)
        return client.list()

    @staticmethod
    def show(model: str) -> ShowResponse:
        client = Client(host=envConfig.OLLAMA_URL, verify=envConfig.OTERM_VERIFY_SSL)
        return client.show(model)

    @staticmethod
    def pull(model: str) -> Iterator[ProgressResponse]:
        client = Client(host=envConfig.OLLAMA_URL, verify=envConfig.OTERM_VERIFY_SSL)
        stream: Iterator[ProgressResponse] = client.pull(model, stream=True)
        yield from stream


def parse_ollama_parameters(parameter_text: str) -> Options:
    lines = parameter_text.split("\n")
    params = Options()
    valid_params = set(Options.model_fields.keys())
    for line in lines:
        if line:
            key, value = line.split(maxsplit=1)
            try:
                value = literal_eval(value)
            except (SyntaxError, ValueError):
                pass
            if key not in valid_params:
                continue
            if params.get(key):
                if not isinstance(params[key], list):
                    params[key] = [params[key], value]
                else:
                    params[key].append(value)
            else:
                params[key] = value
    return params


def jsonify_options(options: Options) -> str:
    return json.dumps(
        {
            key: value
            for key, value in options.model_dump().items()
            if value is not None
        },
        indent=2,
    )
