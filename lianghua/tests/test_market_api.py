# -*- coding: utf-8 -*-
"""v1 行情接口：结构、错误码、空数据。"""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import market
from app.api import v1
from app.database import Base, get_db
from app.errors import ApiError, api_error_handler
from app.models import Stock


def _client() -> TestClient:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)
    app.include_router(v1.router)
    return TestClient(app)


def test_health_v1_shape():
    r = _client().get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["schemaVersion"] == 1
    assert body["status"] == "ok"
    assert body["serverTime"].endswith("Z")


def _market_client(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path}/meta.db",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    DB = sessionmaker(bind=engine)
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)
    app.include_router(market.router)

    def _dep():
        db = DB()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _dep
    return TestClient(app), DB


def test_snapshot_returns_rows(tmp_path, monkeypatch):
    client, DB = _market_client(tmp_path, monkeypatch)
    with DB() as db:
        db.add(Stock(code="sh600519", name="贵州茅台", industry="白酒"))
        db.commit()
    body = client.get("/api/v1/market/stocks/snapshot").json()
    assert body["schemaVersion"] == 1
    assert body["count"] == 1
    assert body["stocks"][0]["code"] == "600519"
    assert body["stocks"][0]["market"] == "SH"


def test_index_without_market_prefix_is_400(tmp_path, monkeypatch):
    class Cfg:
        index_dir = tmp_path
        data_dir = tmp_path
    monkeypatch.setattr(market, "load_config", lambda: Cfg())
    client = _market_client(tmp_path, monkeypatch)[0]
    r = client.get("/api/v1/market/index/000300/kline")
    assert r.status_code == 400
    body = r.json()
    assert body["code"] == "BAD_REQUEST"
    assert "Traceback" not in body["message"] and "d:" not in body["message"].lower()


def test_bad_range_is_422(tmp_path, monkeypatch):
    class Cfg:
        index_dir = tmp_path
        data_dir = tmp_path
    monkeypatch.setattr(market, "load_config", lambda: Cfg())
    client = _market_client(tmp_path, monkeypatch)[0]
    r = client.get("/api/v1/market/stocks/600519/kline?from=2026-10-25&to=2026-10-01")
    assert r.status_code == 422
    assert r.json()["code"] == "VALIDATION_ERROR"
