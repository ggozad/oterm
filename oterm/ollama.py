import json
from typing import Any, AsyncGenerator, Literal

import httpx

from oterm.config import envConfig


class OllamaError(Exception):
    pass


class OllamaConnectError(OllamaError):
    def __init__(self) -> None:
        super().__init__(
            f"Failed to connect to Ollama server running at {envConfig.OLLAMA_URL}. "
            "You can set OLLAMA_URL if you want to use a different server."
        )


class OllamaLLM:
    def __init__(
        self,
        model="nous-hermes:13b",
        template: str | None = None,
        system: str | None = None,
        context: list[int] = [],
        format: Literal["json"] | None = None,
    ):
        self.model = model
        self.template = template
        self.system = system
        self.context = context
        self.format = format

    async def completion(self, prompt: str, images: list[str] = []) -> str:
        response = ""
        context = []
        async for text, ctx in self._agenerate(
            prompt=prompt,
            context=self.context,
            images=images,
        ):
            response = text
            context = ctx
        self.context = context
        return response

    async def stream(
        self, prompt: str, images: list[str] = []
    ) -> AsyncGenerator[str, Any]:
        context = []

        async for text, ctx in self._agenerate(
            prompt=prompt,
            context=self.context,
            images=images,
        ):
            context = ctx
            yield text

        self.context = context

    async def _agenerate(
        self, prompt: str, context: list[int], images: list[str] = []
    ) -> AsyncGenerator[tuple[str, list[int]], Any]:
        client = httpx.AsyncClient(verify=envConfig.OTERM_VERIFY_SSL)
        jsn = {
            "model": self.model,
            "prompt": prompt,
            "context": context,
        }
        if self.system:
            jsn["system"] = self.system
        if self.template:
            jsn["template"] = self.template
        if self.format:
            jsn["format"] = self.format
        if images:
            jsn["images"] = images
        res = ""

        try:
            async with client.stream(
                "POST", f"{envConfig.OLLAMA_URL}/generate", json=jsn, timeout=None
            ) as response:
                async for line in response.aiter_lines():
                    body = json.loads(line)
                    res += body.get("response", "")
                    yield res, []
                    if "error" in body:
                        raise OllamaError(body["error"])

                    if body.get("done", False):
                        yield res, body["context"]
        except httpx.ConnectError:
            raise OllamaConnectError()


class OllamaAPI:
    async def get_models(self) -> list[dict[str, Any]]:
        client = httpx.AsyncClient(verify=envConfig.OTERM_VERIFY_SSL)
        try:
            response = await client.get(f"{envConfig.OLLAMA_URL}/tags")
        except httpx.ConnectError:
            raise OllamaConnectError()
        return response.json().get("models", []) or []

    async def get_model_info(self, model: str) -> dict[str, Any]:
        client = httpx.AsyncClient(verify=envConfig.OTERM_VERIFY_SSL)
        try:
            response = await client.post(
                f"{envConfig.OLLAMA_URL}/show", json={"name": model}
            )
        except httpx.ConnectError:
            raise OllamaConnectError()
        if response.json().get("error"):
            raise OllamaError(response.json()["error"])
        return response.json()

    async def pull_model(self, model: str) -> None:
        client = httpx.AsyncClient()
        async with client.stream(
            "POST", f"{envConfig.OLLAMA_URL}/pull", json={"name": model}, timeout=None
        ) as response:
            async for line in response.aiter_lines():
                body = json.loads(line)
                if "error" in body:
                    raise OllamaError(body["error"])
                if body.get("status", "") == "success":
                    return
