# -*- coding: utf-8 -*-
"""收盘流水线接口（10）：运行记录与手动重跑。

定时触发在进程内（`app/services/scheduler.py`），这里只负责「看一眼跑了什么」和「现在重跑一次」。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.schemas import ok
from app.services import pipeline as pipeline_service

router = APIRouter(tags=["pipeline"])

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class RunRequest(BaseModel):
    date: str
    catchUp: bool = False


@router.get("/pipeline/runs")
def list_runs(
    request: Request,
    page: int = 1,
    pageSize: int = DEFAULT_PAGE_SIZE,
    date: str | None = None,
) -> dict:
    if page < 1:
        raise HTTPException(status_code=400, detail="page 从 1 开始")
    if not 1 <= pageSize <= MAX_PAGE_SIZE:
        raise HTTPException(status_code=400, detail=f"pageSize 应在 1-{MAX_PAGE_SIZE} 之间")
    return ok(
        pipeline_service.list_runs(
            request.app.state.settings, page=page, page_size=pageSize, trade_date=date
        )
    )


@router.post("/pipeline/run")
def run_now(request: Request, payload: RunRequest) -> dict:
    settings = request.app.state.settings
    try:
        if payload.catchUp:
            runs = pipeline_service.catch_up(
                settings, payload.date, notifier=request.app.state.notifier
            )
            return ok({"runs": runs, "count": len(runs)})
        record = pipeline_service.run(
            settings,
            payload.date,
            notifier=request.app.state.notifier,
            trigger="manual",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok({"run": record})
