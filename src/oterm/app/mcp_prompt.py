from mcp.types import Prompt
from textual import on
from textual.app import ComposeResult, RenderResult
from textual.containers import (
    Container,
    Horizontal,
    Vertical,
    VerticalScroll,
)
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, Input, Label, OptionList, TextArea
from textual.widgets.option_list import Option

from oterm.tools.mcp import mcp_prompts


class PromptOptionWidget(Widget):
    def __init__(self, prompt: Prompt) -> None:
        super().__init__()
        self.prompt = prompt

    def render(self) -> RenderResult:
        return f"[b]{self.prompt.name}[/b]\n[i]{self.prompt.description}[/i]"


class PromptFormWidget(Widget):
    prompt: Prompt

    @on(Input.Changed)
    async def on_text_area_change(self, ev: Input.Changed):
        arg_name = (ev.input.id or "").split("arg-")[1]
        print(arg_name, ev.input.value)

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="prompt-form"):
            for arg in self.prompt.arguments or []:
                yield Label(arg.name, classes="title")
                yield Input(id=f"arg-{arg.name}", tooltip=arg.description)
            yield Label("Result:", classes="subtitle")
            yield TextArea(id="prompt-result", read_only=True)


class MCPPrompt(ModalScreen[str]):
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "copy", "Copy"),
    ]

    def action_cancel(self) -> None:
        self.dismiss()

    def action_copy(self) -> None:
        pass

    async def on_mount(self) -> None:
        option_list = self.query_one("#mcp-prompt-select", OptionList)
        option_list.clear_options()
        for prompt in mcp_prompts:
            option_list.add_option(option=self.prompt_option(prompt))

    @staticmethod
    def prompt_option(prompt: Prompt) -> Option:
        return Option(prompt=PromptOptionWidget(prompt).render(), id=prompt.name)

    def on_option_list_option_highlighted(
        self, option: OptionList.OptionHighlighted
    ) -> None:
        for prompt in mcp_prompts:
            if prompt.name == option.option.id:
                break

        form_container = self.query_one("#prompt-form", Vertical)
        form_container.remove_children()
        widget = PromptFormWidget()
        widget.prompt = prompt
        form_container.mount(widget)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.name == "copy":
            pass
        else:
            self.dismiss()

    def compose(self) -> ComposeResult:
        with Container(classes="screen-container full-height"):
            with Horizontal():
                with Vertical():
                    yield Label("Available MCP prompts", classes="title")
                    yield OptionList(id="mcp-prompt-select")

                with Vertical():
                    yield Label("Customize prompt:", classes="title")
                    yield Vertical(id="prompt-form")
            with Horizontal(classes="button-container"):
                yield Button(
                    "Copy",
                    id="copy-btn",
                    name="copy",
                    disabled=True,
                    variant="primary",
                )
                yield Button("Cancel", name="cancel")
