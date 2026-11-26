# -*- coding: utf-8 -*-
"""日报：生成当日汇总快照并投递（09 号票）。

与逐条预警是两条独立路径：逐条负责「尽早知道」，日报负责「不漏」。因此日报读的是
「当日全部真实预警」，而不是「还没推送的那几条」——超限被跳过、推送失败的记录都要在
日报里出现，否则「没收到通知」就等于「没发生」。
"""
from __future__ import annotations

import json
import logging

from app.config import Settings
from app.services import rule_eval
from app.storage.meta_db import connect, now_iso
from app.storage.parquet_store import ParquetStore
from app.storage.report_store import (
    get as get_report,
    list_reports as list_report_rows,
    mark_pushed,
    save_draft,
)
from app.storage.rule_store import alerts_on, list_rules
from app.storage.stock_names import StockNameCache
from app.storage.watchlist_store import load_watchlist

logger = logging.getLogger(__name__)

DISCLAIMER = "本内容仅为数据分析，不构成投资建议"
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def generate(
    settings: Settings,
    trade_date: str,
    *,
    notifier=None,
    deliver: bool = True,
) -> dict:
    """生成并（可选）投递某交易日的日报。

    已投递的日报直接返回原文：重跑不能改掉用户已经在邮件里看过的内容。
    """
    conn = connect(settings.meta_dir, settings.timezone)
    try:
        existing = get_report(conn, trade_date)
    finally:
        conn.close()

    if existing is not None and existing["pushed_at"]:
        return {
            "report": json.loads(existing["content"]),
            "delivered": False,
            "kept": True,
            "reason": "该日日报已投递，保留原文",
        }

    content = build_content(settings, trade_date)
    conn = connect(settings.meta_dir, settings.timezone)
    try:
        save_draft(conn, trade_date, content, timezone=settings.timezone)
    finally:
        conn.close()

    if not deliver:
        return {"report": content, "delivered": False, "kept": False}

    sender = getattr(notifier, "send_report", None) if notifier is not None else None
    if sender is None or not getattr(notifier, "configured", False):
        return {
            "report": content,
            "delivered": False,
            "kept": False,
            "reason": "通知通道尚未配置",
        }

    try:
        outcome = sender(content)
    except Exception as exc:  # 投递异常不能把「日报已生成」变成失败
        logger.warning("日报投递失败：%s（%s）", trade_date, exc)
        return {"report": content, "delivered": False, "kept": False, "reason": str(exc)}

    if outcome.ok:
        conn = connect(settings.meta_dir, settings.timezone)
        try:
            mark_pushed(
                conn,
                trade_date,
                channel=outcome.channel or "unknown",
                timezone=settings.timezone,
            )
        finally:
            conn.close()

    return {
        "report": content,
        "delivered": outcome.ok,
        "kept": False,
        "channel": outcome.channel,
        "reason": outcome.error,
    }


def build_content(settings: Settings, trade_date: str) -> dict:
    """组装日报快照：触发清单、接近阈值清单、自选涨跌概览、数据日期。"""
    names = StockNameCache(settings.meta_dir).names()
    conn = connect(settings.meta_dir, settings.timezone)
    try:
        alerts = alerts_on(conn, trade_date)
        rules = list_rules(conn, enabled_only=True)
    finally:
        conn.close()

    watchlist_codes = [entry.code for entry in load_watchlist(settings.meta_dir)]
    # 指定单只的规则可能不在自选里，也算它的序列，否则「接近阈值」会漏
    scope_cache: dict[str, list[str]] = {}
    targets: list[str] = list(watchlist_codes)
    for rule in rules:
        for code in rule_eval.scope_codes(settings, rule, scope_cache):
            if code not in targets:
                targets.append(code)

    store = ParquetStore(settings.parquet_dir)
    series = {
        code: rule_eval.trading_bars(store.series(code, None, trade_date)) for code in targets
    }

    return {
        "tradeDate": trade_date,
        "dataDate": trade_date,
        "generatedAt": now_iso(settings.timezone),
        "triggers": [_alert_item(row, names) for row in alerts],
        "nearMisses": _near_misses(rules, series, watchlist_codes, trade_date, names),
        "watchlistSummary": _watchlist_summary(series, watchlist_codes, trade_date),
        "disclaimer": DISCLAIMER,
    }


def list_reports(settings: Settings, *, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE) -> dict:
    conn = connect(settings.meta_dir, settings.timezone)
    try:
        rows, total = list_report_rows(conn, page=page, page_size=page_size)
    finally:
        conn.close()

    items = []
    for row in rows:
        content = json.loads(row["content"])
        items.append(
            {
                "tradeDate": row["trade_date"],
                "triggerCount": len(content.get("triggers") or []),
                "nearMissCount": len(content.get("nearMisses") or []),
                "watchlistSummary": content.get("watchlistSummary") or {},
                "pushedAt": row["pushed_at"],
                "pushChannel": row["push_channel"],
                "generatedAt": content.get("generatedAt"),
            }
        )
    return {"items": items, "total": total, "page": page, "pageSize": page_size}


def report_detail(settings: Settings, trade_date: str) -> dict:
    conn = connect(settings.meta_dir, settings.timezone)
    try:
        row = get_report(conn, trade_date)
    finally:
        conn.close()
    if row is None:
        raise LookupError(f"该交易日没有日报：{trade_date}")
    return {
        "report": json.loads(row["content"]),
        "pushedAt": row["pushed_at"],
        "pushChannel": row["push_channel"],
        "disclaimer": DISCLAIMER,
    }


def _alert_item(row, names: dict[str, str]) -> dict:
    return {
        "id": int(row["id"]),
        "code": row["code"],
        "name": names.get(row["code"], ""),
        "ruleId": int(row["rule_id"]),
        "ruleType": row["rule_type"],
        "ruleName": row["rule_name"],
        "value": row["value"],
        "threshold": row["threshold"],
        "price": row["price"],
        "window": row["rule_window"],
    }


def _near_misses(
    rules,
    series: dict[str, list[dict]],
    watchlist_codes: list[str],
    trade_date: str,
    names: dict[str, str],
) -> list[dict]:
    """接近阈值但未触发。口径复用 05 的 `is_near`，不在日报里另立一套。"""
    items: list[dict] = []
    for rule in rules:
        targets = [rule.scope_code] if rule.scope == "single" else watchlist_codes
        for code in targets:
            if not code:
                continue
            bars = series.get(code)
            if not bars or bars[-1]["date"] != trade_date:
                continue
            signal = rule_eval.signal_at(rule, bars, len(bars) - 1)
            if not rule_eval.is_near(rule, signal):
                continue
            items.append(
                {
                    "code": code,
                    "name": names.get(code, ""),
                    "ruleId": rule.id,
                    "ruleType": rule.type,
                    "ruleName": rule.name,
                    "value": signal.value,
                    "threshold": signal.threshold,
                    "price": signal.price,
                    "window": rule.window,
                }
            )
    return items


def _watchlist_summary(
    series: dict[str, list[dict]], codes: list[str], trade_date: str
) -> dict:
    up = down = flat = missing = 0
    for code in codes:
        bars = series.get(code) or []
        if not bars or bars[-1]["date"] != trade_date:
            missing += 1
            continue
        change = bars[-1].get("pctChg")
        if change is None or float(change) == 0:
            flat += 1
        elif float(change) > 0:
            up += 1
        else:
            down += 1
    return {
        "total": len(codes),
        "up": up,
        "down": down,
        "flat": flat,
        # 当日无数据（停牌或尚未入库），不等于下跌
        "suspended": missing,
    }
