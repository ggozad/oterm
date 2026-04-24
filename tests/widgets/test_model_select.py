import pytest
from textual.app import App, ComposeResult
from textual.widgets import Input, OptionList

from oterm.app.widgets.model_select import ModelSelect


class ModelSelectApp(App):
    def compose(self) -> ComposeResult:
        yield ModelSelect(id="test-select")


@pytest.mark.asyncio
async def test_set_options_shows_all():
    app = ModelSelectApp()
    async with app.run_test() as pilot:
        ms = app.query_one(ModelSelect)
        ms.set_options(["alpha", "beta", "gamma"])
        await pilot.pause()
        option_list = ms.query_one(OptionList)
        assert option_list.option_count == 3


@pytest.mark.asyncio
async def test_typing_filters_list():
    app = ModelSelectApp()
    async with app.run_test() as pilot:
        ms = app.query_one(ModelSelect)
        ms.set_options(["llama-3.1-70b", "mistral-7b", "qwen-72b"])
        await pilot.pause()
        input_widget = ms.query_one(Input)
        input_widget.value = "llama"
        await pilot.pause()
        option_list = ms.query_one(OptionList)
        assert option_list.option_count == 1


@pytest.mark.asyncio
async def test_typing_case_insensitive():
    app = ModelSelectApp()
    async with app.run_test() as pilot:
        ms = app.query_one(ModelSelect)
        ms.set_options(["Llama-3.1-70B", "Mistral-7B"])
        await pilot.pause()
        input_widget = ms.query_one(Input)
        input_widget.value = "LLAMA"
        await pilot.pause()
        option_list = ms.query_one(OptionList)
        assert option_list.option_count == 1


@pytest.mark.asyncio
async def test_set_value():
    app = ModelSelectApp()
    async with app.run_test() as pilot:
        ms = app.query_one(ModelSelect)
        ms.set_value("some-model")
        await pilot.pause()
        assert ms.value == "some-model"
        assert ms.query_one(Input).value == "some-model"


@pytest.mark.asyncio
async def test_down_focuses_option_list_when_options_exist():
    app = ModelSelectApp()
    async with app.run_test() as pilot:
        ms = app.query_one(ModelSelect)
        ms.set_options(["a", "b", "c"])
        await pilot.pause()

        ms.query_one(Input).focus()
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()
        option_list = ms.query_one(OptionList)
        assert app.focused is option_list


@pytest.mark.asyncio
async def test_down_is_noop_when_no_options():
    app = ModelSelectApp()
    async with app.run_test() as pilot:
        ms = app.query_one(ModelSelect)
        ms.set_options([])
        await pilot.pause()

        input_widget = ms.query_one(Input)
        input_widget.focus()
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()
        assert app.focused is input_widget


@pytest.mark.asyncio
async def test_selecting_option_posts_submitted():
    app = ModelSelectApp()
    async with app.run_test() as pilot:
        ms = app.query_one(ModelSelect)
        ms.set_options(["alpha", "beta"])
        await pilot.pause()

        received: list[str] = []
        original = ms.post_message

        def record(msg):
            if isinstance(msg, ModelSelect.Submitted):
                received.append(msg.value)
            return original(msg)

        ms.post_message = record  # ty: ignore[invalid-assignment]

        option_list = ms.query_one(OptionList)
        option_list.highlighted = 0
        option_list.focus()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert received == ["alpha"]
        assert ms.value == "alpha"


@pytest.mark.asyncio
async def test_blur_with_value_posts_submitted():
    app = ModelSelectApp()
    async with app.run_test() as pilot:
        ms = app.query_one(ModelSelect)
        ms.set_options(["x"])
        await pilot.pause()

        input_widget = ms.query_one(Input)
        input_widget.value = "custom-model"
        input_widget.focus()
        await pilot.pause()

        received: list[str] = []
        original = ms.post_message

        def record(msg):
            if isinstance(msg, ModelSelect.Submitted):
                received.append(msg.value)
            return original(msg)

        ms.post_message = record  # ty: ignore[invalid-assignment]

        ms.query_one(OptionList).focus()
        await pilot.pause()

        assert "custom-model" in received


@pytest.mark.asyncio
async def test_blur_with_empty_value_does_not_post_submitted():
    app = ModelSelectApp()
    async with app.run_test() as pilot:
        ms = app.query_one(ModelSelect)
        ms.set_options(["x"])
        await pilot.pause()

        input_widget = ms.query_one(Input)
        input_widget.value = ""
        input_widget.focus()
        await pilot.pause()

        received: list[str] = []
        original = ms.post_message

        def record(msg):
            if isinstance(msg, ModelSelect.Submitted):
                received.append(msg.value)
            return original(msg)

        ms.post_message = record  # ty: ignore[invalid-assignment]

        ms.query_one(OptionList).focus()
        await pilot.pause()

        assert received == []
