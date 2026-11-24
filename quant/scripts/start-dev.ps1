#Requires -Version 5.1
<#
.SYNOPSIS
    一键启动 quant 的开发环境：后端 FastAPI + 前端 Vite。

.DESCRIPTION
    两个服务各在一个独立窗口运行，关闭窗口即停止对应服务。
    - 后端：quant\backend 下 `python -m app`，监听地址与端口取自 config\config.toml
    - 前端：quant\web 下 `npm run dev`，127.0.0.1:5173，/api 已代理到后端

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File quant\scripts\start-dev.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$quantRoot   = Split-Path -Parent $PSScriptRoot
$backendDir  = Join-Path $quantRoot 'backend'
$webDir      = Join-Path $quantRoot 'web'
$pythonExe   = Join-Path $backendDir '.venv\Scripts\python.exe'

# 与 config\config.toml 的 server.port、web\vite.config.js 的 server.port 保持一致
$backendPort = 8000
$webPort     = 5173

function Fail([string]$message) {
    Write-Host "启动失败：$message" -ForegroundColor Red
    exit 1
}

function Test-PortInUse([int]$port) {
    try {
        return [bool](Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction Stop)
    } catch {
        return $false
    }
}

function Start-ServiceWindow([string]$title, [string]$workingDirectory, [string]$command) {
    # 子窗口保留在现场，出错信息不会一闪而过；$command 只用单引号，避免多层转义
    $inner = "`$Host.UI.RawUI.WindowTitle = '$title'; $command"
    Start-Process -FilePath 'powershell.exe' `
        -ArgumentList "-NoLogo -NoExit -Command `"$inner`"" `
        -WorkingDirectory $workingDirectory | Out-Null
}

# 前置检查：缺依赖时直接给出可执行的修复命令，不做半启动
if (-not (Test-Path $pythonExe)) {
    Fail "找不到后端虚拟环境 $pythonExe。请先在 quant\backend 执行：`n  python -m venv .venv`n  .\.venv\Scripts\python.exe -m pip install -e `".[dev]`""
}
if (-not (Test-Path (Join-Path $webDir 'node_modules'))) {
    Fail "找不到前端依赖 $webDir\node_modules。请先在 quant\web 执行：`n  npm install"
}

foreach ($port in @($backendPort, $webPort)) {
    if (Test-PortInUse $port) {
        Write-Host "警告：端口 $port 已被占用，对应服务可能启动失败（先关掉旧进程）。" -ForegroundColor Yellow
    }
}

Start-ServiceWindow 'quant-backend (FastAPI :8000)' $backendDir "& '.\.venv\Scripts\python.exe' -m app"
Start-ServiceWindow 'quant-web (Vite :5173)' $webDir 'npm run dev'

# 等两个端口真正可连接，避免浏览器打开时页面还是空白
$deadline = (Get-Date).AddSeconds(30)
while ((Get-Date) -lt $deadline) {
    if ((Test-PortInUse $backendPort) -and (Test-PortInUse $webPort)) {
        break
    }
    Start-Sleep -Milliseconds 500
}

$backendState = if (Test-PortInUse $backendPort) { '已就绪' } else { '未就绪，请查看后端窗口' }
$webState     = if (Test-PortInUse $webPort) { '已就绪' } else { '未就绪，请查看前端窗口' }

Write-Host ''
Write-Host "后端：http://127.0.0.1:$backendPort/api/v1/data/status  $backendState"
Write-Host "前端：http://127.0.0.1:$webPort  $webState"
Write-Host '两个服务运行在独立窗口，关闭窗口即停止对应服务。'
