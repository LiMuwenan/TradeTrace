# Issue tracker

本仓库使用 **local markdown** 跟踪工作：不以 GitHub Issues 为准，issues 是仓库内的普通文件。

## 目录约定

- 位置：`.scratch/<feature>/`，一个 feature 一个目录
- 粒度：一个 ticket 一个文件，命名 `<两位序号>-<slug>.md`（如 `03-alert-rule-model.md`）
- `.scratch/` 纳入 git 版本控制，ticket 随代码一起演进

## Ticket 文件格式

```markdown
---
id: 03
title: 一句话说明这个 ticket 交付什么
status: todo        # todo | doing | done
blocked_by: [01]    # 其他 ticket 的 id，空数组表示无前置
---

## 要做什么

## 验收标准

## 备注
```

## 读写约定

| Skill | 行为 |
|---|---|
| `zh-to-spec` | 把访谈结论写成 spec（放在 `docs/specs/`） |
| `zh-to-tickets` | 按 spec 拆分，写入 `.scratch/<feature>/` |
| `zh-implement` | 读取 ticket，只做 `status: todo` 且 `blocked_by` 全部 done 的条目 |
| `zh-implement-spec` | 把 tickets 当 task graph，在可执行 frontier 上并行 |

## 规则

- ticket 必须自包含：实现者只读这一个文件就能开工，不依赖对话上下文
- 完成一个 ticket 就把 `status` 改为 `done`，并在同一次提交里包含该改动
- 不新建 `.scratch/` 之外的第二套 issue 记录（不在 `docs/` 里再放一份待办列表）
