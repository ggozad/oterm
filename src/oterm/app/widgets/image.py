from collections.abc import Iterable
from pathlib import Path

from PIL import Image as PILImage
from textual.message import Message
from textual.widgets import DirectoryTree

IMG_MAX_SIZE = 80
IMAGE_EXTENSIONS = PILImage.registered_extensions()


class ImageAdded(Message):
    def __init__(self, path: Path, image: str) -> None:
        self.path = path
        self.image = image
        super().__init__()


class ImageDirectoryTree(DirectoryTree):
    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [
            path for path in paths if path.suffix in IMAGE_EXTENSIONS or path.is_dir()
        ]
