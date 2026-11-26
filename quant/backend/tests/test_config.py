# -*- coding: utf-8 -*-
"""配置加载的行为：路径解析、缺失报错、非法值拒绝。"""
from dataclasses import replace

import pytest

from app.config import PROJECT_ROOT, load_settings, resolve_config_path
from app.factory import create_app
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
    assert settings.meta_dir == (PROJECT_ROOT / "data/meta").resolve()
    assert settings.timezone == "Asia/Shanghai"


def test_absolute_dirs_are_kept(tmp_path):
    absolute = (tmp_path / "elsewhere").resolve()
    text = MINIMAL_CONFIG.replace('parquet_dir = "data/parquet"', f'parquet_dir = "{absolute.as_posix()}"')

    settings = load_settings(_write(tmp_path, text))

    assert settings.parquet_dir == absolute


def test_env_overrides_paths_and_port(config_path, monkeypatch, tmp_path):
    monkeypatch.setenv("QUANT_HOST", "0.0.0.0")
    monkeypatch.setenv("QUANT_PORT", "9000")
    monkeypatch.setenv("QUANT_RAW_DIR", str(tmp_path / "mnt" / "raw"))
    monkeypatch.setenv("QUANT_PARQUET_DIR", str(tmp_path / "mnt" / "parquet"))
    monkeypatch.setenv("QUANT_META_DIR", str(tmp_path / "mnt" / "meta"))

    settings = load_settings(config_path)

    assert settings.host == "0.0.0.0"
    assert settings.port == 9000
    assert settings.raw_dir == (tmp_path / "mnt" / "raw").resolve()
    assert settings.parquet_dir == (tmp_path / "mnt" / "parquet").resolve()
    assert settings.meta_dir == (tmp_path / "mnt" / "meta").resolve()


def test_empty_env_falls_back_to_file(config_path, monkeypatch):
    monkeypatch.setenv("QUANT_RAW_DIR", "  ")

    assert load_settings(config_path).raw_dir == (PROJECT_ROOT / "data/raw").resolve()


def test_invalid_env_port_is_rejected(config_path, monkeypatch):
    monkeypatch.setenv("QUANT_PORT", "8000abc")

    with pytest.raises(ValueError, match="QUANT_PORT"):
        load_settings(config_path)


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


def test_startup_rejects_unwritable_data_dir(local_settings, tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("", encoding="utf-8")
    broken = replace(local_settings, raw_dir=blocker / "raw")

    with pytest.raises(RuntimeError, match="raw_dir"):
        create_app(broken)
