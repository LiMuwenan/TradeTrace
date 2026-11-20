# -*- coding: utf-8 -*-
"""共享测试夹具：所有用例用同一份最小配置，避免各文件各写一份 TOML。"""
import pytest

from app.config import Settings, load_settings

MINIMAL_CONFIG = """
[server]
host = "127.0.0.1"
port = 8123

[data]
raw_dir = "data/raw"
parquet_dir = "data/parquet"

[app]
timezone = "Asia/Shanghai"
cors_origins = ["http://localhost:5173"]
"""


@pytest.fixture
def config_path(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(MINIMAL_CONFIG, encoding="utf-8")
    return path


@pytest.fixture
def settings(config_path) -> Settings:
    return load_settings(config_path)


@pytest.fixture
def local_settings(tmp_path) -> Settings:
    """数据目录全部指向 tmp，避免测试写进项目的 quant/data。"""
    return Settings(
        config_path=tmp_path / "config.toml",
        host="127.0.0.1",
        port=8000,
        raw_dir=tmp_path / "raw",
        parquet_dir=tmp_path / "parquet",
        timezone="Asia/Shanghai",
        log_level="INFO",
        cors_origins=["http://localhost:5173"],
    )
