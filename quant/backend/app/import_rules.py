# -*- coding: utf-8 -*-
"""种子规则导入命令（06 号票上线前的调试后门，届时删除）：

    python -m app.import_rules [规则文件]

不指定文件时读取 `config/rules.example.toml`。规则写入 `{meta_dir}/meta.db`
的 `alert_rule` 表；导入后仍需调用 `POST /api/v1/rules/{id}/replay` 建立历史状态。
"""
from __future__ import annotations

import argparse
from pathlib import Path

from app.config import PROJECT_ROOT, load_settings
from app.storage.meta_db import RuleValidationError, connect
from app.storage.rule_store import import_seed_rules

DEFAULT_SEED_PATH = PROJECT_ROOT / "config" / "rules.example.toml"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="从 TOML 导入种子预警规则")
    parser.add_argument("source", nargs="?", help="规则 TOML 路径，默认 config/rules.example.toml")
    args = parser.parse_args(argv)

    settings = load_settings()
    path = Path(args.source) if args.source else DEFAULT_SEED_PATH
    if not path.is_file():
        print(f"规则文件不存在：{path}")
        return 1

    conn = connect(settings.meta_dir, settings.timezone)
    try:
        created = import_seed_rules(conn, path, settings.timezone)
    except RuleValidationError as exc:
        print(f"规则不合法：{exc}")
        return 1
    finally:
        conn.close()

    for rule in created:
        print(f"已导入 #{rule.id} {rule.name}（{rule.type}, N={rule.window}）")
    print(f"共 {len(created)} 条。下一步：POST /api/v1/rules/<id>/replay 建立历史状态。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
