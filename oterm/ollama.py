import json
from typing import Any, AsyncGenerator

import httpx

from oterm.config import Config


class OllamaError(Exception):
    pass


class OllamaLLM:
    def __init__(self, model="nous-hermes:13b", template="", system=""):
        self.model = model
        self.template = template
        self.system = system
        self.context: list[int] = []

    async def completion(self, prompt: str) -> str:
        response = ""
        context = []
        async for text, ctx in self._agenerate(
            prompt=prompt,
            context=self.context,
        ):
            response = text
            context = ctx
        self.context = context
        return response

    async def stream(self, prompt) -> AsyncGenerator[str, Any]:
        context = []

        async for text, ctx in self._agenerate(
            prompt=prompt,
            context=self.context,
        ):
            context = ctx
            yield text

        self.context = context

    async def _agenerate(
        self, prompt: str, context: list[int]
    ) -> AsyncGenerator[tuple[str, list[int]], Any]:
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
            "POST", f"{Config.OLLAMA_URL}/generate", json=jsn, timeout=None
        ) as response:
            async for line in response.aiter_lines():
                body = json.loads(line)
                res += body.get("response", "")
                yield res, []
                if "error" in body:
                    raise OllamaError(body["error"])

                if body.get("done", False):
                    yield res, body["context"]


class OllamaAPI:
    async def get_models(self) -> list[dict[str, Any]]:
        client = httpx.AsyncClient()
        response = await client.get(f"{Config.OLLAMA_URL}/tags")
        return response.json().get("models", [])

    async def get_model_info(self, model: str) -> dict[str, Any]:
        client = httpx.AsyncClient()
        response = await client.post(f"{Config.OLLAMA_URL}/show", json={"name": model})
        if response.json().get("error"):
            raise OllamaError(response.json()["error"])
        return response.json()

    async def pull_model(self, model: str) -> None:
        client = httpx.AsyncClient()
        async with client.stream(
            "POST", f"{Config.OLLAMA_URL}/pull", json={"name": model}, timeout=None
        ) as response:
            async for line in response.aiter_lines():
                body = json.loads(line)
                if "error" in body:
                    raise OllamaError(body["error"])
                if body.get("status", "") == "success":
                    return
