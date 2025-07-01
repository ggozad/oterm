import inspect
import json
from ast import literal_eval
from collections.abc import AsyncGenerator, AsyncIterator, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

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
        thinking: bool = False,
    ):
        self.model = model
        self.system = system
        self.history = list(history)
        self.format = format
        self.keep_alive = keep_alive
        self.options = options
        self.tool_defs = tool_defs
        self.tools = [tool["tool"] for tool in tool_defs]
        self.thinking = thinking
        if system:
            system_prompt: Message = Message(role="system", content=system)
            self.history = [system_prompt] + self.history

    async def stream(
        self,
        prompt: str = "",
        images: list[Path | bytes | str] = [],
        additional_options: Options = Options(),
        tool_call_messages: list = [],
    ) -> AsyncGenerator[tuple[str, str], Any]:
        """Stream a chat response with support for tool calls.

        When tool calls are encountered during streaming, they are executed after the stream
        completes and the result is incorporated into the response.
        """
        client = AsyncClient(
            host=envConfig.OLLAMA_URL, verify=envConfig.OTERM_VERIFY_SSL
        )

        # Add user prompt to history if provided
        if prompt:
            user_prompt: Message = Message(role="user", content=prompt)
            if images:
                user_prompt.images = images  # type: ignore
            self.history.append(user_prompt)

        # Process options
        options = {
            k: v for k, v in self.options.model_dump().items() if v is not None
        } | {k: v for k, v in additional_options.model_dump().items() if v is not None}

        # Start the streaming chat
        stream: AsyncIterator[ChatResponse] = await client.chat(
            model=self.model,
            messages=self.history + tool_call_messages,
            options=options,
            keep_alive=f"{self.keep_alive}m",
            format=parse_format(self.format),
            tools=self.tools,
            stream=True,
            think=self.thinking,
        )

        text = ""
        thought = ""
        current_message = None
        pending_tool_call = False

        async for response in stream:
            message = response.message
            content = message.content if message.content else ""
            thinking = message.thinking if message.thinking else ""
            tool_calls = message.tool_calls
            # If we have tool calls, process them at the end of the stream
            if tool_calls and not pending_tool_call:
                pending_tool_call = True
                current_message = message

            # Add content to the accumulated text only if not processing tool calls
            if not pending_tool_call and (content or thinking):
                if thinking:
                    thought += thinking
                if content:
                    text += content
                yield thought, text

        # After streaming is complete, handle any tool calls
        if pending_tool_call and current_message and current_message.tool_calls:
            # Process each tool call
            tool_messages = [current_message]  # type: ignore
            # If there the model has done "thinking", we need add it to the history
            # before processing tool calls. This way, when the model starts thinking
            # again, it has the full context of the previous thought.

            if thought:
                tool_messages.insert(0, Message(role="assistant", thinking=thought))

            for tool_call in current_message.tool_calls:
                tool_name = tool_call["function"]["name"]

                tool_args = tool_call["function"]["arguments"]
                # Execute the tool
                for tool_def in self.tool_defs:
                    if tool_def["tool"]["function"]["name"] == tool_name:
                        tool_callable = tool_def["callable"]

                        try:
                            log.debug(f"Calling tool: {tool_name} with {tool_args}")
                            # Execute the tool
                            if inspect.iscoroutinefunction(tool_callable):
                                tool_response = await tool_callable(**tool_args)  # type: ignore
                            else:
                                tool_response = tool_callable(**tool_args)  # type: ignore

                            log.debug(f"Tool response: {tool_response}")

                            # Add tool response to messages
                            tool_messages.append(
                                {  # type: ignore
                                    "role": "tool",
                                    "content": str(tool_response),
                                    "name": tool_name,
                                }
                            )
                        except Exception as e:
                            log.error(f"Error calling tool {tool_name}: {e}")
                            return

            # Use a new variable for the follow-up response to avoid duplication
            async for thought_chunk, text_chunk in self.stream(
                tool_call_messages=tool_messages,
                additional_options=additional_options,
            ):
                yield thought_chunk, text_chunk
                # Append the final text and thought to the history
                text = text_chunk
                thought = thought_chunk

        elif text:  # Only regular content was present
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
