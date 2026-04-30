@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   启动书法识别系统所有服务
echo ========================================
echo.

cd /d "%~dp0"

:: 检测 Python
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 未找到，请先安装 Python
    pause
    exit /b 1
)

:: 启动 Redis（使用内置的 redis\redis-server.exe）
echo [1/4] 启动 Redis...
tasklist /FI "IMAGENAME eq redis-server.exe" 2>nul | find /I "redis-server.exe" >nul
if %errorlevel%==0 (
    echo   Redis 已在运行
) else (
    start /B "Redis" redis\redis-server.exe --port 6379 --loglevel warning
    timeout /t 2 /nobreak >nul
    redis\redis-cli.exe ping >nul 2>&1
    if errorlevel 0 (
        echo   [OK] Redis 启动成功
    ) else (
        echo   [WARNING] Redis 启动可能失败，尝试继续...
    )
)

:: 启动 Celery Worker（构图分析 etc.）
echo [2/4] 启动 Celery Worker...
tasklist /FI "WINDOWTITLE eq CeleryWorker" 2>nul | find /I "celery" >nul
if %errorlevel%==0 (
    echo   Celery Worker 已在运行
) else (
    start /B "CeleryWorker" cmd /c ".\venv\Scripts\python.exe -m celery -A app.core.celery_app worker -l info -P threads"
    echo   Celery Worker 启动中（等待 5 秒）...
    timeout /t 5 /nobreak >nul
)

:: 启动 FastAPI
echo [3/4] 启动 FastAPI (uvicorn)...
tasklist /FI "WINDOWTITLE eq FastAPI" 2>nul | find /I "uvicorn" >nul
if %errorlevel%==0 (
    echo   FastAPI 已在运行
) else (
    start /B "FastAPI" cmd /c ".\venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001"
    echo   FastAPI 启动中（等待 3 秒）...
    timeout /t 3 /nobreak >nul
)

:: 启动 tubi_worker
echo [4/4] 启动 tubi_worker...
tasklist /FI "WINDOWTITLE eq tubi_worker" 2>nul | find /I "tubi_worker" >nul
if %errorlevel%==0 (
    echo   tubi_worker 已在运行
) else (
    start /B "tubi_worker" cmd /c ".\venv\Scripts\python.exe tubi_worker.py"
    echo   tubi_worker 启动中（等待 2 秒）...
    timeout /t 2 /nobreak >nul
)

echo.
echo ========================================
echo   启动完成！
echo ========================================
echo.
echo 服务地址：
echo   FastAPI:   http://localhost:8001
echo   前端:      http://localhost:3000
echo   Redis:     localhost:6379
echo.
echo 查看日志：
echo   后端:      backend\app.log
echo   Pipeline:  backend\pipeline.log
echo.
echo 重启流程：双击 stop_all.bat → 再双击本文件
echo.
pause
