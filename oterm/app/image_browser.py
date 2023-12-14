from pathlib import Path
from typing import Iterable

from PIL import Image as PILImage
from rich_pixels import Pixels
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, DirectoryTree, Label

IMG_MAX_SIZE = 80


class Image(Widget):
    path: reactive[str] = reactive("")

    def __init__(self, id="", classes="") -> None:
        self.pixels = None
        super().__init__(id=id, classes=classes)

    def watch_path(self, path: str) -> None:
        if path:
            with PILImage.open(path) as img:
                max_size = max(img.width, img.height)
                width = int(img.width / max_size * IMG_MAX_SIZE)
                height = int(img.height / max_size * IMG_MAX_SIZE)

                self.set_styles(
                    f"""
                    width: {width * 2};
                    height: {height};
                    padding:1;
                    """
                )
                self.pixels = Pixels.from_image_path(path, (width, height))

        else:
            self.pixels = None

    def render(self):
        if self.pixels:
            return self.pixels
        return ""


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

    async def on_directory_tree_file_selected(
        self, ev: DirectoryTree.FileSelected
    ) -> None:
        image = self.query_one(Image)
        image.path = ev.path.as_posix()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.name == "select":
            pass
        else:
            self.dismiss()

    def compose(self) -> ComposeResult:
        with Container(id="image-select-container"):
            yield Label("Select an image:", classes="title")
            with Horizontal():
                yield ImageDirectoryTree("./", id="image-directory-tree")
                with Container(id="image-preview"):
                    yield Image(id="image")
            with Horizontal(classes="button-container"):
                yield Button("Select", name="select", variant="primary")
                yield Button("Cancel", name="cancel")
