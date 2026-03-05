from ast import literal_eval
from typing import Any

from ollama import Options


def parse_ollama_parameters(parameter_text: str) -> dict[str, Any]:
    lines = parameter_text.split("\n")
    params: dict[str, Any] = {}
    valid_params = set(Options.model_fields.keys())
    for line in lines:
        if line:
            key, value = line.split(maxsplit=1)
            try:
                value = literal_eval(value)
            except (SyntaxError, ValueError):
                pass
            if key not in valid_params:
                continue
            if key in params:
                if not isinstance(params[key], list):
                    params[key] = [params[key], value]
                else:
                    params[key].append(value)
            else:
                params[key] = value
    return params
