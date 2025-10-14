import pytest

from oterm.ollamaclient import OllamaLLM
from oterm.tools.shell import ShellTool, shell_command


@pytest.mark.asyncio
async def test_shell(default_model, deterministic_options):
    llm = OllamaLLM(
        model=default_model,
        tool_defs=[
            {"tool": ShellTool, "callable": shell_command},
        ],
        options=deterministic_options,
    )
    res = ""
    async for _, text in llm.stream(
        "What is the current directory? Use the shell tool available and execute the command."
    ):
        res = text
    assert "oterm" in res
