# -*- coding: utf-8 -*-
"""行情服务（v1）：代码归一化、股票快照/搜索、日K、指数、数据集。

只读：SQLite 取股票元数据，Parquet 取价量；不写库、不抓数据。
"""
import datetime

from sqlalchemy.orm import Session

from ..errors import ApiError
from ..models import Dataset, Stock
from . import index_store, parquet_reader

# 指数名称表：与 config 的 report.index_codes 对应；未知代码返回空名
INDEX_NAMES = {
    "sh000001": "上证指数",
    "sz399001": "深证成指",
    "sz399006": "创业板指",
    "sh000688": "科创50",
    "sh000016": "上证50",
    "sh000300": "沪深300",
    "sh000905": "中证500",
    "sh000852": "中证1000",
}

MAX_RANGE_DAYS = 3650


def _market_of(digits: str) -> str:
    """按首位数字判定市场：6/9→SH，0/1/2/3→SZ，4/8→BJ，其余无法识别。"""
    head = digits[0]
    if head in "69":
        return "SH"
    if head in "0123":
        return "SZ"
    if head in "48":
        return "BJ"
    raise ValueError(f"无法识别的证券代码: {digits}")


def normalize_code(raw: str) -> tuple[str, str]:
    """归一化为 (market, 6位数字)。接受 sh600519 / sh.600519 / 600519。"""
    c = str(raw or "").strip().lower().replace(" ", "")
    market = ""
    for prefix in ("sh", "sz", "bj"):
        if c.startswith(prefix):
            market = prefix.upper()
            c = c[len(prefix):].lstrip(".")
            break
    else:
        c = c.lstrip(".")
    if len(c) != 6 or not c.isdigit():
        raise ValueError(f"证券代码应为 6 位数字，收到: {raw}")
    market = market or _market_of(c)
    return market, c


def normalize_index_code(raw: str) -> tuple[str, str]:
    """指数代码必须带市场前缀；返回 (market, 带前缀代码)。"""
    c = str(raw or "").strip().lower().replace(" ", "")
    if not (c.startswith("sh") or c.startswith("sz")) or c.startswith("sh.") or c.startswith("sz."):
        raise ValueError(f"指数代码必须带市场前缀（如 sh000300），收到: {raw}")
    digits = c[2:]
    if len(digits) != 6 or not digits.isdigit():
        raise ValueError(f"指数代码应为 6 位数字，收到: {raw}")
    return c[:2].upper(), c


def validate_range(from_date: str, to_date: str) -> None:
    """区间校验：格式合法、from<=to、跨度不超过 MAX_RANGE_DAYS。"""
    for value in (from_date, to_date):
        if not value:
            continue
        try:
            datetime.date.fromisoformat(value)
        except ValueError:
            raise ApiError(400, "BAD_REQUEST", f"日期格式应为 YYYY-MM-DD，收到: {value}")
    if from_date and to_date:
        if from_date > to_date:
            raise ApiError(422, "VALIDATION_ERROR", "起始日期不能晚于结束日期")
        span = (datetime.date.fromisoformat(to_date) - datetime.date.fromisoformat(from_date)).days
        if span > MAX_RANGE_DAYS:
            raise ApiError(422, "RANGE_TOO_LARGE", f"查询区间超过 {MAX_RANGE_DAYS} 天，请缩小范围")


def build_snapshot(db: Session, generated_at: str) -> dict:
    """全量股票字典快照：跳过无法识别的代码，count 与内容严格一致。"""
    stocks = []
    for row in db.query(Stock).order_by(Stock.code).all():
        try:
            market, code = normalize_code(row.code)
        except ValueError:
            continue
        stocks.append({
            "code": code,
            "name": row.name or "",
            "market": market,
            "industry": row.industry or "",
        })
    stocks.sort(key=lambda item: item["code"])
    return {"schemaVersion": 1, "generatedAt": generated_at, "count": len(stocks), "stocks": stocks}


def search_stocks(db: Session, q: str, limit: int = 50) -> list[dict]:
    """按代码/名称子串搜索；q 为空返回空列表（不返回全表）。"""
    kw = str(q or "").strip()
    if not kw:
        return []
    limit = max(1, min(int(limit), 200))
    like = f"%{kw}%"
    rows = (db.query(Stock)
            .filter((Stock.code.like(like)) | (Stock.name.like(like)))
            .order_by(Stock.code)
            .limit(limit)
            .all())
    out = []
    for row in rows:
        try:
            market, code = normalize_code(row.code)
        except ValueError:
            continue
        out.append({"code": code, "name": row.name or "", "market": market,
                    "industry": row.industry or ""})
    return out


def _empty_series() -> dict:
    """一组空价量序列：文件缺失/区间无数据时返回六个空数组（契约要求）。"""
    return {"dates": [], "open": [], "high": [], "low": [], "close": [], "volume": []}


def _ensure_series(series: dict | None) -> dict:
    """补齐 parquet_reader 缺省返回的空 dict，保证结构固定。"""
    out = _empty_series()
    if series:
        out.update({key: series[key] for key in out if key in series})
    return out


def read_stock_kline(cfg, code_raw: str, from_date: str, to_date: str) -> dict:
    """个股区间日K：三组序列；文件缺失/区间为空返回空数组。"""
    validate_range(from_date, to_date)
    try:
        market, code = normalize_code(code_raw)
    except ValueError as exc:
        raise ApiError(400, "BAD_REQUEST", str(exc))
    data = parquet_reader.read_kline(cfg.data_dir, f"{market.lower()}{code}", from_date, to_date)
    return {"schemaVersion": 1, "code": code, "market": market,
            "raw": _ensure_series(data.get("raw")),
            "qfq": _ensure_series(data.get("qfq")),
            "hfq": _ensure_series(data.get("hfq"))}


def _series_from_df(df) -> dict:
    """指数 DataFrame → 六个数组（只取存在的列）。"""
    def col(name):
        return df[name].tolist() if name in df.columns else []
    return {
        "dates": col("date"),
        "open": col("open"),
        "high": col("high"),
        "low": col("low"),
        "close": col("close"),
        "volume": col("volume"),
    }


def read_index_kline(cfg, code_raw: str, from_date: str, to_date: str) -> dict:
    """指数区间日K：单组序列，无复权。"""
    validate_range(from_date, to_date)
    try:
        market, code = normalize_index_code(code_raw)
    except ValueError as exc:
        raise ApiError(400, "BAD_REQUEST", str(exc))
    df = index_store.read_index(cfg.index_dir, code)
    if df is None or df.empty:
        return {"schemaVersion": 1, "code": code, "name": INDEX_NAMES.get(code, ""),
                "market": market, **_empty_series()}
    df = df.copy()
    df["date"] = df["date"].astype(str)
    if from_date:
        df = df[df["date"] >= from_date]
    if to_date:
        df = df[df["date"] <= to_date]
    df = df.sort_values("date")
    series = _series_from_df(df)
    return {"schemaVersion": 1, "code": code, "name": INDEX_NAMES.get(code, ""),
            "market": market, **series}


def build_datasets(db: Session, cfg, generated_at: str) -> dict:
    """数据新鲜度：先扫描真实文件，再按库内记录组装。"""
    from . import dataset_scan
    dataset_scan.scan_all(cfg, db)
    items = []
    for row in db.query(Dataset).order_by(Dataset.id).all():
        items.append({
            "name": row.name,
            "type": row.type or "",
            "latestDataDate": row.latest_data_date or "",
            "lagDays": row.lag_days,
            "fileCount": row.file_count or 0,
        })
    return {"schemaVersion": 1, "generatedAt": generated_at, "items": items}
