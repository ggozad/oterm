from pathlib import Path
from typing import Iterable

from PIL import Image as PILImage
from PIL import UnidentifiedImageError
from rich_pixels import Pixels
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import DirectoryTree

IMG_MAX_SIZE = 80
IMAGE_EXTENSIONS = PILImage.registered_extensions()


class ImageAdded(Message):
    def __init__(self, path: Path, image: str) -> None:
        self.path = path
        self.image = image
        super().__init__()


class Image(Widget):
    path: reactive[str] = reactive("")

    def __init__(self, id="", classes="") -> None:
        self.pixels = None
        super().__init__(id=id, classes=classes)

    def watch_path(self, path: str) -> None:
        if path:
            try:
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
            except UnidentifiedImageError:
                self.pixels = None
        else:
            self.pixels = None

    def render(self):
        if self.pixels:
            return self.pixels
        return ""


class ImageDirectoryTree(DirectoryTree):
    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [
            path for path in paths if path.suffix in IMAGE_EXTENSIONS or path.is_dir()
        ]
