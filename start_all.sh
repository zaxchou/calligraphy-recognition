#!/usr/bin/env bash
# ============================================================
#  书法碑帖字体认证系统 - 一键启动 (Linux / macOS)
#  按顺序启动: Redis → Celery Worker → FastAPI 后端
#  用法:
#    chmod +x start_all.sh
#    ./start_all.sh                    # 启动全部
#    ./start_all.sh --skip-fastapi      # 只启动 Redis + Celery
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
REDIS_PORT=6379
API_PORT=8001
SKIP_REDIS=false
SKIP_CELERY=false
SKIP_FASTAPI=false

# 解析参数
for arg in "$@"; do
    case "$arg" in
        --skip-redis)      SKIP_REDIS=true ;;
        --skip-celery)     SKIP_CELERY=true ;;
        --skip-fastapi)    SKIP_FASTAPI=true ;;
        --help|-h)
            echo "用法: $0 [--skip-redis] [--skip-celery] [--skip-fastapi]"
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

# ========== 1. Redis ==========
if [ "$SKIP_REDIS" = false ]; then
    echo "[1/3] 检查 Redis ..."
    if redis-cli -p "$REDIS_PORT" ping 2>/dev/null | grep -q PONG; then
        echo "[Redis] 已在运行 (端口 $REDIS_PORT)"
    else
        # 尝试启动系统 Redis
        if command -v redis-server &>/dev/null; then
            echo "[Redis] 启动 Redis ..."
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
    echo "[1/3] 跳过 Redis"
fi

echo ""

# ========== 2. Celery Worker ==========
if [ "$SKIP_CELERY" = false ]; then
    echo "[2/3] 启动 Celery Worker ..."
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
    echo "[2/3] 跳过 Celery Worker"
fi

echo ""

# ========== 3. FastAPI ==========
if [ "$SKIP_FASTAPI" = false ]; then
    echo "[3/3] 启动 FastAPI 后端 ..."
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
    echo "[3/3] 跳过 FastAPI"
fi

echo ""
echo "══════════════════════════════════════════════"
echo "  所有服务已启动!"
echo ""
echo "  Redis:       localhost:$REDIS_PORT"
echo "  Celery:     PID $(cat "$BACKEND_DIR/celery_worker.pid" 2>/dev/null || echo 'N/A')"
echo "  FastAPI:     http://localhost:$API_PORT"
echo "  API 文档:    http://localhost:$API_PORT/docs"
echo ""
echo "  停止服务:    ./stop_all.sh"
echo "══════════════════════════════════════════════"
