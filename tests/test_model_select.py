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
