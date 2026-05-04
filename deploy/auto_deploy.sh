#!/bin/bash
# 自动部署脚本：检查 GitHub 更新，如有则拉取并重建
# 用法: 放在 cron 中每 5 分钟执行一次
set -e

cd /opt/calligraphy-recognition || exit 1

# 记录上次检查的 commit
LAST_COMMIT_FILE="/tmp/.last_deploy_commit"
CURRENT=$(git rev-parse HEAD 2>/dev/null || echo "")

# 获取远程最新 commit
REMOTE=$(git ls-remote https://github.com/zaxchou/calligraphy-recognition.git master 2>/dev/null | awk '{print $1}' || echo "")

if [ -z "$REMOTE" ]; then
  echo "[$(date)] 无法获取远程版本"
  exit 1
fi

if [ "$CURRENT" = "$REMOTE" ]; then
  echo "[$(date)] 已是最新 ($CURRENT)"
  exit 0
fi

echo "[$(date)] 检测到更新: $CURRENT → $REMOTE"

# 拉取最新代码
git fetch origin master
git reset --hard origin/master

# 构建并重启后端
sudo docker compose -f deploy/docker-compose.yml up -d --build backend
sudo docker compose -f deploy/docker-compose.yml restart nginx

echo "[$(date)] 部署完成: $REMOTE"
