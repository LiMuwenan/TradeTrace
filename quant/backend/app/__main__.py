# -*- coding: utf-8 -*-
"""本地启动入口：python -m app

监听地址与端口取自配置文件，改配置重启即生效，不需要在命令行重复传参。
"""
import uvicorn

from app.config import load_settings
from app.factory import create_app


def main() -> None:
    settings = load_settings()
    app = create_app(settings)
    # 证券名称清单走 baostock 逐页拉取，冷启动约一分钟；放后台预热，别让第一次搜索替它等。
    # 预热失败不影响启动：搜索仍可退回到只按代码搜。
    app.state.stock_names.warm_up()
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
