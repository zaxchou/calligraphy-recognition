# ============================================================
#   Molin Wiki - One-Click Launch (Windows PowerShell)
#   每个服务独立窗口，关窗即停，端口 3000 永无冲突
# ============================================================

param(
    [switch]$SkipQdrant,
    [switch]$SkipRedis,
    [switch]$SkipCelery,
    [switch]$SkipTubi
)

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$BACKEND_DIR = "$ROOT\backend"
$FRONTEND_DIR = "$ROOT\frontend"
$PORT = 3000

# ── 端口清理：防止旧进程残留导致启动失败 ──
$ports = @(3000, 5173, 8080, 6333)
foreach ($p in $ports) {
    $conn = Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue
    if ($conn) {
        $name = (Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue).ProcessName
        Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
        Write-Host "Cleaned port $p ($name)" -ForegroundColor DarkGray
    }
}
# 清除所有 Python 编译缓存
Get-ChildItem -Path $BACKEND_DIR -Filter "__pycache__" -Recurse -Directory -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "Cleaned Python bytecode cache" -ForegroundColor DarkGray

Write-Host ""
Write-Host ("=" * 50) -ForegroundColor Cyan
Write-Host "  Molin Wiki - Quick Start" -ForegroundColor Cyan
Write-Host "  All services open in separate windows" -ForegroundColor Cyan
Write-Host ("=" * 50) -ForegroundColor Cyan
Write-Host ""

# Redis
if (-not $SkipRedis) {
    Write-Host "[0/5] Starting Redis..." -ForegroundColor Yellow
    $redisExe = "$BACKEND_DIR\redis_bin\redis-server.exe"
    if (Test-Path $redisExe) {
        Start-Process -FilePath $redisExe -ArgumentList "$BACKEND_DIR\redis_bin\redis.windows.conf" -WindowStyle Normal
        Write-Host "  OK - Redis window opened" -ForegroundColor Green
    } else { Write-Host "  SKIP - Redis not installed" -ForegroundColor DarkGray }
}

# Qdrant
if (-not $SkipQdrant) {
    Write-Host "[1/5] Starting Qdrant..." -ForegroundColor Yellow
    $qdrantExe = "$BACKEND_DIR\qdrant_bin\qdrant.exe"
    if (Test-Path $qdrantExe) {
        Start-Process -FilePath $qdrantExe -WorkingDirectory "$BACKEND_DIR\qdrant_bin" -WindowStyle Normal
        Write-Host "  OK - Qdrant window opened" -ForegroundColor Green
    } else { Write-Host "  SKIP - Qdrant not installed" -ForegroundColor DarkGray }
}

# Celery
if (-not $SkipCelery) {
    Write-Host "[2/5] Starting Celery Worker..." -ForegroundColor Yellow
    Push-Location $BACKEND_DIR
    Start-Process -FilePath "python" -ArgumentList "-m","celery","-A","app.core.celery_app","worker","--loglevel=info","--pool=solo","-n","worker1@%h" -WindowStyle Normal
    Pop-Location
    Write-Host "  OK - Celery window opened" -ForegroundColor Green
}

# Backend (port 3000)
Write-Host "[3/5] Starting FastAPI Backend (port $PORT)..." -ForegroundColor Yellow
Push-Location $BACKEND_DIR
Start-Process -FilePath "python" -ArgumentList "-m","uvicorn","app.main:app","--host","0.0.0.0","--port","$PORT","--workers","2" -WindowStyle Normal
Pop-Location
Write-Host "  OK - Backend window opened" -ForegroundColor Green

# Tubi Worker（已嵌入 FastAPI，不再需要独立进程）
if (-not $SkipTubi) {
    Write-Host "[4/5] Tubi Worker: embedded in FastAPI (no separate process)" -ForegroundColor DarkGray
}

# Frontend (port 8080)
Write-Host "[5/5] Starting Vite Frontend (port 8080)..." -ForegroundColor Yellow
Push-Location $FRONTEND_DIR
Start-Process -FilePath "cmd.exe" -ArgumentList "/k","npm run dev" -WindowStyle Normal
Pop-Location
Write-Host "  OK - Frontend window opened" -ForegroundColor Green

Write-Host ""
Write-Host ("=" * 50) -ForegroundColor Cyan
Write-Host "  All services started!" -ForegroundColor Green
Write-Host ""
Write-Host "  Frontend:   http://localhost:8080" -ForegroundColor White
Write-Host "  Backend:    http://localhost:$PORT" -ForegroundColor White
Write-Host "  API Docs:   http://localhost:$PORT/docs" -ForegroundColor White
Write-Host ""
Write-Host "  Close each window to stop, or use Task Manager." -ForegroundColor DarkGray
Write-Host ("=" * 50) -ForegroundColor Cyan
