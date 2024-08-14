from ast import literal_eval
from typing import Any, AsyncGenerator, AsyncIterator, Literal, Mapping

from ollama import AsyncClient, Client, Options

from oterm.config import envConfig


class OllamaLLM:
    def __init__(
        self,
        model="nous-hermes:13b",
        system: str | None = None,
        history: list[str] = [],
        format: Literal["", "json"] = "",
        options: Options = Options(),
        keep_alive: int = 5,
    ):
        self.model = model
        self.system = system
        self.history = history
        self.format = format
        self.keep_alive = keep_alive
        self.options = options

    async def completion(self, prompt: str, images: list[str] = []) -> str:
        client = AsyncClient(
            host=envConfig.OLLAMA_URL, verify=envConfig.OTERM_VERIFY_SSL
        )
        system_prompt = {"role": "system", "content": self.system}
        user_prompt = {'role': 'user', 'content': prompt}
        if images:
            user_prompt['images'] = images
        self.history.append(user_prompt)
        response: dict = await client.chat(
            model=self.model,
            messages=[system_prompt] + self.history,
            keep_alive=f"{self.keep_alive}m",
	    options=self.options,
            format=self.format,
        )
        ollama_response = response.get("message", {}).get("content", "")
        self.history.append({'role': 'assistant', 'content': ollama_response})
        return ollama_response

    async def stream(
        self, prompt: str, images: list[str] = []
    ) -> AsyncGenerator[str, Any]:
        client = AsyncClient(
            host=envConfig.OLLAMA_URL, verify=envConfig.OTERM_VERIFY_SSL
        )
        system_prompt = {"role": "system", "content": self.system}
        user_prompt = {'role': 'user', 'content': prompt}
        if images:
            user_prompt['images'] = images
        self.history.append(user_prompt)
        stream: AsyncIterator[dict] = await client.chat(
            model=self.model,
            messages=[system_prompt] + self.history,
            stream=True,
	    options=self.options,
            keep_alive=f"{self.keep_alive}m",
            format=self.format,
        )
        text = ""
        async for response in stream:
            ollama_response = response.get("message", {}).get("content", "")
            text = text + ollama_response
            yield text

        self.history.append({'role': 'assistant', 'content': text})

    @staticmethod
    def list() -> Mapping[str, Any]:
        client = Client(host=envConfig.OLLAMA_URL, verify=envConfig.OTERM_VERIFY_SSL)
        return client.list()

    @staticmethod
    def show(model: str) -> Mapping[str, Any]:
        client = Client(host=envConfig.OLLAMA_URL, verify=envConfig.OTERM_VERIFY_SSL)
        return client.show(model)


def parse_ollama_parameters(parameter_text: str) -> Options:
    lines = parameter_text.split("\n")
    params = Options()
    for line in lines:
        if line:
            key, value = line.split(maxsplit=1)
            try:
                value = literal_eval(value)
            except (SyntaxError, ValueError):
                pass
            if params.get(key):
                if not isinstance(params[key], list):
                    params[key] = [params[key], value]
                else:
                    params[key].append(value)
            else:
                params[key] = value
    return params
