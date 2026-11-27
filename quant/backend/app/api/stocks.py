# -*- coding: utf-8 -*-
"""标的接口：搜索与个股详情（04）。

`/stocks/search` 原在自选路由里，随本票一并归到标的域，避免同一前缀分散在两个模块。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.schemas import ok
from app.services import index_quotes
from app.services import stock_detail as detail_service
from app.services import watchlist as watchlist_service
from app.storage.index_catalog import is_index_code
from app.storage.schema import IngestError

router = APIRouter(tags=["stocks"])

CODE_FORMAT_MESSAGE = "标的代码格式应为 sh.600000 / sz.000001"


@router.get("/stocks/search")
def stock_search(request: Request, q: str = "", limit: int = 50) -> dict:
    items, names_available = watchlist_service.search_stocks(
        request.app.state.settings, request.app.state.stock_names, q, limit
    )
    return ok({"items": items, "count": len(items), "namesAvailable": names_available})


@router.get("/stocks/{code}/detail")
def stock_detail(
    request: Request,
    code: str,
    range: str = detail_service.DEFAULT_RANGE,
    adjust: str = detail_service.DEFAULT_ADJUST,
) -> dict:
    try:
        data = detail_service.detail(
            request.app.state.settings, request.app.state.stock_names, code, range, adjust
        )
    except IngestError as exc:
        raise HTTPException(status_code=400, detail=CODE_FORMAT_MESSAGE) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(data)


@router.post("/stocks/{code}/history", status_code=202)
def start_index_history(request: Request, code: str) -> dict:
    """在后台补齐某只指数的历史（加入自选时自动触发，失败后可从这里重试）。

    只对指数开放：股票的行情由全市场日 K 一次入库，没有「按标的补历史」这回事。
    """
    settings = request.app.state.settings
    if not is_index_code(settings.meta_dir, code):
        raise HTTPException(status_code=404, detail=f"{code} 不是已知的指数")
    try:
        state = index_quotes.start_backfill(settings, code, request.app.state.index_fetcher)
    except IngestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(state)
