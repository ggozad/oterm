import json
from typing import List, Tuple

import requests

from oterm.config import Config


class OllamaError(Exception):
    pass


class OlammaLLM:
    def __init__(self, model="nous-hermes:13b", template="", system=""):
        self.model = model
        self.template = template
        self.system = system
        self.context: List[int] = []

    def completion(
        self,
        prompt: str,
    ) -> str:
        response, context = self._generate(
            prompt=prompt,
            context=self.context,
        )
        self.context = context
        return response

    def _generate(self, prompt: str, context: List[int]) -> Tuple[str, List[int]]:
        jsn = {
            "model": self.model,
            "prompt": prompt,
            "context": context,
        }
        if self.system:
            jsn["system"] = self.system
        if self.template:
            jsn["template"] = self.template

        r = requests.post(
            f"{Config.OLLAMA_URL}/generate",
            json=jsn,
            stream=True,
        )
        r.raise_for_status()

        response = ""
        for line in r.iter_lines():
            body = json.loads(line)
            response += body.get("response", "")

            if "error" in body:
                raise OllamaError(body["error"])

            if body.get("done", False):
                return response, body["context"]
        return response, []
