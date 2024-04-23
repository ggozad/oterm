from typing import Any, AsyncGenerator, AsyncIterator, Literal, Mapping

from ollama import AsyncClient, Client

from oterm.config import envConfig


class OllamaLLM:
    def __init__(
        self,
        model="nous-hermes:13b",
        system: str | None = None,
        context: list[int] = [],
        format: Literal["", "json"] = "",
        keep_alive: str | None = None,
        model_options: dict[str, str] = {},
    ):
        self.model = model
        self.system = system
        self.context = context
        self.format = format
        self.keep_alive = keep_alive
        self.model_options = model_options

    async def completion(self, prompt: str, images: list[str] = []) -> str:
        client = AsyncClient(
            host=envConfig.OLLAMA_URL, verify=envConfig.OTERM_VERIFY_SSL
        )
        response: dict = await client.generate(
            model=self.model,
            prompt=prompt,
            context=self.context,
            system=self.system,  # type: ignore
            format=self.format,  # type: ignore
            images=images,
            keep_alive=self.keep_alive,
            options=self.model_options,
        )
        self.context = response.get("context", [])
        return response.get("response", "")

    async def stream(
        self, prompt: str, images: list[str] = []
    ) -> AsyncGenerator[str, Any]:
        client = AsyncClient(
            host=envConfig.OLLAMA_URL, verify=envConfig.OTERM_VERIFY_SSL
        )
        stream: AsyncIterator[dict] = await client.generate(
            model=self.model,
            prompt=prompt,
            context=self.context,
            system=self.system,  # type: ignore
            format=self.format,  # type: ignore
            images=images,
            keep_alive=self.keep_alive,
            options=self.model_options,
            stream=True,
        )
        text = ""
        async for response in stream:
            text = text + response.get("response", "")
            if "context" in response:
                self.context = response.get("context")
            yield text

    @staticmethod
    def list() -> Mapping[str, Any]:
        client = Client(
            host=envConfig.OLLAMA_URL, verify=envConfig.OTERM_VERIFY_SSL
        )
        return client.list()

    @staticmethod
    def show(model: str) -> Mapping[str, Any]:
        client = Client(
            host=envConfig.OLLAMA_URL, verify=envConfig.OTERM_VERIFY_SSL
        )
        return client.show(model)
