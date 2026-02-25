# Adapted from pydantic-ai: https://github.com/pydantic/pydantic-ai/blob/main/tests/json_body_serializer.py
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
import json
import urllib.parse
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from yaml import Dumper, SafeLoader
else:
    try:
        from yaml import CDumper as Dumper
        from yaml import CSafeLoader as SafeLoader
    except ImportError:
        from yaml import Dumper, SafeLoader

FILTERED_HEADER_PREFIXES = ["anthropic-", "cf-", "x-"]
FILTERED_HEADERS = {
    "authorization",
    "date",
    "request-id",
    "server",
    "user-agent",
    "via",
    "set-cookie",
    "api-key",
}
ALLOWED_HEADER_PREFIXES: set[str] = set()
ALLOWED_HEADERS: set[str] = set()

ALLOWED_LOCALHOST_PATHS = ["/api/", "/v1/"]


class LiteralDumper(Dumper):
    pass


def str_presenter(dumper: Dumper, data: str):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


LiteralDumper.add_representer(str, str_presenter)


def _is_filtered_localhost(uri: str) -> bool:
    parsed = urllib.parse.urlparse(uri)
    if parsed.hostname not in ("localhost", "127.0.0.1"):
        return False
    return not any(parsed.path.startswith(p) for p in ALLOWED_LOCALHOST_PATHS)


def deserialize(cassette_string: str):
    cassette_dict = yaml.load(cassette_string, Loader=SafeLoader)
    for interaction in cassette_dict["interactions"]:
        for kind, data in interaction.items():
            parsed_body = data.pop("parsed_body", None)
            if parsed_body is not None:
                dumped_body = json.dumps(parsed_body)
                data["body"] = (
                    {"string": dumped_body} if kind == "response" else dumped_body
                )
    return cassette_dict


def serialize(cassette_dict: Any):
    cassette_dict["interactions"] = [
        i
        for i in cassette_dict["interactions"]
        if not _is_filtered_localhost(i["request"]["uri"])
    ]

    for interaction in cassette_dict["interactions"]:
        for _kind, data in interaction.items():
            headers: dict[str, list[str]] = data.get("headers", {})
            headers = {k.lower(): v for k, v in headers.items()}
            headers = {k: v for k, v in headers.items() if k not in FILTERED_HEADERS}
            headers = {
                k: v
                for k, v in headers.items()
                if not any(k.startswith(prefix) for prefix in FILTERED_HEADER_PREFIXES)
                or k in ALLOWED_HEADERS
                or any(k.startswith(prefix) for prefix in ALLOWED_HEADER_PREFIXES)
            }
            data["headers"] = headers

            content_type = headers.get("content-type", [])
            if any(
                isinstance(header, str) and header.startswith("application/json")
                for header in content_type
            ):
                body = data.get("body", None)
                assert body is not None, data
                if isinstance(body, dict):
                    body = body.get("string")
                if body:
                    data["parsed_body"] = json.loads(body)
                    if "access_token" in data["parsed_body"]:
                        data["parsed_body"]["access_token"] = "scrubbed"
                    del data["body"]
            if content_type == ["application/x-www-form-urlencoded"]:
                query_params = urllib.parse.parse_qs(data["body"])
                for key in ["client_id", "client_secret", "refresh_token"]:
                    if key in query_params:
                        query_params[key] = ["scrubbed"]
                        data["body"] = urllib.parse.urlencode(query_params)

    return yaml.dump(cassette_dict, Dumper=LiteralDumper, allow_unicode=True, width=120)
