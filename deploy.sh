#!/bin/bash
# 用法:
#   bash deploy.sh         完整部署（前端+后端）
#   bash deploy.sh fast    仅前端（跳过后端构建，小改动专用）
#
# SCP 直传，不依赖服务器 git pull（腾讯云连 GitHub 经常 TLS 超时）

set -o pipefail
cd "$(dirname "$0")" || exit 1

MODE="${1:-full}"  # fast | full

echo "=== 1. 推送到 GitHub ==="
git push origin master || echo "⚠️ 推送失败"

echo ""
echo "=== 2. 构建前端 ==="
(cd frontend && npm run build) || { echo "构建失败"; exit 1; }

echo ""
echo "=== 3. 同步前端 dist → 服务器 ==="
ssh xcx "sudo rm -rf /opt/calligraphy-recognition/frontend/dist && sudo mkdir -p /opt/calligraphy-recognition/frontend/dist && sudo chown ubuntu:ubuntu /opt/calligraphy-recognition/frontend/dist"
scp -qr frontend/dist/* xcx:/opt/calligraphy-recognition/frontend/dist/ || { echo "SCP 失败"; exit 1; }

if [ "$MODE" = "fast" ]; then
  echo ""
  echo "=== 🚀 fast 模式：仅更新前端，跳过后端 ==="
  ssh xcx "sudo docker compose -f /opt/calligraphy-recognition/deploy/docker-compose.yml restart nginx"
  echo "✅ 前端部署完成"
  exit 0
fi

echo ""
echo "=== 4. 同步后端源码 → 服务器 ==="
# 排除 data/（Docker volume 挂载）和缓存文件
tar cz --exclude='data' --exclude='__pycache__' --exclude='*.pyc' --exclude='.env' -C backend . | ssh xcx "sudo tar xz -C /opt/calligraphy-recognition/backend"
scp -q deploy/Dockerfile deploy/docker-compose.yml .dockerignore xcx:/opt/calligraphy-recognition/deploy/
# .dockerignore 放在项目根（Docker context 根）才生效
ssh xcx "sudo cp /opt/calligraphy-recognition/deploy/.dockerignore /opt/calligraphy-recognition/.dockerignore"

echo ""
echo "=== 5. 重构并重启后端 ==="
ssh xcx "sudo docker compose -f /opt/calligraphy-recognition/deploy/docker-compose.yml up -d --build backend" || { echo "后端构建失败"; exit 1; }

echo ""
echo "=== 6. 重启 nginx ==="
ssh xcx "sudo docker compose -f /opt/calligraphy-recognition/deploy/docker-compose.yml restart nginx"

echo ""
echo "=== 7. 健康检查 ==="
sleep 5
STATUS=$(ssh xcx "curl -s -o /dev/null -w '%{http_code}' http://localhost:8001/api/v1/tubi/results?limit=1" 2>/dev/null || echo "000")
if [ "$STATUS" = "200" ]; then
  echo "✅ 部署完成（$STATUS）"
else
  echo "⚠️  健康检查返回 $STATUS"
fi
