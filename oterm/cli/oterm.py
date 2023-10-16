from importlib import metadata

import typer

from oterm.app.oterm import app

cli = typer.Typer()


@cli.command()
def oterm(version: bool = typer.Option(None, "--version", "-v")):
    if version:
        typer.echo(f"oterm v{metadata.version('oterm')}")
        exit(0)
    app.run()


if __name__ == "__main__":
    cli()
