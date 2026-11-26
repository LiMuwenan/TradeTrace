---
id: 12
title: Web 端视觉改版：落地页 + 控制台双视图
status: done
blocked_by: []
---

## 要做什么

把 `quant/web` 从单页工具界面改版为两种视图：

1. 图 1 风格的落地首页：渐变光晕 hero、大标题排版、eyebrow、主次按钮、域名/标的展示卡片、三栏特性区。
2. 图 2 风格的控制台：左侧分组侧栏、顶栏搜索/语言/头像、卡片网格。

两视图可相互切换。视觉层用 Tailwind CSS + shadcn 风格组件（cva / clsx / tailwind-merge / lucide 图标 / reka-ui 原语）。

## 验收标准

- [x] `npm install` 与 `npm run build` 通过
- [x] 现有 `fetchHealth` / `fetchDataStatus` / 自选增删改 / `searchStocks` 全部保留，接口调用不变
- [x] 服务状态、自选、数据状态三块功能在控制台视图中可正常使用
- [x] 涨红跌绿配色口径保持不变
- [x] 不引用 `lianghua/`、`everything/` 源码；不改动后端
- [x] 新增依赖只落在 `quant/web/package.json`

## 备注

- 用户选定「两者结合 / 先换皮不动功能 / Tailwind + 组件库」。
- 不引入 vue-router，用单个 `view` 状态切换，避免改动 API 层之外的结构。
- 图 1 落地页按钮只做视图跳转，不接注册/下单逻辑。

## 实现记录

- 依赖：tailwindcss@3 + postcss/autoprefixer，shadcn 风格栈用 cva / clsx / tailwind-merge / lucide-vue-next / reka-ui；未引入 vue-router，用 `view` 状态切换两个视图。
- 设计 token 落在 `src/style.css`，浅色主题；A 股涨跌语义色显式定义为 `--up`（红）/ `--down`（绿），避免与后端 `ok/bad` 语义混淆。
- `src/components/ui/` 下是最小可复用的 Button / Card 系列 / Input / Badge，按需扩展；reka-ui 只用于「说明与帮助」的折叠面板。
- 后端未改动；`api/client.js` 未改动，原三块功能的状态与方法原样迁移到 `Dashboard.vue`。
- `quant/assets/` 下两张参考截图不入库。
