#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# molin-wiki 一键部署脚本
# 首次运行:  bash deploy.sh init
# 后续更新:  bash deploy.sh update
# ============================================================

DOMAIN="${DOMAIN:-zhouhouhan.com}"
REPO_URL="https://github.com/zaxchou/molin-wiki.git"
APP_DIR="/opt/molin-wiki"

# ─── 安装 Docker ────────────────────────────────────────────
install_docker() {
    echo "=== 安装 Docker ==="
    if command -v docker &>/dev/null; then
        echo "Docker 已安装: $(docker --version)"
        return
    fi
    sudo apt-get update -qq
    sudo apt-get install -y -qq ca-certificates curl
    sudo install -m 0755 -d /etc/apt/keyrings
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update -qq
    sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    sudo usermod -aG docker "$USER"
    echo "Docker 安装完成，如果 docker 命令不可用请重新登录"
}

# ─── 克隆代码 ────────────────────────────────────────────────
clone_code() {
    if [ -d "$APP_DIR/.git" ]; then
        echo "代码已存在: $APP_DIR"
    else
        echo "=== 克隆代码 ==="
        sudo mkdir -p "$APP_DIR"
        sudo chown "$USER:$USER" "$APP_DIR"
        git clone "$REPO_URL" "$APP_DIR"
    fi
}

# ─── 申请 SSL 证书 (certbot standalone) ──────────────────────
setup_ssl() {
    echo "=== 申请 SSL 证书 ==="
    if sudo [ -d "/etc/letsencrypt/live/$DOMAIN" ]; then
        echo "SSL 证书已存在"
        return
    fi
    # 临时停 nginx 释放 80 端口
    cd "$APP_DIR/deploy"
    sudo docker compose stop nginx 2>/dev/null || true
    sudo apt-get install -y -qq certbot
    sudo certbot certonly --standalone \
        -d "$DOMAIN" \
        --agree-tos --non-interactive \
        --email "admin@$DOMAIN"
    echo "SSL 证书申请完成"
}

# ─── 初始化 ──────────────────────────────────────────────────
do_init() {
    echo "=============================================="
    echo "  molin-wiki 首次部署"
    echo "=============================================="

    install_docker
    clone_code
    cd "$APP_DIR/deploy"

    # 先申请 SSL（需要 80 端口空闲）
    setup_ssl

    # 构建并启动全部服务
    echo "=== 构建 Docker 镜像 (首次较慢，约 5-10 分钟) ==="
    sudo docker compose build backend
    echo "=== 启动服务 ==="
    sudo docker compose up -d

    echo ""
    echo "=============================================="
    echo "  部署完成!"
    echo "  https://$DOMAIN"
    echo "=============================================="
    echo ""
    echo "后续更新代码: cd $APP_DIR/deploy && sudo docker compose up -d --build backend"
    echo "查看日志:     cd $APP_DIR/deploy && sudo docker compose logs -f backend"
}

# ─── 更新 ────────────────────────────────────────────────────
do_update() {
    echo "=== 拉取最新代码 ==="
    cd "$APP_DIR"
    git pull
    cd "$APP_DIR/deploy"
    echo "=== 重新构建并重启 backend ==="
    sudo docker compose up -d --build backend
    echo "更新完成"
}

# ─── 主入口 ──────────────────────────────────────────────────
case "${1:-}" in
    init)
        do_init
        ;;
    update)
        do_update
        ;;
    *)
        echo "用法: bash deploy.sh {init|update}"
        echo "  init   - 首次部署（安装Docker + 克隆代码 + SSL + 启动）"
        echo "  update - git pull + 重新构建部署"
        exit 1
        ;;
esac
