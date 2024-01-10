import json

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, TabbedContent, TabPane

from oterm.app.model_selection import ModelSelection
from oterm.app.splash import SplashScreen
from oterm.app.widgets.chat import ChatContainer
from oterm.store.store import Store


class OTerm(App):
    TITLE = "oTerm"
    SUB_TITLE = "A terminal-based Ollama client."
    CSS_PATH = "oterm.tcss"
    BINDINGS = [
        ("ctrl+n", "new_chat", "new chat"),
        ("ctrl+t", "toggle_dark", "toggle theme"),
        ("ctrl+q", "quit", "quit"),
    ]

    def action_toggle_dark(self) -> None:
        self.dark = not self.dark

    async def action_quit(self) -> None:
        return self.exit()

    def action_new_chat(self) -> None:
        async def on_model_select(model_info: str) -> None:
            model: dict = json.loads(model_info)
            tabs = self.query_one(TabbedContent)
            tab_count = tabs.tab_count
            name = f"chat #{tab_count+1} - {model['name']}"
            id = await self.store.save_chat(
                id=None,
                name=name,
                model=model["name"],
                context="[]",
                template=model["template"],
                system=model["system"],
                format=model["format"],
            )
            pane = TabPane(name, id=f"chat-{id}")
            pane.compose_add_child(
                ChatContainer(
                    db_id=id,
                    chat_name=name,
                    model=model["name"],
                    system=model["system"],
                    template=model["template"],
                    format=model["format"],
                    messages=[],
                )
            )
            tabs.add_pane(pane)
            tabs.active = f"chat-{id}"

        self.push_screen(ModelSelection(), on_model_select)

    async def on_mount(self) -> None:
        self.store = await Store.create()
        saved_chats = await self.store.get_chats()  # type: ignore
        if not saved_chats:
            self.action_new_chat()
        else:
            tabs = self.query_one(TabbedContent)
            for id, name, model, context, template, system, format in saved_chats:
                messages = await self.store.get_messages(id)
                pane = TabPane(name, id=f"chat-{id}")
                pane.compose_add_child(
                    ChatContainer(
                        db_id=id,
                        chat_name=name,
                        model=model,
                        context=context,
                        messages=messages,  # type: ignore
                        template=template,
                        system=system,
                        format=format,
                    )
                )
                tabs.add_pane(pane)
                tabs.active = f"chat-{id}"
        await self.push_screen(SplashScreen())

    def compose(self) -> ComposeResult:
        yield Header()
        yield TabbedContent(id="tabs")
        yield Footer()


app = OTerm()
