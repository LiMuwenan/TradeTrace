# -*- coding: utf-8 -*-
"""v1 行情接口：股票字典、日K、指数、数据新鲜度。契约见 docs/protocols。"""
import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..config import load_config
from ..database import get_db
from ..schemas import (DatasetsV1Out, IndexKlineOut, KlineV1Out, StockSearchOut,
                       StockSnapshotOut)
from ..services import market_service

router = APIRouter(prefix="/api/v1/market", tags=["market-v1"])


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@router.get("/stocks/snapshot", response_model=StockSnapshotOut)
def stocks_snapshot(db: Session = Depends(get_db)):
    return market_service.build_snapshot(db, _utc_now())


@router.get("/stocks", response_model=StockSearchOut)
def search(q: str = Query("", description="代码或名称关键词"), limit: int = Query(50),
           db: Session = Depends(get_db)):
    items = market_service.search_stocks(db, q, limit)
    return {"schemaVersion": 1, "count": len(items), "items": items}


@router.get("/stocks/{code}/kline", response_model=KlineV1Out)
def stock_kline(code: str,
                from_: str = Query("", alias="from"),
                to: str = Query("", alias="to")):
    cfg = load_config()
    return market_service.read_stock_kline(cfg, code, from_, to)


@router.get("/index/{code}/kline", response_model=IndexKlineOut)
def index_kline(code: str,
                from_: str = Query("", alias="from"),
                to: str = Query("", alias="to")):
    cfg = load_config()
    return market_service.read_index_kline(cfg, code, from_, to)


@router.get("/datasets", response_model=DatasetsV1Out)
def datasets(db: Session = Depends(get_db)):
    cfg = load_config()
    return market_service.build_datasets(db, cfg, _utc_now())
