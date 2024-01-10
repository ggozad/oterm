from base64 import b64encode
from io import BytesIO
from pathlib import Path

from PIL import Image as PILImage
from PIL import UnidentifiedImageError
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import DirectoryTree, Label

from oterm.app.widgets.image import IMAGE_EXTENSIONS, Image, ImageDirectoryTree


class ImageSelect(ModalScreen[tuple[Path, str]]):
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
        try:
            buffer = BytesIO()
            image = PILImage.open(ev.path)
            if image.mode != "RGB":
                image = image.convert("RGB")
            image.save(buffer, format="JPEG")
            b64 = b64encode(buffer.getvalue()).decode("utf-8")
            self.dismiss((ev.path, b64))
        except UnidentifiedImageError:
            self.dismiss()

    async def on_tree_node_highlighted(self, ev: DirectoryTree.NodeHighlighted) -> None:
        path = ev.node.data.path
        if path.suffix in IMAGE_EXTENSIONS:
            image = self.query_one(Image)
            image.path = path.as_posix()

    def compose(self) -> ComposeResult:
        with Container(id="image-select-container"):
            with Horizontal():
                with Vertical(id="image-directory-tree"):
                    yield Label("Select an image:", classes="title")
                    yield ImageDirectoryTree("./")
                with Container(id="image-preview"):
                    yield Image(id="image")
