from pathlib import Path
from typing import Iterable

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Label


class ImageDirectoryTree(DirectoryTree):
    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [
            path
            for path in paths
            if path.suffix in [".png", ".jpg", ".jpeg"] or path.is_dir()
        ]


class ImageSelect(ModalScreen[str]):
    image: reactive[str] = reactive("")
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def action_cancel(self) -> None:
        self.dismiss()

    async def on_mount(self) -> None:
        dt = self.query_one(ImageDirectoryTree)
        dt.show_guides = False
        pass

    async def on_directory_tree_file_selected(
        self, ev: DirectoryTree.FileSelected
    ) -> None:
        print(ev.path)

    def compose(self) -> ComposeResult:
        with Container(id="image-select-container"):
            yield Label("Select an image:", classes="title")
            with Horizontal():
                yield ImageDirectoryTree("./")
            with Horizontal(classes="button-container"):
                yield Button("Cancel", name="cancel")
