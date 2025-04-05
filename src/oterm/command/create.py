import json
import stat
from collections.abc import Iterable
from importlib import metadata
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, TabbedContent

from oterm.app.chat_edit import ChatEdit
from oterm.app.pull_model import PullModel
from oterm.app.splash import splash
from oterm.app.widgets.chat import ChatContainer
from oterm.config import appConfig
from oterm.store.store import Store
from oterm.tools.mcp.setup import setup_mcp_servers, teardown_mcp_servers


class CreateCommandApp(App):
    TITLE = "oterm - Create Command"
    SUB_TITLE = "Create custom LLM chats as commands."
    CSS_PATH = "../app/oterm.tcss"
    BINDINGS = [
        Binding("ctrl+q", "quit", "quit", id="quit"),
    ]

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        yield from super().get_system_commands(screen)

        yield SystemCommand(
            "Pull model",
            "Pulls (or updates) a model from the Ollama server",
            self.action_pull_model,
        )

    async def create_command(self) -> None:
        async def on_done(model_info) -> None:
            if model_info is None:
                await self.action_quit()
            model = json.loads(model_info)
            store = await Store.get_store()

            db_id = await store.save_chat(
                id=None,
                name=self.command_name,
                model=model["name"],
                system=model["system"],
                format=model["format"],
                parameters=model["parameters"],
                keep_alive=model["keep_alive"],
                tools=model["tools"],
                type="command",
            )
            # Load the template from the package
            environment = Environment(loader=FileSystemLoader(Path(__file__).parent))
            template = environment.get_template("command_template.py.jinja")
            path = Path.home() / ".local/bin" / self.command_name
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                f.write(
                    template.render(
                        db_id=db_id,
                        name=self.command_name,
                        version=metadata.version("oterm"),
                    )
                )
            path.chmod(path.stat().st_mode | stat.S_IEXEC)
            await self.action_quit()

        await self.push_screen(ChatEdit(), callback=on_done)

    async def action_quit(self) -> None:
        self.log("Quitting...")
        await teardown_mcp_servers()
        return self.exit()

    async def action_pull_model(self) -> None:
        tabs = self.query_one(TabbedContent)
        if tabs.active_pane is None:
            screen = PullModel("")
        else:
            chat = tabs.active_pane.query_one(ChatContainer)
            screen = PullModel(chat.ollama.model)
        self.push_screen(screen)

    async def load_mcp(self):
        from oterm.tools import avail_tool_defs

        mcp_tool_defs, mcp_tool_prompts = await setup_mcp_servers()
        avail_tool_defs += mcp_tool_defs

    async def on_mount(self) -> None:
        theme = appConfig.get("theme")
        if theme:
            if theme == "dark":
                self.theme = "textual-dark"
            elif theme == "light":
                self.theme = "textual-light"
            else:
                self.theme = theme
        self.dark = appConfig.get("theme") == "dark"
        self.watch(self.app, "theme", self.on_theme_change, init=False)

        await self.load_mcp()

        async def on_splash_done(message) -> None:
            await self.create_command()

        if appConfig.get("splash-screen"):
            self.push_screen(splash, callback=on_splash_done)
        else:
            await on_splash_done("")

    def on_theme_change(self, old_value: str, new_value: str) -> None:
        if appConfig.get("theme") != new_value:
            appConfig.set("theme", new_value)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()

    def run(self, name: str):
        self.command_name = name
        return super().run()


app = CreateCommandApp()
