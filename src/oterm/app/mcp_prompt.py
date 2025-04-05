import inspect
import json
from collections.abc import Awaitable, Callable

from mcp.types import Prompt
from ollama import Message
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

from oterm.tools.mcp.prompts import avail_prompt_defs, mcp_prompt_to_ollama_messages
from oterm.utils import debounce


class PromptOptionWidget(Widget):
    def __init__(self, prompt: Prompt) -> None:
        super().__init__()
        self.prompt = prompt

    def render(self) -> RenderResult:
        return f"[b]{self.prompt.name}[/b]\n[i]{self.prompt.description}[/i]"


class PromptFormWidget(Widget):
    prompt: Prompt
    callable: Callable | Awaitable
    messages: list[Message] = []

    @on(Input.Changed)
    @debounce(1.0)
    async def on_text_area_change(self, ev: Input.Changed):
        is_valid = True
        params = {}
        for arg in self.prompt.arguments or []:
            params[arg.name] = self.query_one(f"#arg-{arg.name}", Input).value
            if arg.required and not params[arg.name]:
                is_valid = False
        prompt_result_widget = self.query_one("#prompt-result", TextArea)
        if inspect.iscoroutinefunction(self.callable):
            messages = await self.callable(**params)
        else:
            messages = self.callable(**params)  # type: ignore
        self.messages = messages = mcp_prompt_to_ollama_messages(messages)
        prompt_result_widget.text = "\n".join(
            [f"{m.role}: {m.content}" for m in messages]
        )
        submit_button = self.screen.query_one("#submit", Button)
        submit_button.disabled = not is_valid

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="prompt-form-container"):
            for arg in self.prompt.arguments or []:
                yield Label(
                    f"{arg.name}{arg.required and ' (required)' or ''}", classes="title"
                )
                yield Input(id=f"arg-{arg.name}", tooltip=arg.description)
            yield Label("Messages:", classes="subtitle")
            yield TextArea(id="prompt-result", read_only=True)


class MCPPrompt(ModalScreen[str]):
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "submit", "Submit"),
    ]

    def action_cancel(self) -> None:
        self.dismiss()

    async def on_mount(self) -> None:
        option_list = self.query_one("#mcp-prompt-select", OptionList)
        option_list.clear_options()
        for prompt_call in avail_prompt_defs:
            option_list.add_option(option=self.prompt_option(prompt_call["prompt"]))

    @staticmethod
    def prompt_option(prompt: Prompt) -> Option:
        return Option(prompt=PromptOptionWidget(prompt).render(), id=prompt.name)

    def on_option_list_option_highlighted(
        self, option: OptionList.OptionHighlighted
    ) -> None:
        for prompt_call in avail_prompt_defs:
            prompt = prompt_call["prompt"]
            if prompt.name == option.option.id:
                break

        form_container = self.query_one("#prompt-form-container", Vertical)
        form_container.remove_children()
        widget = PromptFormWidget(classes="prompt-form")
        widget.prompt = prompt
        widget.callable = prompt_call["callable"]
        form_container.mount(widget)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.name == "submit":
            form = self.query_one(".prompt-form", PromptFormWidget)
            jsn = json.dumps([m.model_dump() for m in form.messages])
            self.dismiss(jsn)
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
                    yield Vertical(id="prompt-form-container")
            with Horizontal(classes="button-container"):
                yield Button(
                    "Submit",
                    id="submit",
                    name="submit",
                    variant="primary",
                    disabled=True,
                )
                yield Button("Cancel", name="cancel")
