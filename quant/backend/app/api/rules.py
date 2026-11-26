# -*- coding: utf-8 -*-
"""规则管理接口：定义增改与启停（06），以及求值触发与回放（05）。

写规则的入口只有本模块；求值本身不改变规则定义。
"""
from __future__ import annotations

from datetime import date as date_type

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.schemas import ok
from app.services import rule_eval
from app.services import rules as rules_service
from app.storage.meta_db import RuleValidationError
from app.storage.schema import IngestError

router = APIRouter(tags=["rules"])

CODE_FORMAT_MESSAGE = "标的代码格式应为 sh.600000 / sz.000001"


class EvaluateRequest(BaseModel):
    date: str
    code: str | None = None


class RuleCreate(BaseModel):
    type: str
    name: str
    scope: str = "watchlist"
    scopeCode: str | None = None
    window: int
    threshold: float | None = None


class RuleUpdate(BaseModel):
    name: str
    window: int
    threshold: float | None = None
    scope: str | None = None


class EnabledToggle(BaseModel):
    enabled: bool


@router.get("/rules")
def list_rules(request: Request) -> dict:
    return ok(rules_service.list_rules(request.app.state.settings))


@router.post("/rules", status_code=201)
def create_rule(request: Request, payload: RuleCreate) -> dict:
    try:
        data = rules_service.create_rule(
            request.app.state.settings,
            type=payload.type,
            name=payload.name,
            scope=payload.scope,
            scope_code=payload.scopeCode,
            window=payload.window,
            threshold=payload.threshold,
        )
    except RuleValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(data)


@router.put("/rules/{rule_id}")
def update_rule(request: Request, rule_id: int, payload: RuleUpdate) -> dict:
    try:
        rules_service.validate_scope_change(payload.scope)
        data = rules_service.update_rule(
            request.app.state.settings,
            rule_id,
            name=payload.name,
            window=payload.window,
            threshold=payload.threshold,
        )
    except RuleValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(data)


@router.post("/rules/{rule_id}/enabled")
def set_rule_enabled(request: Request, rule_id: int, payload: EnabledToggle) -> dict:
    try:
        data = rules_service.set_enabled(
            request.app.state.settings, rule_id, payload.enabled
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(data)


@router.post("/rules/evaluate")
def evaluate(request: Request, payload: EvaluateRequest) -> dict:
    trade_date = _valid_date(payload.date, "date")
    try:
        summary = rule_eval.evaluate_day(
            request.app.state.settings,
            trade_date,
            code=payload.code,
            notifier=request.app.state.notifier,
        )
    except IngestError as exc:
        raise HTTPException(status_code=400, detail=CODE_FORMAT_MESSAGE) from exc
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
    try:
        data = rule_eval.history_for(request.app.state.settings, rule_id, code)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IngestError as exc:
        raise HTTPException(status_code=400, detail=CODE_FORMAT_MESSAGE) from exc
    return ok(data)


def _valid_date(value: str, field: str) -> str:
    try:
        return date_type.fromisoformat(value).isoformat()
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"{field} 应为 YYYY-MM-DD") from exc
