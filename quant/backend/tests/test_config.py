# -*- coding: utf-8 -*-
"""配置加载的行为：路径解析、缺失报错、非法值拒绝。"""
import pytest

from app.config import PROJECT_ROOT, load_settings, resolve_config_path
from tests.conftest import MINIMAL_CONFIG


def _write(tmp_path, text):
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_loads_and_resolves_dirs_against_project_root(settings):
    assert settings.host == "127.0.0.1"
    assert settings.port == 8123
    assert settings.parquet_dir == (PROJECT_ROOT / "data/parquet").resolve()
    assert settings.raw_dir == (PROJECT_ROOT / "data/raw").resolve()
    assert settings.timezone == "Asia/Shanghai"


def test_absolute_dirs_are_kept(tmp_path):
    absolute = (tmp_path / "elsewhere").resolve()
    text = MINIMAL_CONFIG.replace('parquet_dir = "data/parquet"', f'parquet_dir = "{absolute.as_posix()}"')

    settings = load_settings(_write(tmp_path, text))

    assert settings.parquet_dir == absolute


def test_missing_file_reports_actionable_error(tmp_path):
    missing = tmp_path / "nope.toml"

    with pytest.raises(FileNotFoundError) as excinfo:
        load_settings(missing)

    assert "config.example.toml" in str(excinfo.value)


def test_wildcard_cors_is_rejected(tmp_path):
    text = MINIMAL_CONFIG.replace('["http://localhost:5173"]', '["*"]')

    with pytest.raises(ValueError, match="通配符"):
        load_settings(_write(tmp_path, text))


def test_invalid_port_is_rejected(tmp_path):
    text = MINIMAL_CONFIG.replace("port = 8123", "port = 70000")

    with pytest.raises(ValueError, match="server.port"):
        load_settings(_write(tmp_path, text))


def test_invalid_timezone_is_rejected(tmp_path):
    text = MINIMAL_CONFIG.replace("Asia/Shanghai", "Mars/Olympus")

    with pytest.raises(ValueError, match="timezone"):
        load_settings(_write(tmp_path, text))


def test_env_var_selects_config_file(config_path, monkeypatch):
    monkeypatch.setenv("QUANT_CONFIG", str(config_path))

    assert resolve_config_path() == config_path.resolve()
    assert load_settings().config_path == config_path.resolve()
