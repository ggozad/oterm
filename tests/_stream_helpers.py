"""Shared streaming-test helpers.

Provides a `FunctionModel` variant whose `stream_function` may also yield
`FilePart` items, which the standard `FunctionModel` does not support.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pydantic_ai import Agent
from pydantic_ai.messages import FilePart
from pydantic_ai.models import StreamedResponse
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


class _FileAwareModel(FunctionModel):
    @asynccontextmanager
    async def request_stream(
        self, messages, model_settings, model_request_parameters, run_context=None
    ) -> AsyncIterator[StreamedResponse]:
        assert self.stream_function is not None
        model_settings, mrp = self.prepare_request(
            model_settings, model_request_parameters
        )
        agent_info = AgentInfo(
            function_tools=mrp.function_tools,
            allow_text_output=mrp.allow_text_output,
            output_tools=mrp.output_tools,
            model_settings=model_settings,
            model_request_parameters=mrp,
            instructions=None,
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


def make_file_aware_agent(stream_fn) -> Agent:
    """Build an `Agent` whose model accepts `FilePart` items in its stream."""
    return Agent(_FileAwareModel(stream_function=stream_fn))
