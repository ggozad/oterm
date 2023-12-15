import json

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, TabbedContent, TabPane

from oterm.app.chat import ChatContainer
from oterm.app.chat_rename import ChatRename
from oterm.app.image_browser import ImageSelect
from oterm.app.model_selection import ModelSelection
from oterm.app.splash import SplashScreen
from oterm.store.store import Store


class OTerm(App):
    TITLE = "oTerm"
    SUB_TITLE = "A terminal-based Ollama client."
    CSS_PATH = "oterm.tcss"
    BINDINGS = [
        ("ctrl+n", "new_chat", "new chat"),
        ("ctrl+t", "toggle_dark", "Toggle dark mode"),
        ("ctrl+r", "rename_chat", "rename chat"),
        ("ctrl+x", "forget_chat", "forget chat"),
        ("i", "image_select", "image select"),
        ("ctrl+q", "quit", "Quit"),
    ]
    SCREENS = {
        "splash": SplashScreen(),
        "model_selection": ModelSelection(),
    }

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
                )
            )
            tabs.add_pane(pane)
            tabs.active = f"chat-{id}"

        self.push_screen("model_selection", on_model_select)

    async def action_rename_chat(self) -> None:
        tabs = self.query_one(TabbedContent)
        if not tabs.active:
            return
        id = int(tabs.active.split("-")[1])
        chat = await self.store.get_chat(id)
        if chat is None:
            return
        _, name, model, context, template, system, format = chat

        async def on_chat_rename(name: str) -> None:
            await self.store.rename_chat(id, name)
            messages = await self.store.get_messages(id)
            tabs.remove_pane(tabs.active)
            pane = TabPane(name, id=f"chat-{id}")
            pane.compose_add_child(
                ChatContainer(
                    db_id=id,
                    chat_name=name,
                    model=model,
                    messages=messages,
                    context=context,
                    template=template,
                    system=system,
                    format=format,
                )
            )
            added = tabs.add_pane(pane)
            await added()
            tabs.active = f"chat-{id}"

        if chat:
            screen = ChatRename()
            screen.old_name = name
            self.push_screen(screen, on_chat_rename)

    async def action_forget_chat(self) -> None:
        tabs = self.query_one(TabbedContent)
        if not tabs.active:
            return
        id = int(tabs.active.split("-")[1])
        await self.store.delete_chat(id)
        tabs.remove_pane(tabs.active)

    async def action_image_select(self) -> None:
        async def on_image_selected(image) -> None:
            path, b64 = image
            print(path, b64)

        screen = ImageSelect()
        self.push_screen(screen, on_image_selected)

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

        await self.push_screen("splash")

    def compose(self) -> ComposeResult:
        yield Header()
        yield TabbedContent(id="tabs")
        yield Footer()


app = OTerm()
