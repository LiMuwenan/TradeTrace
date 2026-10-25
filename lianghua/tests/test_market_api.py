# -*- coding: utf-8 -*-
"""v1 行情接口：结构、错误码、空数据。"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import v1
from app.errors import ApiError, api_error_handler


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
