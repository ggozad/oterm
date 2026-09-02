import importlib
import importlib.util
import os
import sys
import types
from pathlib import Path

from pydantic_ai import Tool as PydanticTool
from pydantic_ai.capabilities import WebFetch, WebSearch
from pydantic_ai_harness import FileSystem
from pydantic_ai_harness.memory import Memory, SqliteMemoryStore

from oterm.tools.capabilities import capability_defs


def _def(name: str):
    return next(d for d in capability_defs if d["name"] == name)


def _fake_speak_module() -> types.ModuleType:
    module = types.ModuleType("pydantic_ai_tts")
    setattr(module, "Speaks", type("Speaks", (), {}))
    return module


def _reload_with_speak(monkeypatch, importable: bool) -> list[str]:
    """Names in the registry when pydantic_ai_tts is / is not installed."""
    import oterm.tools.capabilities as module

    real_find_spec = importlib.util.find_spec

    def find_spec(name, *args, **kwargs):
        if name == "pydantic_ai_tts":
            return object() if importable else None
        return real_find_spec(name, *args, **kwargs)

    monkeypatch.setattr(importlib.util, "find_spec", find_spec)
    try:
        return [d["name"] for d in importlib.reload(module).capability_defs]
    finally:
        monkeypatch.undo()
        importlib.reload(module)


class TestCapabilityDefs:
    def test_registry_names(self):
        assert [d["name"] for d in capability_defs][:4] == [
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

    def test_speak_registered_when_package_is_importable(self, monkeypatch):
        assert _reload_with_speak(monkeypatch, importable=True)[-1] == "speak"

    def test_speak_absent_when_package_is_missing(self, monkeypatch):
        assert "speak" not in _reload_with_speak(monkeypatch, importable=False)

    def test_speak_capability_is_shared_across_chats(self, monkeypatch):
        from oterm.tools.capabilities import _speak

        monkeypatch.setitem(sys.modules, "pydantic_ai_tts", _fake_speak_module())
        _speak.cache_clear()
        try:
            assert _speak() is _speak()
        finally:
            _speak.cache_clear()

    def test_telemetry_is_disabled_before_onnxruntime_is_imported(self, monkeypatch):
        import oterm.tools.capabilities as module
        from oterm.tools.capabilities import _speak

        monkeypatch.delenv("ORT_DISABLE_TELEMETRY", raising=False)
        seen = {}

        def fake_import(name):
            seen["env"] = os.environ.get("ORT_DISABLE_TELEMETRY")
            return _fake_speak_module()

        monkeypatch.setattr(module, "import_module", fake_import)
        _speak.cache_clear()
        try:
            _speak()
        finally:
            _speak.cache_clear()
        assert seen["env"] == "1"

    def test_an_explicit_telemetry_choice_is_kept(self, monkeypatch):
        from oterm.tools.capabilities import _speak

        monkeypatch.setenv("ORT_DISABLE_TELEMETRY", "0")
        monkeypatch.setitem(sys.modules, "pydantic_ai_tts", _fake_speak_module())
        _speak.cache_clear()
        try:
            _speak()
            assert os.environ["ORT_DISABLE_TELEMETRY"] == "0"
        finally:
            _speak.cache_clear()
