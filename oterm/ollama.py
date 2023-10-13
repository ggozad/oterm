import json
import httpx

from oterm.config import Config


class OllamaError(Exception):
    pass


class OlammaLLM:
    def __init__(self, model="nous-hermes:13b", template="", system=""):
        self.model = model
        self.template = template
        self.system = system
        self.context: list[int] = []

    async def completion(self, prompt: str) -> str:
        response, context = await self._agenerate(
            prompt=prompt,
            context=self.context,
        )
        self.context = context
        return response

    async def _agenerate(
        self, prompt: str, context: list[int]
    ) -> tuple[str, list[int]]:
        client = httpx.AsyncClient()
        jsn = {
            "model": self.model,
            "prompt": prompt,
            "context": context,
        }
        if self.system:
            jsn["system"] = self.system
        if self.template:
            jsn["template"] = self.template

        res = ""
        async with client.stream(
            "POST", f"{Config.OLLAMA_URL}/generate", json=jsn
        ) as response:
            async for line in response.aiter_lines():
                body = json.loads(line)
                res += body.get("response", "")

                if "error" in body:
                    raise OllamaError(body["error"])

                if body.get("done", False):
                    return res, body["context"]
        return res, []
