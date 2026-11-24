# -*- coding: utf-8 -*-
"""配置加载：启动时读取 TOML，解析为不可变的 Settings。

配置文件的优先级：
1. 环境变量 QUANT_CONFIG 指定的路径
2. 默认路径 quant/config/config.toml

数据目录之类的相对路径一律相对 quant 项目根解析，不受启动时工作目录影响。
"""
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# 本文件位于 quant/backend/app/config.py，向上三级即 quant 项目根
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.toml"
EXAMPLE_CONFIG_PATH = PROJECT_ROOT / "config" / "config.example.toml"

DEFAULT_CORS_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]


@dataclass(frozen=True)
class Settings:
    """全局配置。只读，加载后不再修改。

    quant 项目根由模块常量 PROJECT_ROOT 表示，不重复放进配置对象。
    """

    config_path: Path
    host: str
    port: int
    raw_dir: Path
    parquet_dir: Path
    meta_dir: Path
    timezone: str
    log_level: str
    cors_origins: list[str] = field(default_factory=list)


def resolve_config_path(explicit: Path | str | None = None) -> Path:
    """确定要读取的配置文件路径。"""
    if explicit is not None:
        return Path(explicit).expanduser().resolve()
    from_env = os.environ.get("QUANT_CONFIG")
    if from_env:
        return Path(from_env).expanduser().resolve()
    return DEFAULT_CONFIG_PATH


def load_settings(config_path: Path | str | None = None) -> Settings:
    """读取配置并校验。文件缺失或字段非法时直接报错，不做静默兜底。"""
    path = resolve_config_path(config_path)
    if not path.is_file():
        raise FileNotFoundError(
            f"配置文件不存在：{path}\n"
            f"请复制示例后修改：{EXAMPLE_CONFIG_PATH} -> {DEFAULT_CONFIG_PATH}\n"
            "或用环境变量 QUANT_CONFIG 指向其他配置文件。"
        )

    with path.open("rb") as fh:
        raw = tomllib.load(fh)

    server = raw.get("server") or {}
    data = raw.get("data") or {}
    app = raw.get("app") or {}

    port = int(server.get("port", 8000))
    if not 1 <= port <= 65535:
        raise ValueError(f"server.port 非法：{port}，应在 1-65535 之间")

    cors_origins = list(app.get("cors_origins") or DEFAULT_CORS_ORIGINS)
    if not cors_origins:
        raise ValueError("app.cors_origins 不能为空")
    if any("*" in origin for origin in cors_origins):
        raise ValueError("app.cors_origins 不允许包含通配符 '*'（服务无鉴权，只允许显式来源）")

    timezone = str(app.get("timezone", "Asia/Shanghai"))
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"app.timezone 非法：{timezone}") from exc

    return Settings(
        config_path=path,
        host=str(server.get("host", "127.0.0.1")),
        port=port,
        raw_dir=_resolve_dir(data.get("raw_dir", "data/raw")),
        parquet_dir=_resolve_dir(data.get("parquet_dir", "data/parquet")),
        # 用户数据与字典缓存（自选清单、股票名称），与可重建的 Parquet 分开
        meta_dir=_resolve_dir(data.get("meta_dir", "data/meta")),
        timezone=timezone,
        log_level=str(app.get("log_level", "INFO")).upper(),
        cors_origins=cors_origins,
    )


def _resolve_dir(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()
