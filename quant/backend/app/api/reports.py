# -*- coding: utf-8 -*-
"""日报接口（09）：生成并投递、按日期列表、单日详情。

自动生成由 10 号的收盘流水线触发；这里的端点用于手动补跑与 Web 回看。
"""
from __future__ import annotations

from datetime import date as date_type

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.schemas import ok
from app.services import report as report_service

router = APIRouter(tags=["reports"])


class GenerateRequest(BaseModel):
    date: str


@router.post("/reports/generate")
def generate_report(request: Request, payload: GenerateRequest) -> dict:
    trade_date = _valid_date(payload.date)
    data = report_service.generate(
        request.app.state.settings, trade_date, notifier=request.app.state.notifier
    )
    return ok(data)


@router.get("/reports")
def list_reports(
    request: Request,
    page: int = 1,
    pageSize: int = report_service.DEFAULT_PAGE_SIZE,
) -> dict:
    if page < 1:
        raise HTTPException(status_code=400, detail="page 从 1 开始")
    if not 1 <= pageSize <= report_service.MAX_PAGE_SIZE:
        raise HTTPException(
            status_code=400, detail=f"pageSize 应在 1-{report_service.MAX_PAGE_SIZE} 之间"
        )
    return ok(report_service.list_reports(request.app.state.settings, page=page, page_size=pageSize))


@router.get("/reports/{trade_date}")
def report_detail(request: Request, trade_date: str) -> dict:
    try:
        data = report_service.report_detail(
            request.app.state.settings, _valid_date(trade_date)
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(data)


def _valid_date(value: str) -> str:
    try:
        return date_type.fromisoformat(value).isoformat()
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="date 应为 YYYY-MM-DD") from exc
