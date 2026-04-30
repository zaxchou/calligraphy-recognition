@echo off
chcp 65001 >nul
echo 正在停止所有服务...
cd /d "%~dp0"
taskkill /FI "WINDOWTITLE eq FastAPI" /F 2>nul
taskkill /FI "WINDOWTITLE eq CeleryWorker" /F 2>nul
taskkill /FI "WINDOWTITLE eq tubi_worker" /F 2>nul
taskkill /FI "WINDOWTITLE eq Redis" /F 2>nul
echo 已停止。
timeout /t 1 /nobreak >nul
