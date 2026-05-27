#!/usr/bin/env bash
set -e
# ============================================================
# molin-wiki 服务器初始化
# 在服务器上执行: bash /opt/molin-wiki/deploy/setup.sh
# ============================================================

cd "$(dirname "$0")"

export DOMAIN="${DOMAIN:-zhouhouhan.com}"

# ---- Fix Qdrant URL in .env ----
echo ">>> 1/5 配置环境变量"
sed -i 's|QDRANT_URL=http://localhost:6333|QDRANT_URL=http://qdrant:6333|' ../backend/.env
grep QDRANT_URL ../backend/.env

# ---- Start Qdrant first ----
echo ">>> 2/5 启动 Qdrant"
sudo docker compose up -d qdrant
sleep 3

# ---- Build backend image ----
echo ">>> 3/5 构建后端镜像 (5-10min)"
sudo docker compose build backend

# ---- SSL certificate ----
echo ">>> 4/5 申请 SSL 证书"
if sudo [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    echo "SSL 证书已存在，跳过"
else
    # Stop nginx if running, certbot needs port 80
    sudo docker compose stop nginx 2>/dev/null || true
    # Also kill any process on port 80
    sudo fuser -k 80/tcp 2>/dev/null || true
    sleep 1
    sudo certbot certonly --standalone \
        -d "$DOMAIN" \
        --agree-tos --non-interactive \
        --email "admin@$DOMAIN"
    echo "SSL 证书申请完成"
fi

# ---- Start all services ----
echo ">>> 5/5 启动全部服务"
sudo docker compose up -d
echo ""
echo "======================================"
echo "  部署完成!  https://$DOMAIN"
echo "======================================"
echo "  查看日志: sudo docker compose logs -f backend"
echo "  重新部署: cd /opt/molin-wiki/deploy && sudo docker compose up -d --build backend"
