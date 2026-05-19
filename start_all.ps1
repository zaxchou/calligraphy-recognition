# ============================================================
#  墨林百科 - 一键启动 (Windows PowerShell)
#  启动: FastAPI 后端 (3000) + Vite 前端 (8080)
# ============================================================

$ErrorActionPreference = "Stop"

$BACKEND_DIR = "$PSScriptRoot\backend"
$FRONTEND_DIR = "$PSScriptRoot\frontend"
$BACKEND_PORT = 3000
$FRONTEND_PORT = 8080

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  墨林百科 - 一键启动" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ---------- 1. 后端 ----------
Write-Host "[1/2] 启动 FastAPI 后端 (port $BACKEND_PORT)..." -ForegroundColor Yellow

# 杀掉占用端口的旧进程
$oldPid = (Get-NetTCPConnection -LocalPort $BACKEND_PORT -ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess
if ($oldPid) {
    Write-Host "  关闭旧进程 PID $oldPid..."
    Stop-Process -Id $oldPid -Force -ErrorAction SilentlyContinue
    Start-Sleep 2
}

Push-Location $BACKEND_DIR
try {
    Start-Process -NoNewWindow -FilePath "python" -ArgumentList "-m","uvicorn","app.main:app","--host","0.0.0.0","--port","$BACKEND_PORT","--workers","2" -RedirectStandardOutput "$BACKEND_DIR\fastapi.log" -RedirectStandardError "$BACKEND_DIR\fastapi_error.log"
    Write-Host "  后端已启动，日志: $BACKEND_DIR\fastapi.log" -ForegroundColor Green
} finally {
    Pop-Location
}

Start-Sleep 3

# 验证后端
try {
    $resp = Invoke-WebRequest -Uri "http://localhost:$BACKEND_PORT/docs" -UseBasicParsing -TimeoutSec 5
    Write-Host "  后端验证: OK (http://localhost:$BACKEND_PORT/docs)" -ForegroundColor Green
} catch {
    Write-Host "  后端可能还在启动中，稍等..." -ForegroundColor DarkYellow
}

Write-Host ""

# ---------- 2. 前端 ----------
Write-Host "[2/2] 启动 Vite 前端 (port $FRONTEND_PORT)..." -ForegroundColor Yellow

$oldFrontPid = (Get-NetTCPConnection -LocalPort $FRONTEND_PORT -ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess
if ($oldFrontPid) {
    Write-Host "  关闭旧进程 PID $oldFrontPid..."
    Stop-Process -Id $oldFrontPid -Force -ErrorAction SilentlyContinue
    Start-Sleep 2
}

Push-Location $FRONTEND_DIR
try {
    Start-Process -NoNewWindow -FilePath "npm" -ArgumentList "run","dev" -RedirectStandardOutput "$FRONTEND_DIR\vite.log" -RedirectStandardError "$FRONTEND_DIR\vite_error.log"
    Write-Host "  前端已启动，日志: $FRONTEND_DIR\vite.log" -ForegroundColor Green
} finally {
    Pop-Location
}

Start-Sleep 3

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  全部服务已启动!" -ForegroundColor Green
Write-Host ""
Write-Host "  前端:       http://localhost:$FRONTEND_PORT" -ForegroundColor White
Write-Host "  后端 API:   http://localhost:$BACKEND_PORT" -ForegroundColor White
Write-Host "  API 文档:   http://localhost:$BACKEND_PORT/docs" -ForegroundColor White
Write-Host ""
Write-Host "  停止: 关闭这两个 PowerShell 窗口" -ForegroundColor DarkGray
Write-Host "========================================" -ForegroundColor Cyan
