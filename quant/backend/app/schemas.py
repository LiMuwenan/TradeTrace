# -*- coding: utf-8 -*-
"""统一响应结构：成功为 {code:0, message:"ok", data}，失败为 {code, message}。

字段命名遵循仓库协议约定（JSON 使用 camelCase）。
"""


def ok(data: dict) -> dict:
    return {"code": 0, "message": "ok", "data": data}


def fail(code: int, message: str) -> dict:
    return {"code": code, "message": message}
