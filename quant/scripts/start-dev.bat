@echo off
chcp 65001 >nul
setlocal

rem 一键启动 quant 开发环境：后端 FastAPI（8000）+ 前端 Vite（5173）
rem 两个服务各在一个独立窗口运行，关闭窗口即停止对应服务。
rem 端口与 config\config.toml 的 server.port、web\vite.config.js 的 server.port 保持一致。

for %%I in ("%~dp0..") do set "QUANT_ROOT=%%~fI"
set "BACKEND_DIR=%QUANT_ROOT%\backend"
set "WEB_DIR=%QUANT_ROOT%\web"
set "PYTHON=%BACKEND_DIR%\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo 启动失败：找不到后端虚拟环境 %PYTHON%
    echo 请先在 quant\backend 执行：
    echo   python -m venv .venv
    echo   .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
    exit /b 1
)
if not exist "%WEB_DIR%\node_modules" (
    echo 启动失败：找不到前端依赖 %WEB_DIR%\node_modules
    echo 请先在 quant\web 执行：
    echo   npm install
    exit /b 1
)

netstat -ano | findstr /c:":8000 " | findstr /i "LISTENING" >nul
if not errorlevel 1 echo 警告：端口 8000 已被占用，后端可能启动失败（先关掉旧进程）。
netstat -ano | findstr /c:":5173 " | findstr /i "LISTENING" >nul
if not errorlevel 1 echo 警告：端口 5173 已被占用，前端可能启动失败（先关掉旧进程）。

start "quant-backend (FastAPI :8000)" /D "%BACKEND_DIR%" cmd /k ".\.venv\Scripts\python.exe -m app"
start "quant-web (Vite :5173)" /D "%WEB_DIR%" cmd /k "npm run dev"

rem 等两个端口真正可连接，避免浏览器打开时页面还是空白
set /a WAITED=0
:wait_ready
netstat -ano | findstr /c:":8000 " | findstr /i "LISTENING" >nul
if errorlevel 1 goto still_waiting
netstat -ano | findstr /c:":5173 " | findstr /i "LISTENING" >nul
if errorlevel 1 goto still_waiting
goto report

:still_waiting
if %WAITED% GEQ 20 goto report
timeout /t 2 /nobreak >nul
set /a WAITED+=2
goto wait_ready

:report
echo.
netstat -ano | findstr /c:":8000 " | findstr /i "LISTENING" >nul
if errorlevel 1 (echo 后端：http://127.0.0.1:8000/api/v1/data/status  未就绪，请查看后端窗口) else (echo 后端：http://127.0.0.1:8000/api/v1/data/status  已就绪)
netstat -ano | findstr /c:":5173 " | findstr /i "LISTENING" >nul
if errorlevel 1 (echo 前端：http://127.0.0.1:5173  未就绪，请查看前端窗口) else (echo 前端：http://127.0.0.1:5173  已就绪)
echo 两个服务运行在独立窗口，关闭窗口即停止对应服务。
endlocal
