#!/bin/bash
# 一键推送 + 部署到腾讯云服务器
# 用法: bash deploy.sh
# 保险: 服务器 cron 每 5 分钟也会自动检查更新

set -o pipefail

cd "$(dirname "$0")" || exit 1

echo "=== 1. 推送到 GitHub ==="
git push origin master || { echo "推送失败"; exit 1; }

echo ""
echo "=== 2. 触发服务器部署 ==="
ssh xcx "cd /opt/calligraphy-recognition && sudo bash deploy/auto_deploy.sh" || {
  echo "部署命令执行失败，但代码已推送到 GitHub，服务器 cron 将在 5 分钟内自动部署"
  exit 1
}

echo ""
echo "=== ✅ 部署流程完成 ==="
