import pytest

from oterm.ollamaclient import OllamaLLM
from oterm.tools.web import WebTool, fetch_url


@pytest.mark.asyncio
async def test_web():
    llm = OllamaLLM(
        tool_defs=[{"tool": WebTool, "callable": fetch_url}],
    )
    res = await llm.completion(
        "What's oterm in a single phrase? oterm is hosted at https://github.com/ggozad/oterm."
    )
    assert "Ollama" in res
