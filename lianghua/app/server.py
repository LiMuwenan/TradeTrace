# -*- coding: utf-8 -*-
"""按配置启动 uvicorn：默认仅监听本机，局域网模式需显式配置 server.bind_host。

启动：python -m app.server
"""
import uvicorn

from .config import load_config


def main() -> None:
    cfg = load_config()
    uvicorn.run("app.main:app", host=cfg.bind_host, port=cfg.port, reload=False)


if __name__ == "__main__":
    main()
