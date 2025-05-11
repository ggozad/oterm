import re
import unicodedata
from collections.abc import Sequence

from textual import on
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Input, Label

from oterm.store.store import Store
from oterm.types import MessageModel


def slugify(value):
    """
    Taken from https://github.com/django/django/blob/master/django/utils/text.py
    """
    value = str(value)
    value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    )
    value = re.sub(r"[^\w\s-]", "", value.lower())
    return re.sub(r"[-\s]+", "-", value).strip("-_")


class ChatExport(ModalScreen[str]):
    chat_id: int
    file_name: str = ""
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, chat_id: int, file_name: str = "") -> None:
        super().__init__()
        self.chat_id = chat_id
        self.file_name = file_name

    def action_cancel(self) -> None:
        self.dismiss()

    @on(Input.Submitted)
    async def on_submit(self, event: Input.Submitted) -> None:
        store = await Store.get_store()

        if not event.value:
            return

        messages: Sequence[MessageModel] = await store.get_messages(self.chat_id)
        with open(event.value, "w", encoding="utf-8") as file:
            for message in messages:
                file.write(f"*{message.role}*\n")
                file.write(f"{message.text}\n")
                file.write("\n---\n")
        self.app.notify(f"Chat exported to {file.name}")
        self.dismiss()

    def compose(self) -> ComposeResult:
        with Container(classes="screen-container short"):
            yield Label("Export chat", classes="title")
            yield Input(id="chat-name-input", value=self.file_name)
