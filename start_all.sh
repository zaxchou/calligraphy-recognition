#!/usr/bin/env bash
# ============================================================
#  书法碑帖字体认证系统 - 一键启动 (Linux / macOS)
#  按顺序启动: Qdrant → Redis → Celery Worker → FastAPI 后端
#  用法:
#    chmod +x start_all.sh
#    ./start_all.sh                    # 启动全部
#    ./start_all.sh --skip-fastapi      # 只启动 Qdrant + Redis + Celery
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
REDIS_PORT=6379
API_PORT=8001
QDRANT_PORT=6333
SKIP_QDRANT=false
SKIP_REDIS=false
SKIP_CELERY=false
SKIP_FASTAPI=false

# 解析参数
for arg in "$@"; do
    case "$arg" in
        --skip-qdrant)     SKIP_QDRANT=true ;;
        --skip-redis)      SKIP_REDIS=true ;;
        --skip-celery)     SKIP_CELERY=true ;;
        --skip-fastapi)    SKIP_FASTAPI=true ;;
        --help|-h)
            echo "用法: $0 [--skip-qdrant] [--skip-redis] [--skip-celery] [--skip-fastapi]"
            exit 0
            ;;
    esac
done

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   书法碑帖字体认证系统 - 一键启动            ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# 查找 Python
PYTHON="${PYTHON:-$(command -v python3 || command -v python || echo '')}"
if [ -z "$PYTHON" ]; then
    echo "[错误] 找不到 Python，请安装 Python 3.9+" >&2
    exit 1
fi

# 检查虚拟环境
if [ -f "$BACKEND_DIR/venv/bin/activate" ]; then
    echo "[环境] 检测到 venv，使用虚拟环境"
    source "$BACKEND_DIR/venv/bin/activate"
    PYTHON="python"
fi

# ========== 1. Qdrant ==========
if [ "$SKIP_QDRANT" = false ]; then
    echo "[1/4] Checking Qdrant ..."
    if curl -s "http://localhost:$QDRANT_PORT/collections" >/dev/null 2>&1; then
        echo "[Qdrant] Already running (port $QDRANT_PORT)"
    else
        QDRANT_BIN=""
        # Check bundled binary
        if [ -x "$BACKEND_DIR/qdrant_bin/qdrant" ]; then
            QDRANT_BIN="$BACKEND_DIR/qdrant_bin/qdrant"
        elif command -v qdrant &>/dev/null; then
            QDRANT_BIN="qdrant"
        fi

        if [ -z "$QDRANT_BIN" ]; then
            echo "[WARNING] Qdrant not found. Composition analysis will not work." >&2
            echo "  Download: https://github.com/qdrant/qdrant/releases" >&2
            echo "  Install:  sudo apt install qdrant (Ubuntu) or download binary" >&2
        else
            echo "[Qdrant] Starting Qdrant ..."
            mkdir -p "$BACKEND_DIR/qdrant_bin/qdrant_storage"
            if [ -f "$BACKEND_DIR/qdrant_bin/config.yaml" ]; then
                nohup "$QDRANT_BIN" --config-path "$BACKEND_DIR/qdrant_bin/config.yaml" --disable-telemetry \
                    > "$BACKEND_DIR/qdrant.log" 2>&1 &
            else
                nohup "$QDRANT_BIN" --disable-telemetry \
                    > "$BACKEND_DIR/qdrant.log" 2>&1 &
            fi
            echo "$!" > "$BACKEND_DIR/qdrant.pid"
            sleep 5
            if curl -s "http://localhost:$QDRANT_PORT/collections" >/dev/null 2>&1; then
                echo "[Qdrant] Started (port $QDRANT_PORT)"
                echo "[Qdrant] Dashboard: http://localhost:$QDRANT_PORT/dashboard"
            else
                echo "[WARNING] Qdrant may still be starting. Check: $BACKEND_DIR/qdrant.log" >&2
            fi
        fi
    fi
else
    echo "[1/4] Skip Qdrant"
fi

echo ""

