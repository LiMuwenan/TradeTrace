# -*- coding: utf-8 -*-
"""自选与标的搜索接口。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.schemas import ok
from app.services import watchlist as watchlist_service
from app.storage.schema import IngestError

router = APIRouter(tags=["watchlist"])

CODE_FORMAT_MESSAGE = "标的代码格式应为 sh.600000 / sz.000001"


class WatchlistAdd(BaseModel):
    code: str


@router.get("/watchlist")
def get_watchlist(request: Request) -> dict:
    items = watchlist_service.list_watchlist(
        request.app.state.settings, request.app.state.stock_names
    )
    return ok({"items": items, "count": len(items)})


@router.post("/watchlist")
def post_watchlist(request: Request, payload: WatchlistAdd) -> dict:
    try:
        item, created = watchlist_service.add_to_watchlist(
            request.app.state.settings, request.app.state.stock_names, payload.code
        )
    except IngestError as exc:
        raise HTTPException(status_code=400, detail=CODE_FORMAT_MESSAGE) from exc
    return ok({"item": item, "created": created})


@router.delete("/watchlist/{code}")
def delete_watchlist(request: Request, code: str) -> dict:
    try:
        normalized, removed = watchlist_service.remove_from_watchlist(
            request.app.state.settings, code
        )
    except IngestError as exc:
        raise HTTPException(status_code=400, detail=CODE_FORMAT_MESSAGE) from exc
    return ok({"code": normalized, "removed": removed})
