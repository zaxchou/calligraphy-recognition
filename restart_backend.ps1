# 重启后端服务
Write-Host "正在重启后端服务..." -ForegroundColor Yellow

# 尝试停止现有 Python 进程
Get-Process python -ErrorAction SilentlyContinue | ForEach-Object { 
    try {
        $_.Kill()
        Write-Host "已停止 Python 进程 (PID: $($_.Id))"
    } catch {
        Write-Host "无法停止进程 $($_.Id)，可能正在运行中"
    }
}

Start-Sleep 2

# 启动后端
Write-Host "启动 FastAPI 后端..." -ForegroundColor Green
$env:PYTHONPATH = "c:\Users\zeroz\cursor code\calligraphy-recognition\backend"
$env:SERVER_PORT = "8001"

cd "c:\Users\zeroz\cursor code\calligraphy-recognition\backend"
Start-Process python -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--reload" -WindowStyle Hidden

Write-Host "后端服务已启动在 http://localhost:8001" -ForegroundColor Green
Write-Host "按任意键关闭此窗口..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
