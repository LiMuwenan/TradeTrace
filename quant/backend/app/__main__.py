# -*- coding: utf-8 -*-
"""本地启动入口：python -m app

监听地址与端口取自配置文件，改配置重启即生效，不需要在命令行重复传参。
"""
import uvicorn

from app.config import load_settings
from app.factory import create_app


def main() -> None:
    settings = load_settings()
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
