#!/bin/bash
# 一键推送 + SCP 部署到腾讯云服务器
# 用法: bash deploy.sh
#
# 用 SCP 而非服务器 git pull，避免腾讯云连 GitHub 超时问题
# 保险: 服务器 cron 每 5 分钟仍会尝试 git pull

set -o pipefail

cd "$(dirname "$0")" || exit 1

echo "=== 1. 推送到 GitHub（备份代码） ==="
git push origin master || echo "⚠️ 推送失败，继续部署（本地代码仍可用）"

echo ""
echo "=== 2. 构建前端 ==="
cd frontend
if npm run build; then
  echo "前端构建成功"
else
  echo "前端构建失败，中止部署"
  exit 1
fi
cd "$OLDPWD" || exit 1

echo ""
echo "=== 3. SCP 前端 dist → 服务器 ==="
ssh xcx "sudo rm -rf /opt/calligraphy-recognition/frontend/dist && sudo mkdir -p /opt/calligraphy-recognition/frontend/dist && sudo chown ubuntu:ubuntu /opt/calligraphy-recognition/frontend/dist"
scp -r frontend/dist/* xcx:/opt/calligraphy-recognition/frontend/dist/ || {
  echo "前端 SCP 失败，中止部署"
  exit 1
}

echo ""
echo "=== 4. SCP 后端源码 → 服务器 ==="
# 排除 data/ 目录（数据在 Docker volume 里）
rsync -a --delete --exclude='data/' --exclude='__pycache__/' --exclude='*.pyc' --exclude='.env' backend/ xcx:/opt/calligraphy-recognition/backend/ 2>/dev/null || {
  echo "rsync 不可用，改用 tar+ssh"
  tar cz --exclude='data' --exclude='__pycache__' --exclude='*.pyc' --exclude='.env' -C backend . | ssh xcx "sudo tar xz -C /opt/calligraphy-recognition/backend" || {
    echo "后端 SCP 失败，中止部署"
    exit 1
  }
}
# 同步 deploy 目录（Dockerfile、docker-compose 等）
scp deploy/Dockerfile deploy/docker-compose.yml xcx:/opt/calligraphy-recognition/deploy/ || {
  echo "deploy 配置文件同步失败"
  exit 1
}

echo ""
echo "=== 5. 服务器：构建并重启后端 ==="
ssh xcx "sudo docker compose -f /opt/calligraphy-recognition/deploy/docker-compose.yml up -d --build backend" || {
  echo "后端构建/重启失败"
  exit 1
}

echo ""
echo "=== 6. 服务器：重启 nginx ==="
ssh xcx "sudo docker compose -f /opt/calligraphy-recognition/deploy/docker-compose.yml restart nginx"

echo ""
echo "=== 7. 健康检查 ==="
sleep 5
HEALTH=$(ssh xcx "curl -s -o /dev/null -w '%{http_code}' http://localhost:8001/api/v1/tubi/results?limit=1" 2>/dev/null || echo "000")
if [ "$HEALTH" = "200" ]; then
  echo "✅ 部署完成，后端健康检查通过 ($HEALTH)"
else
  echo "⚠️  后端健康检查返回 $HEALTH，请手动检查"
fi

echo ""
echo "=== ✅ deploy.sh 全部完成 ==="
