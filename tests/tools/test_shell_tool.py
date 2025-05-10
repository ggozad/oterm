import pytest

from oterm.ollamaclient import OllamaLLM
from oterm.tools.shell import ShellTool, shell_command


@pytest.mark.asyncio
async def test_shell(default_model):
    llm = OllamaLLM(
        model=default_model,
        tool_defs=[
            {"tool": ShellTool, "callable": shell_command},
        ],
    )
    res = await llm.completion(
        "What is the current directory? Use the shell tool available and execute the command."
    )
    assert "oterm" in res
