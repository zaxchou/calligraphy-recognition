#Requires -Version 5.1
<#
.SYNOPSIS
    Start Qdrant vector database (Windows)
.DESCRIPTION
    Starts Qdrant from bundled binary in backend/qdrant_bin/.
    Data stored in backend/qdrant_bin/qdrant_storage/.
.EXAMPLE
    .\start_qdrant_windows.ps1
#>

$ErrorActionPreference = 'Stop'
$ProjectDir = $PSScriptRoot
$BackendDir = Join-Path $ProjectDir 'backend'
$QdrantBinDir = Join-Path $BackendDir 'qdrant_bin'
$QdrantExe = Join-Path $QdrantBinDir 'qdrant.exe'
$QdrantPort = 6333

if (-not (Test-Path $QdrantExe)) {
    Write-Host '[Qdrant] qdrant.exe not found at' $QdrantExe -ForegroundColor Red
    Write-Host '[Qdrant] Please download from: https://github.com/qdrant/qdrant/releases' -ForegroundColor Yellow
    exit 1
}

# Check if already running
try {
    $conn = New-Object System.Net.Sockets.TcpClient('127.0.0.1', $QdrantPort)
    $conn.Close()
    Write-Host "[Qdrant] Already running on port $QdrantPort" -ForegroundColor Green
    exit 0
} catch {}

# Start Qdrant
$configPath = Join-Path $QdrantBinDir 'config.yaml'
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $QdrantExe
$psi.Arguments = "--config-path `"$configPath`" --disable-telemetry"
$psi.WorkingDirectory = $QdrantBinDir
$psi.UseShellExecute = $true
$psi.WindowStyle = 'Normal'
[System.Diagnostics.Process]::Start($psi) | Out-Null

# Wait and verify
$maxWait = 15
$started = $false
for ($i = 1; $i -le $maxWait; $i++) {
    Start-Sleep -Seconds 1
    try {
        $conn = New-Object System.Net.Sockets.TcpClient('127.0.0.1', $QdrantPort)
        $conn.Close()
        $started = $true
        break
    } catch {}
}

if ($started) {
    Write-Host "[Qdrant] Started on port $QdrantPort (PID captured)" -ForegroundColor Green
    Write-Host "[Qdrant] Dashboard: http://localhost:$QdrantPort/dashboard" -ForegroundColor DarkGray
} else {
    Write-Host "[Qdrant] Failed to start within ${maxWait}s" -ForegroundColor Red
    exit 1
}
