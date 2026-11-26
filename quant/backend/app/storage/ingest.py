# -*- coding: utf-8 -*-
"""唯一的数据写入入口：`Ingestor.ingest_days` / `ingest_day`。

历史导入与每日增量走同一条代码路径，区别只在数据来源。写库之前完成：
- 代码归一与日期校验（在数据源里做）；
- 后复权因子按行前向填充；
- 官方因子异常（回退、单次增量过大）只记告警，不拒绝写入；
- 按年份合并、去重后原子替换。

因子口径（ADR 0005）：只使用数据源的 `backAdjustFactor`（以上市首日为基准的累计值），
不计算也不存储前复权。为了让「从历史中段开始导入」的序列也连续，每个标的第一次
见到官方因子时记一个基准 `scale`，落盘的 `back_factor = 官方后复权因子 / scale`。
官方值本身会因配股、缩股或数据源修正而下降或大幅跳变，因此不做「单调不减 /
单次增量」这类硬校验，只记录告警，避免个别异常数据卡住整段历史导入。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Iterable
from zoneinfo import ZoneInfo

import pandas as pd

from app.config import Settings
from app.storage.parquet_store import ParquetStore
from app.storage.schema import IngestError
from app.storage.sources import DaySnapshot, HistoricalCsvSource, MarketDataSource
from app.storage.store_state import StoreState, load_state, save_state

# 超过这个跨度就不再适用「单次除权」的增量判断（中间可能夹杂多次除权或长期停牌）
_RATIO_WINDOW_DAYS = 14

# 单次除权增量的常规区间，仅用于告警
_NORMAL_INCREMENT = (0.5, 3.0)

# 用 昨收 / preclose 还原除权比例时的合理区间，超出则退回官方累计值
_RATIO_RANGE = (0.1, 10.0)


@dataclass
class IngestReport:
    trade_dates: list[str]
    rows: int
    source: str
    ran_at: str
    status: str = "ok"
    replaced_rows: int = 0
    elapsed_ms: int = 0
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "tradeDates": self.trade_dates,
            "rows": self.rows,
            "replacedRows": self.replaced_rows,
            "source": self.source,
            "ranAt": self.ran_at,
            "elapsedMs": self.elapsed_ms,
            "status": self.status,
            "warnings": self.warnings,
        }


class Ingestor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.store = ParquetStore(settings.parquet_dir)
        self._timezone = ZoneInfo(settings.timezone)

    def ingest_day(self, trade_date: str, source: MarketDataSource) -> IngestReport:
        """单日增量。任何入库都必须经过这里。"""
        return self.ingest_days([trade_date], source)

    def ingest_days(self, trade_dates: Iterable[str], source: MarketDataSource) -> IngestReport:
        """按交易日批量入库；先全部校验，再按年份原子写入。"""
        dates = _normalize_dates(trade_dates)
        started = time.perf_counter()
        ran_at = datetime.now(self._timezone).isoformat(timespec="seconds")
        state = load_state(self.store.root)
        report = IngestReport(
            trade_dates=dates,
            rows=0,
            source=source.name,
            ran_at=ran_at,
        )

        try:
            frames, scales = self._build_frames(dates, source, state, report)
            merged = self.store.merge(pd.concat(frames, ignore_index=True))
            report.rows = merged.rows
            report.replaced_rows = merged.replaced
        except Exception as exc:
            report.status = "error"
            report.elapsed_ms = _elapsed_ms(started)
            report.warnings.append(str(exc))
            state.last_run = report.as_dict()
            save_state(self.store.root, state)
            raise

        report.warnings = _dedupe(report.warnings)
        report.elapsed_ms = _elapsed_ms(started)
        # 只有整批写入成功才持久化本批推导出的因子基准，避免污染历史
        state.scales = scales
        state.last_run = report.as_dict()
        save_state(self.store.root, state)
        return report

    def import_history(self, source: HistoricalCsvSource) -> list[IngestReport]:
        """整段历史按年分批导入；一年失败不影响其他年份。"""
        reports: list[IngestReport] = []
        by_year: dict[str, list[str]] = {}
        for trade_date in source.dates():
            by_year.setdefault(trade_date[:4], []).append(trade_date)
        for year in sorted(by_year):
            reports.append(self.ingest_days(by_year[year], source))
        return reports

    def _build_frames(
        self,
        dates: list[str],
        source: MarketDataSource,
        state: StoreState,
        report: IngestReport,
    ) -> tuple[list[pd.DataFrame], dict[str, float]]:
        previous = self.store.last_bars(before=dates[0])
        factors = {code: float(info["factor"]) for code, info in previous.items()}
        last_dates = {code: str(info["date"]) for code, info in previous.items()}
        last_closes = {
            code: float(info["close"])
            for code, info in previous.items()
            if info["close"] is not None and not pd.isna(info["close"])
        }
        # 拷贝一份：校验失败时不能把本次推导出的 scale 落进 store_state
        scales = dict(state.scales)

        frames: list[pd.DataFrame] = []
        for trade_date in dates:
            snapshot = source.load(trade_date)
            report.warnings.extend(snapshot.warnings)
            frames.append(
                self._apply_factors(
                    snapshot,
                    factors=factors,
                    last_dates=last_dates,
                    last_closes=last_closes,
                    scales=scales,
                    report=report,
                )
            )
        return frames, scales

    def _apply_factors(
        self,
        snapshot: DaySnapshot,
        *,
        factors: dict[str, float],
        last_dates: dict[str, str],
        last_closes: dict[str, float],
        scales: dict[str, float],
        report: IngestReport,
    ) -> pd.DataFrame:
        bars = snapshot.bars.copy()
        codes = bars["code"].tolist()
        closes = bars["close"].to_numpy(dtype="float64")
        back = bars["code"].map(factors).fillna(1.0).to_numpy(dtype="float64", copy=True)

        if snapshot.factor_events:
            positions = {code: index for index, code in enumerate(codes)}
            precloses = bars["preclose"].to_numpy(dtype="float64")
            tradable = bars["tradestatus"].to_numpy() != 0
            unverified: list[str] = []
            anomalies: list[str] = []
            for code, official in snapshot.factor_events.items():
                index = positions.get(code)
                if index is None:
                    continue  # 不是当日横截面中的标的（例如指数或 ETF），无处应用
                back[index] = self._factor_for_event(
                    code=code,
                    official=official,
                    previous_factor=factors.get(code),
                    previous_date=last_dates.get(code),
                    previous_close=last_closes.get(code),
                    preclose=precloses[index],
                    tradable=bool(tradable[index]),
                    trade_date=snapshot.trade_date,
                    scales=scales,
                    unverified=unverified,
                    anomalies=anomalies,
                )
            if unverified:
                preview = "、".join(unverified[:3]) + (" 等" if len(unverified) > 3 else "")
                report.warnings.append(
                    f"{snapshot.trade_date}：{len(unverified)} 个标的首次除权无法校验单次增量"
                    f"（与上一交易日相距过远或当日停牌），因子保持不变（{preview}）"
                )
            if anomalies:
                preview = "；".join(anomalies[:3]) + (" 等" if len(anomalies) > 3 else "")
                report.warnings.append(
                    f"{snapshot.trade_date}：{len(anomalies)} 个标的的官方后复权因子变化超出常规，"
                    f"已按官方值写入（{preview}）"
                )

        bars["back_factor"] = back
        factors.update(zip(codes, back.tolist()))
        # 停牌且全天无报价的行不带价格信息，不能当作「上一交易日」的基准
        for code, close in zip(codes, closes.tolist()):
            if pd.isna(close):
                continue
            last_dates[code] = snapshot.trade_date
            last_closes[code] = close
        return bars

    def _factor_for_event(
        self,
        *,
        code: str,
        official: float,
        previous_factor: float | None,
        previous_date: str | None,
        previous_close: float | None,
        preclose: float,
        tradable: bool,
        trade_date: str,
        scales: dict[str, float],
        unverified: list[str],
        anomalies: list[str],
    ) -> float:
        """把官方累计因子换算成行内因子；变化异常只记告警，不拒绝写入。"""
        if official <= 0:
            raise IngestError(f"{code} 在 {trade_date} 的后复权因子非法：{official}")

        scale = scales.get(code)
        if scale is not None:
            factor = official / scale
        elif (
            previous_factor is not None
            and tradable
            and self._gap_days(previous_date, trade_date) <= _RATIO_WINDOW_DAYS
        ):
            # 第一次见到该标的的官方因子：用相邻交易日的 昨收 / preclose 还原真实除权比例，
            # 让第一段历史的价格也连续
            ratio = _implied_ratio(previous_close, preclose)
            if ratio is None:
                scales[code] = official / previous_factor
                factor = previous_factor
                unverified.append(code)
            else:
                scales[code] = official / ratio
                factor = ratio
        elif previous_factor is not None:
            # 间隔过远或当日停牌（昨收 = preclose，无法还原增量）：保持原因子，等下一段连续数据再校
            scales[code] = official / previous_factor
            factor = previous_factor
            unverified.append(code)
        else:
            # 该标的第一次入库就带着除权事件，直接以官方值为基准
            scales[code] = official
            factor = 1.0

        if previous_factor is not None:
            if factor + 1e-9 < previous_factor:
                anomalies.append(f"{code} {trade_date} 回退 {previous_factor:.6f}→{factor:.6f}")
            elif self._gap_days(previous_date, trade_date) <= _RATIO_WINDOW_DAYS:
                increment = factor / previous_factor if previous_factor else factor
                if not _NORMAL_INCREMENT[0] <= increment <= _NORMAL_INCREMENT[1]:
                    anomalies.append(f"{code} {trade_date} 单次增量 {increment:.4f}")

        return factor

    @staticmethod
    def _gap_days(previous_date: str | None, trade_date: str) -> int:
        if not previous_date:
            return 0
        return (date.fromisoformat(trade_date) - date.fromisoformat(previous_date)).days


def _implied_ratio(previous_close: float | None, preclose: float) -> float | None:
    """用 昨收 / preclose 还原单次除权比例；数据缺失或明显不合理时返回 None。"""
    if previous_close is None or not preclose:
        return None
    ratio = previous_close / preclose
    return ratio if _RATIO_RANGE[0] <= ratio <= _RATIO_RANGE[1] else None


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _normalize_dates(trade_dates: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in trade_dates:
        text = str(value).strip()
        try:
            parsed = date.fromisoformat(text)
        except ValueError as exc:
            raise IngestError(f"交易日格式不正确：{value!r}（应为 YYYY-MM-DD）") from exc
        result.append(parsed.isoformat())
    if not result:
        raise IngestError("没有指定要导入的交易日")
    return sorted(set(result))


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
