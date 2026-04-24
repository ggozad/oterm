from pathlib import Path

from textual.app import App
from textual.widgets import DirectoryTree, Input

from oterm.app.image_browser import ImageSelect
from oterm.app.widgets.image import ImageDirectoryTree


class _Host(App):
    pass


async def test_escape_cancels_with_none(tmp_path):
    app = _Host()
    async with app.run_test() as pilot:
        received: list = []
        app.push_screen(ImageSelect(), lambda r: received.append(r))
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert received == [None]


async def test_selecting_valid_image_dismisses_with_path_and_b64(tmp_path, llama_image):
    img_path = tmp_path / "llama.jpg"
    img_path.write_bytes(llama_image)

    app = _Host()
    async with app.run_test() as pilot:
        received: list = []
        screen = ImageSelect()
        app.push_screen(screen, lambda r: received.append(r))
        await pilot.pause()

        await screen.on_image_selected(
            DirectoryTree.FileSelected(None, img_path)  # ty: ignore[invalid-argument-type]
        )
        await pilot.pause()

        assert received
        path, b64 = received[0]
        assert path == img_path
        assert isinstance(b64, str) and len(b64) > 0


async def test_selecting_non_image_dismisses_with_none(tmp_path):
    bad = tmp_path / "not-an-image.txt"
    bad.write_text("nope")

    app = _Host()
    async with app.run_test() as pilot:
        received: list = []
        screen = ImageSelect()
        app.push_screen(screen, lambda r: received.append(r))
        await pilot.pause()

        await screen.on_image_selected(
            DirectoryTree.FileSelected(None, bad)  # ty: ignore[invalid-argument-type]
        )
        await pilot.pause()
        assert received == [None]


async def test_root_input_changes_update_tree(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()

    app = _Host()
    async with app.run_test() as pilot:
        screen = ImageSelect()
        app.push_screen(screen)
        await pilot.pause()

        tree = screen.query_one(ImageDirectoryTree)
        root_input = screen.query_one(Input)
        root_input.value = str(sub)
        await pilot.pause()
        assert tree.path == sub


async def test_root_input_ignores_nonexistent_path(tmp_path):
    app = _Host()
    async with app.run_test() as pilot:
        screen = ImageSelect()
        app.push_screen(screen)
        await pilot.pause()

        tree = screen.query_one(ImageDirectoryTree)
        original = tree.path
        root_input = screen.query_one(Input)
        root_input.value = "/nope/does-not-exist"
        await pilot.pause()
        assert tree.path == original


async def test_highlight_image_sets_preview(tmp_path, llama_image):
    img_path = tmp_path / "llama.jpg"
    img_path.write_bytes(llama_image)

    app = _Host()
    async with app.run_test() as pilot:
        screen = ImageSelect()
        app.push_screen(screen)
        await pilot.pause()

        # Build a fake NodeHighlighted-like event
        from textual.widgets._directory_tree import DirEntry

        class _FakeNode:
            def __init__(self, p: Path):
                self.data = DirEntry(path=p, loaded=True)

        class _FakeEvent:
            def __init__(self, p: Path):
                self.node = _FakeNode(p)

        await screen.on_image_highlighted(_FakeEvent(img_path))  # ty: ignore[invalid-argument-type]
        await pilot.pause()

        from textual_image.widget import Image as ImageWidget

        widget = screen.query_one(ImageWidget)
        assert widget.image is not None


async def test_highlight_non_image_clears_preview(tmp_path):
    bad = tmp_path / "notes.txt"
    bad.write_text("hi")

    app = _Host()
    async with app.run_test() as pilot:
        screen = ImageSelect()
        app.push_screen(screen)
        await pilot.pause()

        from textual.widgets._directory_tree import DirEntry

        class _FakeNode:
            def __init__(self, p: Path):
                self.data = DirEntry(path=p, loaded=True)

        class _FakeEvent:
            def __init__(self, p: Path):
                self.node = _FakeNode(p)

        await screen.on_image_highlighted(_FakeEvent(bad))  # ty: ignore[invalid-argument-type]
        await pilot.pause()

        from textual_image.widget import Image as ImageWidget

        widget = screen.query_one(ImageWidget)
        assert widget.image is None
