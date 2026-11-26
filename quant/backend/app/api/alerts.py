# -*- coding: utf-8 -*-
"""预警阅读接口（07 号票）：列表、详情、已读切换、一键已读。

本模块只做参数校验与委派，查询与组装在 `app.services.alerts`。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.schemas import ok
from app.services import alerts as alerts_service
from app.storage.meta_db import RULE_TYPES
from app.storage.schema import IngestError

router = APIRouter(tags=["alerts"])

CODE_FORMAT_MESSAGE = "标的代码格式应为 sh.600000 / sz.000001"


class ReadToggle(BaseModel):
    read: bool


@router.get("/alerts")
def list_alerts(
    request: Request,
    read: str | None = None,
    code: str | None = None,
    ruleType: str | None = None,
    page: int = 1,
    pageSize: int = alerts_service.DEFAULT_PAGE_SIZE,
) -> dict:
    if page < 1:
        raise HTTPException(status_code=400, detail="page 从 1 开始")
    if not 1 <= pageSize <= alerts_service.MAX_PAGE_SIZE:
        raise HTTPException(
            status_code=400, detail=f"pageSize 应在 1-{alerts_service.MAX_PAGE_SIZE} 之间"
        )
    if ruleType and ruleType not in RULE_TYPES:
        raise HTTPException(
            status_code=400, detail=f"未知的规则类型：{ruleType}，可选 {'/'.join(RULE_TYPES)}"
        )
    try:
        data = alerts_service.list_alerts(
            request.app.state.settings,
            request.app.state.stock_names,
            read=_parse_read(read),
            code=code,
            rule_type=ruleType,
            page=page,
            page_size=pageSize,
        )
    except IngestError as exc:
        raise HTTPException(status_code=400, detail=CODE_FORMAT_MESSAGE) from exc
    return ok(data)


@router.get("/alerts/{alert_id}")
def alert_detail(request: Request, alert_id: int) -> dict:
    try:
        data = alerts_service.alert_detail(
            request.app.state.settings, request.app.state.stock_names, alert_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(data)


@router.patch("/alerts/{alert_id}/read")
def set_read(request: Request, alert_id: int, payload: ReadToggle) -> dict:
    try:
        data = alerts_service.set_read(request.app.state.settings, alert_id, payload.read)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(data)


@router.post("/alerts/read-all")
def read_all(request: Request) -> dict:
    return ok(alerts_service.mark_all_read(request.app.state.settings))


def _parse_read(value: str | None) -> bool | None:
    """查询串里的已读筛选：留空表示不筛选。"""
    if value is None or value == "":
        return None
    lowered = value.lower()
    if lowered in ("true", "1"):
        return True
    if lowered in ("false", "0"):
        return False
    raise HTTPException(status_code=400, detail="read 只能是 true 或 false")
