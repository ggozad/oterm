from pathlib import Path

from pydantic_ai import Tool as PydanticTool
from pydantic_ai.capabilities import WebFetch, WebSearch
from pydantic_ai_harness import FileSystem
from pydantic_ai_harness.memory import Memory, SqliteMemoryStore

from oterm.tools.capabilities import capability_defs


def _def(name: str):
    return next(d for d in capability_defs if d["name"] == name)


class TestCapabilityDefs:
    def test_registry_names(self):
        assert [d["name"] for d in capability_defs] == [
            "web_search",
            "web_fetch",
            "memory",
            "filesystem",
        ]

    def test_descriptions_populated(self):
        for capability_def in capability_defs:
            assert capability_def["description"] != ""

    def test_web_search_uses_duckduckgo_fallback(self):
        from pydantic_ai.common_tools.duckduckgo import DuckDuckGoSearchTool

        capability = _def("web_search")["factory"]()
        assert isinstance(capability, WebSearch)
        assert isinstance(capability.local, PydanticTool)
        assert isinstance(capability.local.function.__self__, DuckDuckGoSearchTool)

    def test_web_fetch_uses_local_fallback(self):
        from pydantic_ai.common_tools.web_fetch import WebFetchLocalTool

        capability = _def("web_fetch")["factory"]()
        assert isinstance(capability, WebFetch)
        assert isinstance(capability.local, PydanticTool)
        assert isinstance(capability.local.function.__self__, WebFetchLocalTool)

    def test_memory_is_global_sqlite_in_data_dir(self, tmp_path, monkeypatch):
        from oterm.config import envConfig

        monkeypatch.setattr(envConfig, "OTERM_DATA_DIR", tmp_path)
        capability = _def("memory")["factory"]()
        assert isinstance(capability, Memory)
        assert isinstance(capability.store, SqliteMemoryStore)

    def test_filesystem_rooted_at_cwd(self):
        capability = _def("filesystem")["factory"]()
        assert isinstance(capability, FileSystem)
        assert capability.root_dir == Path.cwd()