# ========== 2. Redis ==========
if [ "$SKIP_REDIS" = false ]; then
    echo "[2/4] Checking Redis ..."
    if redis-cli -p "$REDIS_PORT" ping 2>/dev/null | grep -q PONG; then
        echo "[Redis] Already running (port $REDIS_PORT)"
    else
        # Try system Redis
        if command -v redis-server &>/dev/null; then
            echo "[Redis] Starting Redis ..."
            redis-server --port "$REDIS_PORT" --daemonize yes --maxmemory 256mb --maxmemory-policy allkeys-lru
            sleep 2
            if redis-cli -p "$REDIS_PORT" ping 2>/dev/null | grep -q PONG; then
                echo "[Redis] 启动成功 (端口 $REDIS_PORT)"
            else
                echo "[错误] Redis 启动失败。请先安装: sudo apt install redis-server (Ubuntu) 或 brew install redis (macOS)" >&2
                exit 1
            fi
        else
            echo "[错误] 未找到 redis-server。请先安装 Redis:" >&2
            echo "  Ubuntu: sudo apt install redis-server" >&2
            echo "  macOS:  brew install redis" >&2
            exit 1
        fi
    fi
else
    echo "[2/4] Skip Redis"
fi

echo ""

# ========== 3. Celery Worker ==========
if [ "$SKIP_CELERY" = false ]; then
    echo "[3/4] Starting Celery Worker ..."
    # 终止旧 Worker
    pkill -f "celery.*app.core.celery_app.*worker" 2>/dev/null || true
    sleep 1

    cd "$BACKEND_DIR"
    nohup $PYTHON -m celery -A app.core.celery_app worker \
        --loglevel=info \
        --pool=prefork \
        --logfile="$BACKEND_DIR/celery_worker.log" \
        --pidfile="$BACKEND_DIR/celery_worker.pid" \
        2>&1 &
    echo "$!" > "$BACKEND_DIR/celery_worker.pid"
    sleep 2
    if kill -0 "$(cat "$BACKEND_DIR/celery_worker.pid" 2>/dev/null)" 2>/dev/null; then
        echo "[Celery] Worker 启动成功 (PID: $(cat "$BACKEND_DIR/celery_worker.pid"))"
        echo "[Celery] 日志: $BACKEND_DIR/celery_worker.log"
    else
        echo "[错误] Celery Worker 启动失败，查看日志: $BACKEND_DIR/celery_worker.log" >&2
        exit 1
    fi
else
    echo "[3/4] Skip Celery Worker"
fi

echo ""

# ========== 4. FastAPI ==========
if [ "$SKIP_FASTAPI" = false ]; then
    echo "[4/4] Starting FastAPI backend ..."
    # 终止旧进程
    if lsof -ti ":$API_PORT" &>/dev/null; then
        kill "$(lsof -ti ":$API_PORT")" 2>/dev/null || true
        sleep 2
    fi

    cd "$BACKEND_DIR"
    nohup $PYTHON -m uvicorn app.main:app \
        --host 0.0.0.0 --port "$API_PORT" \
        --log-level info \
        --logfile="$BACKEND_DIR/fastapi.log" \
        --pidfile="$BACKEND_DIR/fastapi.pid" \
        2>&1 &
    echo "$!" > "$BACKEND_DIR/fastapi.pid"
    sleep 3
    if curl -s "http://localhost:$API_PORT/docs" >/dev/null 2>&1; then
        echo "[FastAPI] 后端启动成功 (端口 $API_PORT)"
    else
        echo "[FastAPI] 后端可能启动中，稍等片刻后访问 http://localhost:$API_PORT/docs" >&2
    fi
else
    echo "[4/4] Skip FastAPI"
fi

echo ""
echo "══════════════════════════════════════════════"
echo "  All services started!"
echo ""
echo "  Qdrant:      http://localhost:$QDRANT_PORT/dashboard"
echo "  Redis:       localhost:$REDIS_PORT"
echo "  Celery:     PID $(cat "$BACKEND_DIR/celery_worker.pid" 2>/dev/null || echo 'N/A')"
echo "  FastAPI:     http://localhost:$API_PORT"
echo "  API Docs:    http://localhost:$API_PORT/docs"
echo ""
echo "  Stop:        ./stop_all.sh"
echo "══════════════════════════════════════════════"
