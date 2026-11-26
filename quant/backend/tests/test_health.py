# -*- coding: utf-8 -*-
"""健康检查：确认服务可启动、配置已生效、响应结构统一。"""
from fastapi.testclient import TestClient

from app import __version__
from app.factory import create_app


def _health(client: TestClient) -> dict:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    return response.json()


def test_health_uses_unified_envelope(settings):
    body = _health(TestClient(create_app(settings)))

    assert body["code"] == 0
    assert body["message"] == "ok"
    assert set(body["data"]) >= {"status", "version", "timezone", "serverTime", "parquetDir", "rawDir"}


def test_health_reports_version_and_dirs(settings):
    data = _health(TestClient(create_app(settings)))["data"]

    assert data["status"] == "ok"
    assert data["version"] == __version__
    assert data["timezone"] == "Asia/Shanghai"
    assert data["parquetDir"].endswith("parquet")
    assert data["rawDir"].endswith("raw")
    assert data["metaDir"].endswith("meta")
    assert data["serverTime"]


def test_health_fields_are_camel_case(settings):
    data = _health(TestClient(create_app(settings)))["data"]

    assert not [key for key in data if "_" in key]


def test_cors_allows_configured_origin_only(settings):
    client = TestClient(create_app(settings))

    allowed = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
    denied = client.get("/api/v1/health", headers={"Origin": "http://evil.example"})

    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in denied.headers


def test_unknown_route_returns_unified_error_body(settings):
    response = TestClient(create_app(settings)).get("/api/v1/nope")

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == 404
    assert body["message"]
    assert "detail" not in body
