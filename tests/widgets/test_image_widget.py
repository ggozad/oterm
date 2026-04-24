from pathlib import Path

from oterm.app.widgets.image import IMAGE_EXTENSIONS, ImageAdded, ImageDirectoryTree


def test_image_added_carries_path_and_b64():
    msg = ImageAdded(Path("/tmp/x.png"), "b64data")
    assert msg.path == Path("/tmp/x.png")
    assert msg.image == "b64data"


def test_image_extensions_contains_common_formats():
    assert ".png" in IMAGE_EXTENSIONS
    assert ".jpg" in IMAGE_EXTENSIONS
    assert ".gif" in IMAGE_EXTENSIONS


def test_directory_tree_filter_keeps_images_and_dirs(tmp_path):
    img = tmp_path / "a.png"
    img.write_bytes(b"fake")
    txt = tmp_path / "b.txt"
    txt.write_text("no")
    subdir = tmp_path / "sub"
    subdir.mkdir()

    tree = ImageDirectoryTree(tmp_path)
    kept = list(tree.filter_paths([img, txt, subdir]))
    assert img in kept
    assert subdir in kept
    assert txt not in kept
