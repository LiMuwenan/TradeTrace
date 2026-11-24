#!/usr/bin/env bash
# 一键启动 quant 开发环境（Windows + Git Bash）
#
# 后端 FastAPI 监听 8000，前端 Vite 监听 5173；两个进程都在当前终端输出日志，
# Ctrl+C 同时停止。端口与 config/config.toml、web/vite.config.js 保持一致。

set -u

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
QUANT_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
BACKEND_DIR="$QUANT_ROOT/backend"
WEB_DIR="$QUANT_ROOT/web"
PYTHON="$BACKEND_DIR/.venv/Scripts/python.exe"

BACKEND_PORT=8000
WEB_PORT=5173

BACKEND_PID=""
WEB_PID=""
STOPPED=0

fail() {
    printf '启动失败：%s\n' "$1" >&2
    exit 1
}

# 用 bash 的 /dev/tcp 探测端口，避免依赖 curl 或 netstat
port_open() {
    (echo > "/dev/tcp/127.0.0.1/$1") >/dev/null 2>&1
}

# 结束一个后台任务及其子进程：npm 会派生 node，只杀 npm 会留下占用端口的孤儿进程
stop_process() {
    local pid=${1:-}
    [ -z "$pid" ] && return 0

    local win_pid
    win_pid=$(cat "/proc/$pid/winpid" 2>/dev/null || true)
    if [ -n "$win_pid" ]; then
        taskkill //F //T //PID "$win_pid" >/dev/null 2>&1 || true
    fi
    kill "$pid" 2>/dev/null || true
}

cleanup() {
    [ "$STOPPED" = 1 ] && return
    STOPPED=1
    printf '\n正在停止服务...\n'
    stop_process "$WEB_PID"
    stop_process "$BACKEND_PID"
    wait 2>/dev/null
    printf '已停止。\n'
}

trap cleanup EXIT
trap 'exit 0' INT TERM

# 前置检查：缺依赖时直接给出可执行的修复命令，不做半启动
[ -f "$PYTHON" ] || fail "找不到后端虚拟环境 $PYTHON
请先在 quant/backend 执行：
  python -m venv .venv
  ./.venv/Scripts/python.exe -m pip install -e '.[dev]'"
[ -d "$WEB_DIR/node_modules" ] || fail "找不到前端依赖 $WEB_DIR/node_modules
请先在 quant/web 执行：
  npm install"

if port_open "$BACKEND_PORT"; then
    printf '警告：端口 %s 已被占用，后端可能启动失败（先关掉旧进程）。\n' "$BACKEND_PORT"
fi
if port_open "$WEB_PORT"; then
    printf '警告：端口 %s 已被占用，前端可能启动失败（先关掉旧进程）。\n' "$WEB_PORT"
fi

printf '启动后端：%s\n' "$BACKEND_DIR"
(cd "$BACKEND_DIR" && exec "$PYTHON" -m app) &
BACKEND_PID=$!

printf '启动前端：%s\n' "$WEB_DIR"
(cd "$WEB_DIR" && exec npm run dev) &
WEB_PID=$!

# 等两个端口真正可连接，避免浏览器打开时页面还是空白
waited=0
while [ "$waited" -lt 20 ]; do
    if port_open "$BACKEND_PORT" && port_open "$WEB_PORT"; then
        break
    fi
    if ! kill -0 "$BACKEND_PID" 2>/dev/null || ! kill -0 "$WEB_PID" 2>/dev/null; then
        break
    fi
    sleep 1
    waited=$((waited + 1))
done

printf '\n'
if port_open "$BACKEND_PORT"; then
    printf '后端：http://127.0.0.1:%s/api/v1/data/status  已就绪\n' "$BACKEND_PORT"
else
    printf '后端：http://127.0.0.1:%s/api/v1/data/status  未就绪，请查看上方日志\n' "$BACKEND_PORT"
fi
if port_open "$WEB_PORT"; then
    printf '前端：http://127.0.0.1:%s  已就绪\n' "$WEB_PORT"
else
    printf '前端：http://127.0.0.1:%s  未就绪，请查看上方日志\n' "$WEB_PORT"
fi
printf '按 Ctrl+C 停止两个服务。\n'

# 任一服务退出就结束，由 EXIT trap 清理另一个
while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$WEB_PID" 2>/dev/null; do
    sleep 1
done
