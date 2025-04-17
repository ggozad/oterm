import itertools

from oterm.types import ToolCall

available_tool_defs: dict[str, list[ToolCall]] = {}


def available_tool_calls() -> list[ToolCall]:
    return list(itertools.chain.from_iterable(available_tool_defs.values()))
