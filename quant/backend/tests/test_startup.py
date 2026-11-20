# -*- coding: utf-8 -*-
"""启动入口：监听地址与端口必须来自配置，而不是命令行参数。"""
import app.__main__ as entry


def test_startup_uses_configured_host_and_port(config_path, monkeypatch):
    captured = {}

    def fake_run(application, **kwargs):
        captured.update(kwargs)
        captured["app"] = application

    monkeypatch.setenv("QUANT_CONFIG", str(config_path))
    monkeypatch.setattr(entry.uvicorn, "run", fake_run)

    entry.main()

    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8123
    assert captured["log_level"] == "info"
