"""Shared test helpers."""

import asyncio
from collections.abc import Callable


async def wait_until(
    pilot, predicate: Callable[[], bool], *, max_iters: int = 80
) -> None:
    """Pump the event loop until ``predicate()`` is truthy or we give up.

    A single ``await pilot.pause()`` is unreliable for actions that schedule
    background tasks (notably ``ChatContainer.action_regenerate_llm_message``,
    which spawns ``response_task`` via ``asyncio.create_task``). On Python 3.13
    the task often drains in one cycle; on 3.12 it doesn't. Poll instead.
    """
    for _ in range(max_iters):
        if predicate():
            return
        await asyncio.sleep(0)
        await pilot.pause()
