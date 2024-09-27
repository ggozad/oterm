import inspect
from ast import literal_eval
from typing import (
    Any,
    AsyncGenerator,
    AsyncIterator,
    Iterator,
    Literal,
    Mapping,
    Sequence,
)

from ollama import AsyncClient, Client, Message, Options, ResponseError

from oterm.config import envConfig
from oterm.tools import ToolDefinition


class OllamaLLM:
    def __init__(
        self,
        model="llama3.2",
        system: str | None = None,
        history: list[Message] = [],
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
            system_prompt: Message = {"role": "system", "content": system}
            self.history = [system_prompt] + self.history

    async def completion(self, prompt: str = "", images: list[str] = []) -> str:
        client = AsyncClient(
            host=envConfig.OLLAMA_URL, verify=envConfig.OTERM_VERIFY_SSL
        )
        if prompt:
            user_prompt: Message = {"role": "user", "content": prompt}
            if images:
                user_prompt["images"] = images
            self.history.append(user_prompt)
        response = await client.chat(
            model=self.model,
            messages=self.history,
            keep_alive=f"{self.keep_alive}m",
            options=self.options,
            format=self.format,  # type: ignore
            tools=self.tools,
        )

        message = response.get("message", {})
        tool_calls = message.get("tool_calls", [])
        if tool_calls:
            for tool_call in tool_calls:
                tool_name = tool_call["function"]["name"]
                self.history.append(message)
                for tool_def in self.tool_defs:
                    if tool_def["tool"]["function"]["name"] == tool_name:
                        tool_callable = tool_def["callable"]
                        tool_arguments = tool_call["function"]["arguments"]
                        if inspect.iscoroutinefunction(tool_callable):
                            tool_response = await tool_callable(**tool_arguments)  # type: ignore
                        else:
                            tool_response = tool_callable(**tool_arguments)  # type: ignore
                        self.history.append({"role": "tool", "content": tool_response})
            return await self.completion()

        self.history.append(message)
        text_response = message.get("content", "")
        return text_response

    async def stream(
        self,
        prompt: str,
        images: list[str] = [],
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
        user_prompt: Message = {"role": "user", "content": prompt}
        if images:
            user_prompt["images"] = images
        self.history.append(user_prompt)
        stream: AsyncIterator[dict] = await client.chat(
            model=self.model,
            messages=self.history,
            stream=True,
            options={**self.options, **additional_options},
            keep_alive=f"{self.keep_alive}m",
            format=self.format,  # type: ignore
            tools=self.tools,
        )
        text = ""
        async for response in stream:
            ollama_response = response.get("message", {}).get("content", "")
            text = text + ollama_response
            yield text

        self.history.append({"role": "assistant", "content": text})

    @staticmethod
    def list() -> Mapping[str, Any]:
        client = Client(host=envConfig.OLLAMA_URL, verify=envConfig.OTERM_VERIFY_SSL)
        return client.list()

    @staticmethod
    def show(model: str) -> Mapping[str, Any]:
        client = Client(host=envConfig.OLLAMA_URL, verify=envConfig.OTERM_VERIFY_SSL)
        return client.show(model)

    @staticmethod
    def pull(model: str) -> Iterator[Mapping[str, Any]]:
        client = Client(host=envConfig.OLLAMA_URL, verify=envConfig.OTERM_VERIFY_SSL)
        try:
            stream: Iterator[Mapping[str, Any]] = client.pull(model, stream=True)
            for response in stream:
                yield response
        except ResponseError as e:
            yield {"status": "error", "message": str(e)}


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
