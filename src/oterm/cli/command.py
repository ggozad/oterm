import asyncio
from pathlib import Path
from typing import Annotated

import typer

from oterm.command.create import app
from oterm.store.store import Store

cli = typer.Typer()


@cli.command("create")
def create(
    name: Annotated[str, typer.Argument(help="The name of the command to create.")],
):
    app.run(name)


@cli.command("list")
def list_commands():
    async def get_commands():
        store = await Store.get_store()
        commands = await store.get_chats(type="command")
        return commands

    commands = asyncio.run(get_commands())
    if not commands:
        typer.echo("No commands found.")
        return

    typer.echo("Commands found:")
    for command in commands:
        id, name, *rest = command
        path = Path.home() / ".local" / "bin" / name
        exists = path.exists()
        typer.echo(f"{id}: {name} -> {exists and str(path) or 'Not found'}")


@cli.command("delete")
def delete_command(
    id: Annotated[int, typer.Argument(help="The id of the command to delete.")],
):
    async def delete_comm():
        store = await Store.get_store()
        command = await store.get_chat(id=id)
        if not command:
            typer.echo("Command not found.")
            return
        _, name, *rest = command
        path = Path.home() / ".local" / "bin" / name
        path.unlink(missing_ok=True)
        await store.delete_chat(id=id)
        typer.echo("Command deleted.")

    asyncio.run(delete_comm())


if __name__ == "__main__":
    cli()
