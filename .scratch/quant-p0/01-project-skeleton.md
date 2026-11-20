---
id: 01
title: 项目骨架与配置
status: done
blocked_by: []
---

## 要做什么

在仓库内新建独立的 `quant` 项目（与 `lianghua`、`everything` 平级，互不引用源码），跑通最小可运行闭环：后端服务启动、读取配置文件、提供健康检查接口、前端页面能显示后端在线状态。

## 验收标准

- [x] 后端可启动，健康检查接口返回版本号与当前生效的数据目录绝对路径
- [x] 数据目录、监听端口、时区从配置文件读取，修改配置后重启即生效，无需改代码
- [x] 前端页面能显示后端在线状态与版本号
- [x] 仓库中不出现对 `lianghua`、`everything` 源码的 import 或路径引用
- [x] 提供配置示例文件，真实配置文件不入 git

## 备注

- 后端 Python + FastAPI；前端 Vue 3；移动端后期用 Expo/RN（不在本票范围）
- 部署形态：家庭局域网内运行，服务端可访问公网（用于出站推送），不接受公网入站
- 所有接口统一前缀 `/api/v1`，返回结构统一，便于后续票扩展

## 实现记录

- 配置用 TOML + 标准库 `tomllib`，不引入配置框架；相对路径一律相对 `quant` 项目根解析，与启动工作目录无关
- 配置错误一律启动即失败并给出可操作提示（缺文件时提示复制示例），不做静默兜底
- Windows 无系统时区库，`zoneinfo` 需要 `tzdata` 依赖，否则 `Asia/Shanghai` 解析失败
- Vite 默认 `localhost` 在 Windows 上可能只监听 `::1`，导致 `127.0.0.1:5173` 连不上；已显式绑定 IPv4，与 CORS 白名单保持一致
- CORS 白名单禁止通配符（服务无鉴权），与 `lianghua` 的约定一致
- 响应统一为 `{code, message, data}`，字段 camelCase，时间为带时区的 ISO 8601；错误体统一为 `{code, message}`，不把 FastAPI 默认的 `{detail}` 漏给前端
- 启动入口收敛为 `python -m app`，监听地址与端口取自配置；不再保留 `uvicorn app.main:app` 这条并行入口，避免两套启动方式漂移
- 新增 `quant/AGENTS.md`，按根 `AGENTS.md` 的子项目约定补齐技术栈、命令与边界
