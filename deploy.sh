#!/bin/bash
# 用法:
#   bash deploy.sh            完整部署（前端+后端，代码热挂载仅 restart）
#   bash deploy.sh --rebuild  完整部署 + Docker 重构（改 pip 包时用）
#   bash deploy.sh fast       仅前端（跳过后端）
#
# 后端代码通过 SCP 传到服务器后 mount 进容器，只需 restart 不需 rebuild
# 只有改 Python 依赖（requirements/Dockerfile）时才需要 --rebuild

set -o pipefail
cd "$(dirname "$0")" || exit 1

MODE="${1:-full}"  # fast | full | --rebuild

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
  echo "=== 🚀 fast 模式：仅前端 ==="
  ssh xcx "sudo docker compose -f /opt/calligraphy-recognition/deploy/docker-compose.yml restart nginx"
  echo "✅ 完成"
  exit 0
fi

echo ""
echo "=== 4. 同步后端源码 → 服务器 ==="
tar cz --exclude='data' --exclude='__pycache__' --exclude='*.pyc' --exclude='.env' -C backend . \
  | ssh xcx "sudo tar xz -C /opt/calligraphy-recognition/backend"

echo ""
echo "=== 5. 重启后端 ==="
if [ "$MODE" = "--rebuild" ]; then
  echo "（--rebuild 模式，完整 Docker 重构）"
  ssh xcx "sudo docker compose -f /opt/calligraphy-recognition/deploy/docker-compose.yml up -d --build backend" || exit 1
else
  ssh xcx "sudo docker compose -f /opt/calligraphy-recognition/deploy/docker-compose.yml restart backend"
fi

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
