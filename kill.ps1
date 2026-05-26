# kill.ps1 — 一键杀掉所有书法项目进程
# 用法：右键 → "使用 PowerShell 运行"，或桌面双击

$ports = @(3000, 5173, 6333, 8080)
foreach ($port in $ports) {
    $conn = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Where-Object { $_.OwningProcess -ne 0 }
    if ($conn) {
        $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
        Stop-Process -Id $conn.OwningProcess -Force
        Write-Host "Killed $($proc.ProcessName) (PID $($conn.OwningProcess)) on port $port"
    } else {
        Write-Host "Port $port is free"
    }
}

# 兜底：杀掉所有残留 Python 进程
$pythons = Get-Process -Name "python*" -ErrorAction SilentlyContinue
if ($pythons) {
    $pythons | Stop-Process -Force
    Write-Host "Killed $($pythons.Count) python processes"
}

Write-Host "All cleared. Ready to start fresh."
Read-Host "Press Enter to close"
