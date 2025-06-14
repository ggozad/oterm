import asyncio

import pytest

from oterm.utils import debounce, throttle


@pytest.mark.asyncio
async def test_throttle_first_call_executes_immediately():
    call_count = 0

    @throttle(0.1)
    async def test_func():
        nonlocal call_count
        call_count += 1

    await test_func()
    assert call_count == 1


@pytest.mark.asyncio
async def test_throttle_blocks_subsequent_calls_within_interval():
    call_count = 0

    @throttle(0.1)
    async def test_func():
        nonlocal call_count
        call_count += 1

    await test_func()
    await test_func()
    await test_func()

    assert call_count == 1


@pytest.mark.asyncio
async def test_throttle_allows_call_after_interval():
    call_count = 0

    @throttle(0.05)
    async def test_func():
        nonlocal call_count
        call_count += 1

    await test_func()
    await asyncio.sleep(0.06)
    await test_func()

    assert call_count == 2


@pytest.mark.asyncio
async def test_throttle_with_args_and_kwargs():
    received_args = []
    received_kwargs = []

    @throttle(0.1)
    async def test_func(*args, **kwargs):
        received_args.append(args)
        received_kwargs.append(kwargs)

    await test_func(1, 2, key="value")
    await test_func(3, 4, other="ignored")  # Should be ignored

    assert len(received_args) == 1
    assert received_args[0] == (1, 2)
    assert received_kwargs[0] == {"key": "value"}


@pytest.mark.asyncio
async def test_debounce_delays_execution():
    call_count = 0

    @debounce(0.05)
    async def test_func():
        nonlocal call_count
        call_count += 1

    await test_func()
    assert call_count == 0  # Should not execute immediately

    await asyncio.sleep(0.06)
    assert call_count == 1  # Should execute after delay


@pytest.mark.asyncio
async def test_debounce_cancels_previous_calls():
    call_count = 0

    @debounce(0.05)
    async def test_func():
        nonlocal call_count
        call_count += 1

    await test_func()
    await asyncio.sleep(0.02)
    await test_func()  # Should cancel the first call
    await asyncio.sleep(0.02)
    await test_func()  # Should cancel the second call

    await asyncio.sleep(0.06)
    assert call_count == 1  # Only the last call should execute


@pytest.mark.asyncio
async def test_debounce_with_args_and_kwargs():
    received_args = []
    received_kwargs = []

    @debounce(0.05)
    async def test_func(*args, **kwargs):
        received_args.append(args)
        received_kwargs.append(kwargs)

    await test_func(1, 2, key="value")
    await test_func(3, 4, other="final")  # Should replace the first call

    await asyncio.sleep(0.06)

    assert len(received_args) == 1
    assert received_args[0] == (3, 4)
    assert received_kwargs[0] == {"other": "final"}


@pytest.mark.asyncio
async def test_debounce_multiple_rapid_calls():
    call_count = 0

    @debounce(0.05)
    async def test_func():
        nonlocal call_count
        call_count += 1

    # Make multiple rapid calls
    for _ in range(10):
        await test_func()
        await asyncio.sleep(0.01)

    await asyncio.sleep(0.06)
    assert call_count == 1  # Only one execution should happen


@pytest.mark.asyncio
async def test_debounce_respects_wait_time():
    call_count = 0

    @debounce(0.1)
    async def test_func():
        nonlocal call_count
        call_count += 1

    await test_func()
    await asyncio.sleep(0.05)  # Less than wait time
    assert call_count == 0

    await asyncio.sleep(0.06)  # Total > wait time
    assert call_count == 1
