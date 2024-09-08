import pytest

from oterm.ollamaclient import OllamaLLM
from oterm.tools.shell import ShellTool, shell_command


@pytest.mark.asyncio
async def test_shell():
    llm = OllamaLLM(
        model="mistral-nemo",
        tool_defs=[
            {"tool": ShellTool, "callable": shell_command},
        ],
    )
    res = await llm.completion("What is the current directory")
    assert "oterm" in res
