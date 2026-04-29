"""Shared streaming-test helpers.

Provides a `FunctionModel` variant whose `stream_function` may also yield
`FilePart` items, which the standard `FunctionModel` does not support.
"""

from contextlib import asynccontextmanager

from pydantic_ai import Agent
from pydantic_ai.messages import FilePart
from pydantic_ai.models.function import (
    AgentInfo,
    FunctionModel,
    FunctionStreamedResponse,
    PeekableAsyncStream,
)


class _FileAwareStream(FunctionStreamedResponse):
    async def _get_event_iterator(self):
        original_iter = self._iter

        async def one(item):
            yield item

        async for item in original_iter:
            if isinstance(item, FilePart):
                yield self._parts_manager.handle_part(
                    vendor_part_id=f"file_{id(item)}", part=item
                )
                continue
            self._iter = one(item)
            async for ev in super()._get_event_iterator():
                yield ev
        self._iter = original_iter


def make_file_aware_agent(stream_fn) -> Agent:
    """Build an `Agent` whose model accepts `FilePart` items in its stream."""
    model = FunctionModel(stream_function=stream_fn)

    @asynccontextmanager
    async def request_stream(
        self, messages, model_settings, model_request_parameters, run_context=None
    ):
        model_settings, mrp = self.prepare_request(
            model_settings, model_request_parameters
        )
        agent_info = AgentInfo(
            function_tools=mrp.function_tools,
            allow_text_output=mrp.allow_text_output,
            output_tools=mrp.output_tools,
            model_settings=model_settings,
            model_request_parameters=mrp,
            instructions=self._get_instructions(messages, mrp),
        )
        response_stream = PeekableAsyncStream(
            self.stream_function(messages, agent_info)
        )
        await response_stream.peek()
        yield _FileAwareStream(
            model_request_parameters=mrp,
            _model_name=self._model_name,
            _iter=response_stream,
        )

    model.request_stream = request_stream.__get__(model, type(model))
    return Agent(model)
