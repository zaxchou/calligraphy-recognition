# 重启后端服务
$ErrorActionPreference = "Continue"

$backendDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $backendDir

Write-Host "[1/3] 停用旧进程..." -ForegroundColor Yellow
$pids = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {
    $_.MainWindowTitle -eq "" -and $_.Id -ne $PID
} | ForEach-Object { $_.Id }

if ($pids) {
    $pids | ForEach-Object {
        Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 1
    Write-Host "  已终止: $($pids -join ', ')" -ForegroundColor Green
} else {
    Write-Host "  无正在运行的后端进程" -ForegroundColor DarkGray
}

Write-Host "[2/3] 检查端口..." -ForegroundColor Yellow
$portCheck = netstat -ano | Select-String ":8001" -ErrorAction SilentlyContinue
if ($portCheck) { Write-Host "  端口 8001 已被释放" -ForegroundColor Green }

Write-Host "[3/3] 启动后端 (http://localhost:8001)..." -ForegroundColor Yellow
$env:PYTHONPATH = $backendDir
python "$backendDir\app\main.py"
