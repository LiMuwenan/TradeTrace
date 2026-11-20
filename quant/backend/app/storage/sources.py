# -*- coding: utf-8 -*-
"""两种行情数据来源：历史按日 CSV 目录、每日实时接口。

两者产出同一种中间结构 `DaySnapshot`：当日全市场日 K + 当日除权清单。
实时来源在抓取后按历史目录的格式额外归档一份原始 CSV。
"""
from __future__ import annotations

import bisect
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Protocol

import pandas as pd

from app.storage.schema import (
    DAILY_COLUMNS,
    FACTOR_COLUMNS,
    IngestError,
    normalize_code,
)

_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})$")

# 错误消息里最多列出几个标的，避免刷屏
_MAX_LISTED_CODES = 5


@dataclass(frozen=True)
class DaySnapshot:
    """某一交易日的中间结构，所有来源统一产出它。"""

    trade_date: str
    bars: pd.DataFrame
    factor_events: dict[str, float]
    warnings: list[str] = field(default_factory=list)


class MarketDataSource(Protocol):
    name: str

    def load(self, trade_date: str) -> DaySnapshot:
        """取某一交易日的数据；取不到时抛 IngestError。"""


def read_daily_csv(path: Path, trade_date: str) -> pd.DataFrame:
    """读取一份按日横截面 CSV，返回规范化的 18 列。"""
    frame = pd.read_csv(path, dtype={"code": str}, encoding="utf-8-sig")
    return normalize_daily_frame(frame, source=path.name, trade_date=trade_date)


