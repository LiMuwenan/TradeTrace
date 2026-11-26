# -*- coding: utf-8 -*-
"""规则求值接口：手动触发某交易日的求值，以及新规则的静默回放。

本票不做定时器——每日自动触发由 10 号票的调度负责（见 05 票备注）。
"""
from __future__ import annotations

from datetime import date as date_type

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.schemas import ok
from app.services import rule_eval
from app.storage import meta_db, rule_store
from app.storage.schema import IngestError, normalize_code

router = APIRouter(tags=["rules"])

CODE_FORMAT_MESSAGE = "标的代码格式应为 sh.600000 / sz.000001"


class EvaluateRequest(BaseModel):
    date: str
    code: str | None = None


@router.post("/rules/evaluate")
def evaluate(request: Request, payload: EvaluateRequest) -> dict:
    trade_date = _valid_date(payload.date, "date")
    summary = rule_eval.evaluate_day(
        request.app.state.settings,
        trade_date,
        code=payload.code,
        notifier=request.app.state.notifier,
    )
    return ok(summary)


@router.post("/rules/{rule_id}/replay")
def replay(request: Request, rule_id: int) -> dict:
    try:
        summary = rule_eval.replay_rule(request.app.state.settings, rule_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(summary)


@router.get("/rules/{rule_id}/history")
def rule_history(request: Request, rule_id: int, code: str) -> dict:
    """某标的某规则的触发历史：何时进入触发态、何时解除。"""
    settings = request.app.state.settings
    try:
        normalized = normalize_code(code)
    except IngestError as exc:
        raise HTTPException(status_code=400, detail=CODE_FORMAT_MESSAGE) from exc

    conn = meta_db.connect(settings.meta_dir, settings.timezone)
    try:
        rule = rule_store.get_rule(conn, rule_id)
        if rule is None:
            raise HTTPException(status_code=404, detail=f"规则不存在：{rule_id}")
        items = [
            {
                "tradeDate": row["trade_date"],
                "event": row["event"],
                "value": row["value"],
                "threshold": row["threshold"],
                "price": row["price"],
                "reason": row["reason"],
                "replayed": bool(row["replayed"]),
                "pushedAt": row["pushed_at"],
                "readAt": row["read_at"],
            }
            for row in rule_store.history(conn, rule_id, normalized)
        ]
        state = rule_store.current_state(conn, normalized, rule_id)
    finally:
        conn.close()

    return ok({"rule": rule.as_dict(), "code": normalized, "state": state, "items": items, "count": len(items)})


def _valid_date(value: str, field: str) -> str:
    try:
        return date_type.fromisoformat(value).isoformat()
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"{field} 应为 YYYY-MM-DD") from exc
