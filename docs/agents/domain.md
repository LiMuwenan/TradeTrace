# Domain docs

布局：**single-context**

## 位置

- `GLOSSARY.md` —— 仓库根目录，全仓库唯一的领域词汇表
- `docs/adr/` —— 架构决策记录，命名 `NNNN-<slug>.md`

## 使用规则

- 命名任何新概念前先读 `GLOSSARY.md`；同一个词只允许一个含义。
- 出现新术语时立即追加到 `GLOSSARY.md`：写定义，并写「它不是什么」作为反例。
- 难以逆转的决策写 ADR，至少包含：背景、选择、备选方案、代价与风险。
- 既有 ADR 被推翻时不改写原文，新增一条 ADR 并在其中标注它取代了哪一条。
- 本仓库有多个子项目（`lianghua/`、`everything/`、后续新增目录），共用这同一份词汇表。**同一个词在不同子项目含义不同时，必须在 `GLOSSARY.md` 中显式标注作用域**，不得各自默会。
- `docs/conversation-archive/` 记录会话过程，不承担词汇表职责；词汇以 `GLOSSARY.md` 为准。