def normalize_daily_frame(frame: pd.DataFrame, *, source: str, trade_date: str) -> pd.DataFrame:
    """校验并规范化日 K（CSV 与实时接口共用），避免两份校验逻辑漂移。"""
    missing = [column for column in DAILY_COLUMNS if column not in frame.columns]
    if missing:
        raise IngestError(f"{source} 缺少列：{', '.join(missing)}")

    frame = frame[DAILY_COLUMNS].copy()
    frame["code"] = frame["code"].map(normalize_code)
    frame["date"] = frame["date"].astype(str).str.strip()

    if (frame["date"] != trade_date).any():
        other = sorted(set(frame["date"]) - {trade_date})[:3]
        raise IngestError(f"{source} 的日期与目标交易日 {trade_date} 不一致：{other}")

    duplicated = frame.loc[frame["code"].duplicated(), "code"].unique().tolist()
    if duplicated:
        raise IngestError(f"{source} 存在重复标的：{', '.join(duplicated[:_MAX_LISTED_CODES])}")

    for column in ("open", "high", "low", "close", "preclose", "tradestatus"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if frame[column].isna().any():
            raise IngestError(f"{source} 的 {column} 存在空值或非数字")

    for column in ("volume", "amount", "turn", "pctChg", "peTTM", "pbMRQ", "psTTM", "pcfNcfTTM"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    for column in ("adjustflag", "tradestatus", "isST"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0).astype("int64")

    return frame.reset_index(drop=True)


def read_factor_csv(path: Path) -> pd.DataFrame:
    """读取一份当日除权清单，返回 code / dividOperateDate / backAdjustFactor。"""
    frame = pd.read_csv(path, dtype={"code": str}, encoding="utf-8-sig")
    return normalize_factor_frame(frame, source=path.name)


def normalize_factor_frame(frame: pd.DataFrame, *, source: str) -> pd.DataFrame:
    missing = [column for column in FACTOR_COLUMNS if column not in frame.columns]
    if missing:
        raise IngestError(f"{source} 缺少列：{', '.join(missing)}")

    result = pd.DataFrame(
        {
            "code": frame["code"].map(normalize_code),
            "dividOperateDate": pd.to_datetime(frame["dividOperateDate"], errors="coerce"),
            "backAdjustFactor": pd.to_numeric(frame["backAdjustFactor"], errors="coerce"),
        }
    )
    if result["dividOperateDate"].isna().any() or result["backAdjustFactor"].isna().any():
        raise IngestError(f"{source} 的除权日期或后复权因子存在空值")
    result["dividOperateDate"] = result["dividOperateDate"].dt.strftime("%Y-%m-%d")
    return result


def _events_from_frame(frame: pd.DataFrame) -> dict[str, float]:
    return {code: float(factor) for code, _, factor in frame.itertuples(index=False)}


def _filename_date(path: Path) -> str | None:
    match = _DATE_RE.match(path.stem)
    return match.group(1) if match else None


class HistoricalCsvSource:
    """历史按日横截面 CSV 目录。

    目录约定：`<root>/daily/YYYY-MM-DD.csv` 与 `<root>/factors/YYYY-MM-DD.csv`；
    没有 `daily/` 子目录时把 `<root>/*.csv` 当日 K。除权文件按 `dividOperateDate`
    对齐到“当天或之后的第一个交易日”，因此某天漏了日 K 也不会丢掉除权事件。
    """

    name = "csv"

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        daily_dir = self.root / "daily"
        if not daily_dir.is_dir():
            daily_dir = self.root
        if not daily_dir.is_dir():
            raise IngestError(f"历史数据目录不存在：{self.root}")

        self._daily_files: dict[str, Path] = {}
        for path in sorted(daily_dir.glob("*.csv")):
            trade_date = _filename_date(path)
            if trade_date:
                self._daily_files[trade_date] = path
        if not self._daily_files:
            raise IngestError(f"历史数据目录中没有 YYYY-MM-DD.csv 文件：{daily_dir}")

        self._dates = sorted(self._daily_files)
        self._events_by_date = self._load_factor_events(self.root / "factors")

    def dates(self) -> list[str]:
        return list(self._dates)

    def _load_factor_events(self, factor_dir: Path) -> dict[str, dict[str, float]]:
        if not factor_dir.is_dir():
            return {}

        frames = [read_factor_csv(path) for path in sorted(factor_dir.glob("*.csv"))]
        if not frames:
            return {}

        events = pd.concat(frames, ignore_index=True)
        events = events.sort_values("dividOperateDate", kind="mergesort")
        grouped: dict[str, dict[str, tuple[str, float]]] = {}
        for code, event_date, factor in events.itertuples(index=False):
            index = bisect.bisect_left(self._dates, event_date)
            if index >= len(self._dates):
                continue  # 除权日之后没有任何日 K，暂时无处应用
            target = self._dates[index]
            current = grouped.setdefault(target, {}).get(code)
            # 同一天有多个除权事件时保留最新的官方值
            if current is None or event_date >= current[0]:
                grouped[target][code] = (event_date, float(factor))
        return {key: {code: value[1] for code, value in items.items()} for key, items in grouped.items()}

    def load(self, trade_date: str) -> DaySnapshot:
        path = self._daily_files.get(trade_date)
        if path is None:
            raise IngestError(f"历史数据中没有交易日 {trade_date} 的日 K 文件")
        return DaySnapshot(
            trade_date=trade_date,
            bars=read_daily_csv(path, trade_date),
            factor_events=dict(self._events_by_date.get(trade_date, {})),
        )


class DailyFetcher(Protocol):
    """实时取数的最小接口；测试用假实现替换，不访问网络。"""

    def fetch_daily(self, trade_date: str) -> pd.DataFrame:
        ...

    def fetch_factors(self, trade_date: str) -> pd.DataFrame:
        ...


class RealtimeSource:
    """每日实时接口：抓取当日全市场日 K 与当日除权清单，并归档原始 CSV。"""

    name = "realtime"

    def __init__(self, fetcher: DailyFetcher, raw_dir: Path | str) -> None:
        self.fetcher = fetcher
        self.raw_dir = Path(raw_dir)

    def load(self, trade_date: str) -> DaySnapshot:
        daily = self.fetcher.fetch_daily(trade_date)
        factors = self.fetcher.fetch_factors(trade_date)
        if daily.empty:
            raise IngestError(f"{trade_date} 没有取到日 K 数据（非交易日或接口失败）")

        daily_dir = self.raw_dir / "daily"
        factor_dir = self.raw_dir / "factors"
        daily_dir.mkdir(parents=True, exist_ok=True)

        warnings: list[str] = []
        daily_path = daily_dir / f"{trade_date}.csv"
        if daily_path.exists():
            # 原始 CSV 是不可变事实源，已归档就不覆盖、也不再信任本次抓取
            warnings.append(f"原始日 K 已归档，本次沿用归档文件：{daily_path}")
            bars = read_daily_csv(daily_path, trade_date)
        else:
            # 先校验再归档，避免把坏数据固化成“事实源”
            bars = normalize_daily_frame(daily, source="实时日 K", trade_date=trade_date)
            daily[DAILY_COLUMNS].to_csv(daily_path, index=False, encoding="utf-8-sig")

        events: dict[str, float] = {}
        if not factors.empty:
            factor_dir.mkdir(parents=True, exist_ok=True)
            factor_path = factor_dir / f"{trade_date}.csv"
            if factor_path.exists():
                events = _events_from_frame(read_factor_csv(factor_path))
            else:
                normalized = normalize_factor_frame(factors, source="实时除权清单")
                factors[FACTOR_COLUMNS].to_csv(factor_path, index=False, encoding="utf-8-sig")
                events = _events_from_frame(normalized)

        return DaySnapshot(
            trade_date=trade_date,
            bars=bars,
            factor_events=events,
            warnings=warnings,
        )


class BaostockFetcher:
    """baostock 的按日批量接口实现；每次取数独立登录，避免长连接失效。"""

    def __init__(self) -> None:
        try:
            import baostock  # noqa: F401
        except ImportError as exc:  # pragma: no cover - 依赖缺失时的可操作提示
            raise IngestError("未安装 baostock，无法使用实时取数；请先 pip install baostock") from exc

    def fetch_daily(self, trade_date: str) -> pd.DataFrame:
        import baostock as bs

        return self._query(bs, "query_daily_history_k_AStock", trade_date)

    def fetch_factors(self, trade_date: str) -> pd.DataFrame:
        import baostock as bs

        return self._query(bs, "query_daily_adjust_factor", trade_date)

    @staticmethod
    def _query(module, name: str, trade_date: str) -> pd.DataFrame:
        login = module.login()
        if login.error_code != "0":
            raise IngestError(f"baostock 登录失败：{login.error_msg}")
        try:
            result = getattr(module, name)(date=trade_date)
            if result.error_code != "0":
                raise IngestError(f"baostock {name} 失败：{result.error_msg}")
            rows = result.get_data()
            return pd.DataFrame(rows, columns=result.fields)
        finally:
            module.logout()
