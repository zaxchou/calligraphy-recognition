#!/bin/bash
# 在服务器上构建并部署前端

set -e

echo "=== 开始构建前端 ==="

# 进入项目目录
cd /volume1/web/calligraphy-recognition

# 进入前端目录
cd frontend

# 安装依赖（如果 node_modules 不存在）
if [ ! -d "node_modules" ]; then
    echo "安装依赖..."
    npm ci
fi

# 构建
echo "构建前端..."
npm run build

echo "=== 构建完成 ==="
echo "构建结果位于: $(pwd)/dist"
