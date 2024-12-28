import inspect
import json
from ast import literal_eval
from pathlib import Path
from typing import (
    Any,
    AsyncGenerator,
    AsyncIterator,
    Iterator,
    Literal,
    Mapping,
    Sequence,
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

from oterm.config import envConfig
from oterm.types import ToolDefinition


class OllamaLLM:
    def __init__(
        self,
        model="llama3.2",
        system: str | None = None,
        history: list[Mapping[str, Any] | Message] = [],
        format: Literal["", "json"] = "",
        options: Options = Options(),
        keep_alive: int = 5,
        tool_defs: Sequence[ToolDefinition] = [],
    ):
        self.model = model
        self.system = system
        self.history = history
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
            format=self.format,  # type: ignore
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
                            if inspect.iscoroutinefunction(tool_callable):
                                tool_response = await tool_callable(**tool_arguments)  # type: ignore
                            else:
                                tool_response = tool_callable(**tool_arguments)  # type: ignore
                        except Exception as e:
                            tool_response = str(e)
                        tool_messages.append(
                            {
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
        tool_defs: Sequence[ToolDefinition] = [],
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
        stream: AsyncIterator[ChatResponse] = await client.chat(
            model=self.model,
            messages=self.history,
            stream=True,
            options={**self.options.model_dump(), **additional_options.model_dump()},
            keep_alive=f"{self.keep_alive}m",
            format=self.format,  # type: ignore
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
        for response in stream:
            yield response


def parse_ollama_parameters(parameter_text: str) -> Options:
    lines = parameter_text.split("\n")
    params = Options()
    for line in lines:
        if line:
            key, value = line.split(maxsplit=1)
            try:
                value = literal_eval(value)
            except (SyntaxError, ValueError):
                pass
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
