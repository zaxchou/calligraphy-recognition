#!/bin/bash
# 一键部署：自动检测变更，做最快的事
# 用法: bash deploy.sh

set -o pipefail
cd "$(dirname "$0")" || exit 1

echo "=== 1. 推送到 GitHub ==="
git push origin master || echo "⚠️ 推送失败"

# 检测改了哪些文件
CHANGED=$(git diff --name-only HEAD~1..HEAD 2>/dev/null || git diff --name-only HEAD@{1} HEAD 2>/dev/null || echo "")
HAS_BACKEND=$(echo "$CHANGED" | grep -c '^backend/' || true)
HAS_DEPLOY=$(echo "$CHANGED" | grep -c '^deploy/Dockerfile\|^deploy/docker-compose' || true)

echo ""
echo "=== 2. 构建前端 ==="
(cd frontend && npm run build) || { echo "构建失败"; exit 1; }

echo ""
echo "=== 3. 同步前端 dist → 服务器 ==="
ssh xcx "sudo rm -rf /opt/calligraphy-recognition/frontend/dist && sudo mkdir -p /opt/calligraphy-recognition/frontend/dist && sudo chown ubuntu:ubuntu /opt/calligraphy-recognition/frontend/dist"
scp -qr frontend/dist/* xcx:/opt/calligraphy-recognition/frontend/dist/

if [ "$HAS_BACKEND" -gt 0 ]; then
  echo ""
  echo "=== 4. 检测到后端变更，同步源码 ==="
  tar cz --exclude='data' --exclude='__pycache__' --exclude='*.pyc' --exclude='.env' -C backend . \
    | ssh xcx "sudo tar xz -C /opt/calligraphy-recognition/backend"
  # 始终同步 deploy 配置（docker-compose.yml 有代码 volume 挂载，不更新则容器读不到新代码）
  scp -q deploy/Dockerfile deploy/docker-compose.yml xcx:/opt/calligraphy-recognition/deploy/

  if [ "$HAS_DEPLOY" -gt 0 ]; then
    echo "（检测到 Dockerfile/docker-compose 变更 → 完整重构）"
    ssh xcx "sudo docker compose -f /opt/calligraphy-recognition/deploy/docker-compose.yml up -d --build backend"
  else
    echo "（仅源码变更 → 快速 restart）"
    ssh xcx "sudo docker compose -f /opt/calligraphy-recognition/deploy/docker-compose.yml restart backend"
  fi
else
  echo ""
  echo "=== 4. 无后端变更，跳过 ==="
fi

echo ""
echo "=== 5. 重启 nginx ==="
ssh xcx "sudo docker compose -f /opt/calligraphy-recognition/deploy/docker-compose.yml restart nginx"

echo ""
echo "=== 6. 健康检查 ==="
sleep 5
STATUS=$(ssh xcx "curl -s -o /dev/null -w '%{http_code}' http://localhost:8001/api/v1/tubi/results?limit=1" 2>/dev/null || echo "000")
echo "$([ "$STATUS" = "200" ] && echo "✅ 部署完成" || echo "⚠️  健康检查返回 $STATUS")"
