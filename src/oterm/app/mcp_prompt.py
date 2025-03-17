from mcp.types import Prompt
from textual.app import ComposeResult, RenderResult
from textual.containers import (
    Container,
    Horizontal,
    Vertical,
)
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, Label, OptionList
from textual.widgets.option_list import Option

from oterm.tools.mcp import mcp_prompts


class PromptWidget(Widget):
    def __init__(self, prompt: Prompt) -> None:
        super().__init__()
        self.prompt = prompt

    def render(self) -> RenderResult:
        return f"[b]{self.prompt.name}[/b]\n[i]{self.prompt.description}[/i]"


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
        return Option(prompt=PromptWidget(prompt).render(), id=prompt.name)

    def on_option_list_option_highlighted(
        self, option: OptionList.OptionHighlighted
    ) -> None:
        print(option.option.id)

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

            with Horizontal(classes="button-container"):
                yield Button(
                    "Copy",
                    id="copy-btn",
                    name="copy",
                    disabled=True,
                    variant="primary",
                )
                yield Button("Cancel", name="cancel")
