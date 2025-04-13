import asyncio

from ollama import ResponseError
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, TextArea

from oterm.ollamaclient import OllamaLLM


class PullModel(ModalScreen[str]):
    model: str = ""
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, model: str) -> None:
        self.model = model
        super().__init__()

    def action_cancel(self) -> None:
        self.dismiss()

    @work
    async def pull_model(self) -> None:
        log = self.query_one(".log", TextArea)
        stream = OllamaLLM.pull(self.model)
        try:
            for response in stream:
                log.text += response.model_dump_json() + "\n"
                await asyncio.sleep(0.1)
            await asyncio.sleep(1.0)
        except ResponseError as e:
            log.text += f"Error: {e}\n"
        self.app.notify("Model pulled successfully")

    @on(Input.Changed)
    async def on_model_change(self, ev: Input.Changed) -> None:
        self.model = ev.value

    @on(Button.Pressed)
    @on(Input.Submitted)
    async def on_pull(self, ev: Button.Pressed) -> None:
        self.pull_model()

    def compose(self) -> ComposeResult:
        with Container(
            id="pull-model-container", classes="screen-container full-height"
        ):
            yield Label("Pull model", classes="title")
            with Horizontal():
                yield Input(self.model)
                yield Button("Pull", variant="primary")
            yield TextArea(classes="parameters log", read_only=True)
