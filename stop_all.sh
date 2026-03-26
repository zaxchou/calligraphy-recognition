#!/usr/bin/env bash
# ============================================================
#  书法碑帖字体认证系统 - 停止所有服务 (Linux / macOS)
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
API_PORT=8001

echo "停止所有服务 ..."

# FastAPI
if [ -f "$BACKEND_DIR/fastapi.pid" ]; then
    PID=$(cat "$BACKEND_DIR/fastapi.pid")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "[FastAPI] 已停止 (PID: $PID)"
    fi
    rm -f "$BACKEND_DIR/fastapi.pid"
fi

# Celery
if [ -f "$BACKEND_DIR/celery_worker.pid" ]; then
    PID=$(cat "$BACKEND_DIR/celery_worker.pid")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "[Celery] 已停止 (PID: $PID)"
    fi
    rm -f "$BACKEND_DIR/celery_worker.pid"
fi

# Redis (可选，不自动停系统 Redis，避免影响其他服务)
echo ""
echo "注意: Redis 未停止 (可能被其他服务使用)"
echo "如需停止: redis-cli shutdown"
echo ""
echo "所有服务已停止。"
