#Requires -Version 5.1
<#
.SYNOPSIS
    Windows - Redis auto-download & start
.DESCRIPTION
    First run: downloads Redis for Windows to backend/redis_bin/
    Subsequent runs: starts local Redis directly
.NOTES
    redis_bin/ is gitignored
#>

$ErrorActionPreference = 'Stop'
$RedisDir = Join-Path (Join-Path $PSScriptRoot 'backend') 'redis_bin'
$RedisPort = 6379

# ---------- Check if Redis already exists ----------
if (Test-Path (Join-Path $RedisDir 'redis-server.exe')) {
    Write-Host '[Redis] Already exists locally, skip download' -ForegroundColor Green
} else {
    Write-Host '[Redis] First run, downloading Redis for Windows ...' -ForegroundColor Yellow

    $DownloadUrl = 'https://github.com/tporadowski/redis/releases/download/v5.0.14.1/Redis-x64-5.0.14.1.zip'
    $ZipPath = Join-Path $env:TEMP 'redis-windows.zip'

    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Write-Host "[Redis] Download: $DownloadUrl"
        Invoke-WebRequest -Uri $DownloadUrl -OutFile $ZipPath -UseBasicParsing
        Write-Host '[Redis] Download complete, extracting ...' -ForegroundColor Yellow

        New-Item -ItemType Directory -Force -Path $RedisDir | Out-Null
        Expand-Archive -Path $ZipPath -DestinationPath $RedisDir -Force
        Remove-Item $ZipPath -Force

        Write-Host '[Redis] Extract complete' -ForegroundColor Green
    } catch {
        Write-Host "[Redis] Download failed: $_" -ForegroundColor Red
        Write-Host "[Redis] Please download Redis for Windows manually to: $RedisDir" -ForegroundColor Yellow
        Write-Host '[Redis] Recommended: https://github.com/tporadowski/redis/releases' -ForegroundColor Yellow
        exit 1
    }
}

# ---------- Check if port is already in use ----------
$portInUse = Get-NetTCPConnection -LocalPort $RedisPort -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Listen' }
if ($portInUse) {
    Write-Host "[Redis] Port $RedisPort already in use, Redis may already be running" -ForegroundColor Yellow
    exit 0
}

# ---------- Start Redis ----------
$RedisExe = Join-Path $RedisDir 'redis-server.exe'
if (-not (Test-Path $RedisExe)) {
    Write-Host "[Redis] redis-server.exe not found in $RedisDir" -ForegroundColor Red
    exit 1
}

Write-Host "[Redis] Starting Redis on port $RedisPort ..." -ForegroundColor Green
Start-Process -FilePath $RedisExe -ArgumentList '--port', $RedisPort, '--maxmemory', '256mb', '--maxmemory-policy', 'allkeys-lru' -WindowStyle Normal

# Wait for Redis ready
$maxWait = 10
$ready = $false
for ($i = 0; $i -lt $maxWait; $i++) {
    Start-Sleep -Seconds 1
    try {
        $conn = New-Object System.Net.Sockets.TcpClient('127.0.0.1', $RedisPort)
        $conn.Close()
        $ready = $true
        break
    } catch {
        # keep waiting
    }
}

if ($ready) {
    Write-Host "[Redis] Redis started successfully (port $RedisPort)" -ForegroundColor Green
} else {
    Write-Host '[Redis] Redis startup timeout, please check manually' -ForegroundColor Red
    exit 1
}
