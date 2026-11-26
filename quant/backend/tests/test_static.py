# -*- coding: utf-8 -*-
"""前端托管：有 dist 时首页与前端路由回退到 index.html，接口 404 不被页面吞掉。"""
from fastapi.testclient import TestClient

from app import factory
from app.factory import create_app


def _make_dist(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><div id=app></div>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    return dist


def test_serves_index_and_assets(settings, tmp_path, monkeypatch):
    monkeypatch.setattr(factory, "WEB_DIST", _make_dist(tmp_path))
    client = TestClient(create_app(settings))

    assert "<div id=app>" in client.get("/").text
    assert client.get("/assets/app.js").text == "console.log(1)"


def test_frontend_routes_fall_back_to_index(settings, tmp_path, monkeypatch):
    monkeypatch.setattr(factory, "WEB_DIST", _make_dist(tmp_path))
    client = TestClient(create_app(settings))

    assert "<div id=app>" in client.get("/alerts/12").text
    assert "<div id=app>" in client.get("/stocks/sh.600519").text


def test_api_404_keeps_json_envelope(settings, tmp_path, monkeypatch):
    monkeypatch.setattr(factory, "WEB_DIST", _make_dist(tmp_path))
    client = TestClient(create_app(settings))

    response = client.get("/api/v1/nope")

    assert response.status_code == 404
    assert response.json()["code"] == 404


def test_no_dist_keeps_api_only(settings):
    client = TestClient(create_app(settings))

    assert client.get("/dashboard").status_code == 404
