from base64 import b64encode
from io import BytesIO
from pathlib import Path

import PIL.Image as PILImage
from PIL import UnidentifiedImageError
from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import DirectoryTree, Input, Label
from textual_image.widget import Image

from oterm.app.widgets.image import IMAGE_EXTENSIONS, ImageDirectoryTree


class ImageSelect(ModalScreen[tuple[Path, str]]):
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def action_cancel(self) -> None:
        self.dismiss()

    async def on_mount(self) -> None:
        dt = self.query_one(ImageDirectoryTree)
        dt.show_guides = False
        dt.focus()

    @on(DirectoryTree.FileSelected)
    async def on_image_selected(self, ev: DirectoryTree.FileSelected) -> None:
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

    @on(DirectoryTree.NodeHighlighted)
    async def on_image_highlighted(self, ev: DirectoryTree.NodeHighlighted) -> None:
        path = ev.node.data.path  # type: ignore
        image_widget = self.query_one(Image)
        if path.suffix in IMAGE_EXTENSIONS:
            try:
                image_widget.image = PILImage.open(path.as_posix())
            except UnidentifiedImageError:
                image_widget.image = None
        else:
            image_widget.image = None

    @on(Input.Changed)
    async def on_root_changed(self, ev: Input.Changed) -> None:
        dt = self.query_one(ImageDirectoryTree)
        path = Path(ev.value)
        if not path.exists() or not path.is_dir():
            return
        dt.path = path

    def compose(self) -> ComposeResult:
        with Container(
            id="image-select-container", classes="screen-container full-height"
        ):
            with Horizontal():
                with Vertical(id="image-directory-tree"):
                    yield Label("Select an image:", classes="title")
                    yield Label("Root:")
                    yield Input(Path("./").resolve().as_posix())
                    yield ImageDirectoryTree("./")
                with Container(id="image-preview"):
                    yield Image(id="image")
