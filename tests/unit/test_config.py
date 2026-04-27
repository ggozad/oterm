import json

from oterm.config import AppConfig, EnvConfig


class TestEnvConfig:
    def test_defaults(self):
        cfg = EnvConfig.model_validate({})
        assert cfg.OLLAMA_HOST == "127.0.0.1:11434"
        assert cfg.OLLAMA_URL == ""
        assert cfg.OTERM_VERIFY_SSL is True

    def test_env_overrides(self, tmp_path):
        cfg = EnvConfig.model_validate(
            {
                "OLLAMA_HOST": "example.com:1234",
                "OLLAMA_URL": "https://example.com",
                "OTERM_VERIFY_SSL": "false",
                "OTERM_DATA_DIR": str(tmp_path),
            }
        )
        assert cfg.OLLAMA_HOST == "example.com:1234"
        assert cfg.OLLAMA_URL == "https://example.com"
        assert cfg.OTERM_VERIFY_SSL is False
        assert cfg.OTERM_DATA_DIR == tmp_path


class TestAppConfig:
    def test_first_run_creates_file_with_defaults(self, tmp_path):
        path = tmp_path / "config.json"
        assert not path.exists()
        cfg = AppConfig(path=path)
        assert path.exists()
        assert cfg.get("theme") == "textual-dark"
        assert cfg.get("splash-screen") is True

    def test_set_persists_to_disk(self, tmp_path):
        path = tmp_path / "config.json"
        cfg = AppConfig(path=path)
        cfg.set("theme", "solarized")

        reread = json.loads(path.read_text())
        assert reread["theme"] == "solarized"

    def test_get_with_missing_key_returns_default(self, tmp_path):
        cfg = AppConfig(path=tmp_path / "config.json")
        assert cfg.get("nope") is None
        assert cfg.get("nope", "fallback") == "fallback"

    def test_loaded_values_merge_with_defaults(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text(json.dumps({"theme": "light", "custom": 42}))

        cfg = AppConfig(path=path)
        assert cfg.get("theme") == "light"
        assert cfg.get("custom") == 42
        assert cfg.get("splash-screen") is True

    def test_create_dir_if_missing(self, tmp_path):
        path = tmp_path / "nested" / "config.json"
        AppConfig(path=path)
        assert path.exists()
        assert path.parent.is_dir()
