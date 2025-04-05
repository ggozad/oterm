import pytest

from oterm.ollamaclient import OllamaLLM
from oterm.tools.think import ThinkTool, think


@pytest.mark.asyncio
async def test_think():
    llm = OllamaLLM(
        model="llama3.2", tool_defs=[{"tool": ThinkTool, "callable": think}]
    )
    res = await llm.completion(
        """
Cannibals ambush a safari in the jungle and capture three men. The cannibals give the men a single chance to escape uneaten.
The captives are lined up in order of height, and are tied to stakes. The man in the rear can see the backs of his two friends, the man in the middle can see the back of the man in front, and the man in front cannot see anyone. The cannibals show the men five hats. Three of the hats are black and two of the hats are white.
Blindfolds are then placed over each man's eyes and a hat is placed on each man's head. The two hats left over are hidden. The blindfolds are then removed and it is said to the men that if one of them can guess what color hat he is wearing they can all leave unharmed.
The man in the rear who can see both of his friends' hats but not his own says, "I don't know". The middle man who can see the hat of the man in front, but not his own says, "I don't know". The front man who cannot see ANYBODY'S hat says "I know!"
What was the color of his hat? Reply just with the color of the hat.
        """
    )
    assert res.lower() == "white"
