#!/bin/bash
# 自动部署脚本：检查 GitHub 更新，如有则拉取并重建前端+后端
# 用法: 放在 cron 中每 5 分钟执行一次
# 安全设计：git pull 失败不会影响当前运行的服务

set -o pipefail  # 管道中任一命令失败则整体失败（但不用 set -e）

cd /opt/calligraphy-recognition || { echo "[$(date)] 目录不存在"; exit 1; }

LOG_TAG="[auto_deploy]"
echo "$LOG_TAG [$(date)] 开始检查更新..."

# ── 1. 获取远程最新 commit ──────────────────────────────────
REMOTE=""
for i in 1 2 3; do
  REMOTE=$(git ls-remote https://github.com/zaxchou/calligraphy-recognition.git master 2>/dev/null | awk '{print $1}')
  if [ -n "$REMOTE" ]; then break; fi
  echo "$LOG_TAG 第 ${i} 次获取远程版本失败，3 秒后重试..."
  sleep 3
done

if [ -z "$REMOTE" ]; then
  echo "$LOG_TAG [$(date)] 无法获取远程版本（已重试 3 次），跳过本次检查"
  exit 0
fi

CURRENT=$(git rev-parse HEAD 2>/dev/null || echo "")

if [ "$CURRENT" = "$REMOTE" ]; then
  echo "$LOG_TAG [$(date)] 已是最新 ($CURRENT)"
  exit 0
fi

echo "$LOG_TAG [$(date)] 检测到更新: ${CURRENT:0:8} → ${REMOTE:0:8}"

# ── 2. 拉取最新代码 ──────────────────────────────────────────
if ! git fetch origin master; then
  echo "$LOG_TAG [$(date)] git fetch 失败，跳过本次部署"
  exit 0
fi

if ! git reset --hard origin/master; then
  echo "$LOG_TAG [$(date)] git reset 失败，跳过本次部署"
  exit 0
fi

echo "$LOG_TAG [$(date)] 代码已更新"

# ── 3. 构建前端 ──────────────────────────────────────────────
if [ -d "frontend" ]; then
  echo "$LOG_TAG [$(date)] 开始构建前端..."
  cd frontend
  if npm install --silent && npm run build; then
    echo "$LOG_TAG [$(date)] 前端构建成功"
  else
    echo "$LOG_TAG [$(date)] 前端构建失败，跳过前端更新"
  fi
  cd /opt/calligraphy-recognition
else
  echo "$LOG_TAG [$(date)] frontend 目录不存在，跳过前端构建"
fi

# ── 4. 构建并重启后端 ────────────────────────────────────────
echo "$LOG_TAG [$(date)] 开始构建后端..."
if sudo docker compose -f deploy/docker-compose.yml up -d --build backend; then
  echo "$LOG_TAG [$(date)] 后端构建成功"
else
  echo "$LOG_TAG [$(date)] 后端构建失败，跳过部署"
  exit 0
fi

# ── 5. 重启 nginx ────────────────────────────────────────────
echo "$LOG_TAG [$(date)] 重启 nginx..."
sudo docker compose -f deploy/docker-compose.yml restart nginx

# ── 6. 健康检查 ──────────────────────────────────────────────
sleep 5
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/api/v1/tubi/results?limit=1 2>/dev/null || echo "000")
if [ "$HEALTH" = "200" ]; then
  echo "$LOG_TAG [$(date)] ✅ 部署完成，后端健康检查通过 ($HEALTH)"
else
  echo "$LOG_TAG [$(date)] ⚠️  后端健康检查返回 $HEALTH，请手动检查"
fi

echo "$LOG_TAG [$(date)] 部署结束: ${REMOTE:0:8}"
