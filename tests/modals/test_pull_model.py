from textual.app import App
from textual.widgets import Input, TextArea

from oterm.app.pull_model import PullModel


class _Host(App):
    pass


class _FakeProgress:
    def __init__(self, status: str):
        self._status = status

    def model_dump_json(self) -> str:
        import json

        return json.dumps({"status": self._status})


async def test_initial_model_value(monkeypatch):
    app = _Host()
    async with app.run_test() as pilot:
        screen = PullModel("llama3")
        app.push_screen(screen)
        await pilot.pause()
        assert screen.query_one(Input).value == "llama3"


async def test_escape_cancels():
    app = _Host()
    async with app.run_test() as pilot:
        received: list[str | None] = []
        app.push_screen(PullModel(""), lambda r: received.append(r))
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert received == [None]


async def test_input_change_updates_model_name():
    app = _Host()
    async with app.run_test() as pilot:
        screen = PullModel("old")
        app.push_screen(screen)
        await pilot.pause()

        screen.query_one(Input).value = "new-model"
        await pilot.pause()
        assert screen.model == "new-model"


async def test_pull_streams_progress_into_log(monkeypatch):
    from oterm.providers import ollama as ollama_mod

    def fake_pull(model):
        yield _FakeProgress("pulling manifest")
        yield _FakeProgress("success")

    monkeypatch.setattr(ollama_mod, "pull_model", fake_pull)

    app = _Host()
    async with app.run_test() as pilot:
        screen = PullModel("test-model")
        app.push_screen(screen)
        await pilot.pause()

        screen.pull_model()
        # Give the worker a chance to stream the entire fake progress.
        for _ in range(30):
            await pilot.pause()
            log_text = screen.query_one(".log", TextArea).text
            if "success" in log_text:
                break

        log_text = screen.query_one(".log", TextArea).text
        assert "pulling manifest" in log_text
        assert "success" in log_text


async def test_pull_error_logged(monkeypatch):
    from ollama import ResponseError

    from oterm.providers import ollama as ollama_mod

    def fake_pull(model):
        raise ResponseError("nope", 404)
        yield  # pragma: no cover

    monkeypatch.setattr(ollama_mod, "pull_model", fake_pull)

    app = _Host()
    async with app.run_test() as pilot:
        screen = PullModel("x")
        app.push_screen(screen)
        await pilot.pause()

        screen.pull_model()
        for _ in range(30):
            await pilot.pause()
            if "Error" in screen.query_one(".log", TextArea).text:
                break

        assert "Error" in screen.query_one(".log", TextArea).text
