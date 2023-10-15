from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Label, OptionList

from oterm.ollama import OllamaAPI


class ModelDetails(Widget):
    name: reactive[str] = reactive("")
    tag: reactive[str] = reactive("")
    bytes: reactive[int] = reactive(0)

    def watch_name(self, name: str) -> None:
        try:
            widget = self.query_one(".name", Label)
            if widget:
                widget.update(f"Name: {self.name}")
        except NoMatches:
            pass

    def watch_tag(self, tag: str) -> None:
        try:
            widget = self.query_one(".tag", Label)
            if widget:
                widget.update(f"Tag: {self.tag}")
        except NoMatches:
            pass

    def watch_bytes(self, size: int) -> None:
        try:
            widget = self.query_one(".size", Label)
            if widget:
                widget.update(f"Size: {(self.bytes / 1.0e9):.2f} GB")
        except NoMatches:
            pass

    def compose(self) -> ComposeResult:
        yield Label("Model details:", classes="title")
        yield Label(f"Name: {self.name}", classes="name")
        yield Label(f"Tag: {self.tag}", classes="tag")
        yield Label(f"Size: {self.bytes}", classes="size")


class ModelSelection(ModalScreen[str]):
    api = OllamaAPI()
    models = []

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def action_cancel(self) -> None:
        self.dismiss()

    async def on_mount(self) -> None:
        self.models = await self.api.get_models()
        models = [model["name"] for model in self.models]
        option_list = self.query_one("#model-select", OptionList)
        option_list.clear_options()
        for model in models:
            option_list.add_option(item=self.model_option(model))

    def on_option_list_option_selected(self, option: OptionList.OptionSelected) -> None:
        model = option.option.prompt
        self.dismiss(str(model))

    def on_option_list_option_highlighted(
        self, option: OptionList.OptionHighlighted
    ) -> None:
        model = option.option.prompt
        model_info = next((m for m in self.models if m["name"] == str(model)), None)
        model_details = self.query_one("#model-details", ModelDetails)
        if model_info:
            name, tag = model_info["name"].split(":")
            model_details.name = name
            model_details.tag = tag
            model_details.bytes = model_info["size"]

    @staticmethod
    def model_option(model: str) -> Text:
        return Text(model)

    def compose(self) -> ComposeResult:
        with Container(id="model-select-container"):
            yield Label("Select a model:", classes="title")
            with Horizontal():
                yield OptionList(id="model-select")
                yield ModelDetails(id="model-details")
