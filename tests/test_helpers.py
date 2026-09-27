import pytest
from textual.app import App

from tests._helpers import wait_until


async def test_wait_until_raises_when_the_condition_never_holds():
    async with App().run_test() as pilot:
        with pytest.raises(TimeoutError):
            await wait_until(pilot, lambda: False, max_iters=3)


async def test_wait_until_returns_once_the_condition_holds():
    seen: list[int] = []
    async with App().run_test() as pilot:
        await wait_until(pilot, lambda: len(seen.append(1) or seen) >= 2)
    assert len(seen) == 2
