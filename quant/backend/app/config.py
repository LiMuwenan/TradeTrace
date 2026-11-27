# -*- coding: utf-8 -*-
"""配置加载：启动时读取 TOML，解析为不可变的 Settings。

配置文件的优先级：
1. 环境变量 QUANT_CONFIG 指定的路径
2. 默认路径 quant/config/config.toml

字段取值的优先级：环境变量 > 配置文件 > 代码默认值。容器部署时挂载点、
监听端口随宿主机变化，用 QUANT_HOST / QUANT_PORT / QUANT_RAW_DIR /
QUANT_PARQUET_DIR / QUANT_META_DIR 覆盖，不必把宿主机路径写进镜像。

数据目录之类的相对路径一律相对 quant 项目根解析，不受启动时工作目录影响。
"""
import os
import re
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
    # 收盘后自动跑流水线；默认关，由 config.toml 的 [schedule] 显式打开，
    # 这样直接构造 Settings 的测试不会意外启动后台任务
    schedule_enabled: bool = False
    schedule_time: str = "15:30"

    @property
    def index_parquet_dir(self) -> Path:
        """指数日线的独立目录：与股票分开，列不同、分区方式也不同（见 IndexStore）。"""
        return self.parquet_dir / "index"


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
    schedule = raw.get("schedule") or {}

    port = _int_from_env("QUANT_PORT", server.get("port", 8000))
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

    schedule_time = str(schedule.get("time", "15:30"))
    _validate_clock(schedule_time)

    return Settings(
        config_path=path,
        host=_env("QUANT_HOST") or str(server.get("host", "127.0.0.1")),
        port=port,
        raw_dir=_resolve_dir(_env("QUANT_RAW_DIR") or data.get("raw_dir", "data/raw")),
        parquet_dir=_resolve_dir(
            _env("QUANT_PARQUET_DIR") or data.get("parquet_dir", "data/parquet")
        ),
        # 用户数据与字典缓存（自选清单、股票名称），与可重建的 Parquet 分开
        meta_dir=_resolve_dir(_env("QUANT_META_DIR") or data.get("meta_dir", "data/meta")),
        timezone=timezone,
        log_level=str(app.get("log_level", "INFO")).upper(),
        cors_origins=cors_origins,
        schedule_enabled=bool(schedule.get("enabled", False)),
        schedule_time=schedule_time,
    )


def _validate_clock(value: str) -> None:
    """`HH:MM`，24 小时制。格式写错就启动失败，不要静默退回默认时间。"""
    match = re.fullmatch(r"(\d{2}):(\d{2})", value)
    if match is None:
        raise ValueError(f"schedule.time 应为 HH:MM，当前为 {value!r}")
    hour, minute = int(match.group(1)), int(match.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"schedule.time 超出范围：{value}")


def _env(name: str) -> str | None:
    """读取非空环境变量。空串按未设置处理，避免 compose 里的空值把路径清空。"""
    value = os.environ.get(name)
    if value is None:
        return None
    return value.strip() or None


def _int_from_env(name: str, default: object) -> int:
    raw = _env(name)
    if raw is None:
        return int(default)
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} 应为整数，当前为 {raw!r}") from exc


def _resolve_dir(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()
