#!/bin/bash
# ============================================================
#  molin-wiki + zi2anki 一键部署脚本
#  原则：全部走本地 SCP，GitHub 不参与部署（纯版本管理）
# ============================================================
#
# 用法:
#   bash deploy.sh                  — 部署两个项目（代码 + 文件）
#   bash deploy.sh wiki             — 仅部署 molin-wiki
#   bash deploy.sh anki             — 仅部署 zi2anki
#   bash deploy.sh wiki --full      — molin-wiki 全量（含数据库 + 全部文件）
#   bash deploy.sh anki --full      — zi2anki 全量（含 node_modules + uploads）
#
# 先决条件:
#   - npm、python3、scp 可用
#   - SSH 别名 xcx 已配置

set -o pipefail

SSH_HOST="xcx"

# molin-wiki 路径
WIKI_LOCAL="$(cd "$(dirname "$0")" && pwd)"
WIKI_REMOTE="/opt/molin-wiki"
WIKI_DATA="$WIKI_LOCAL/backend/data"

# zi2anki 路径
ANKI_LOCAL="E:/下载/春江花明月/calligraphy-memory"
ANKI_REMOTE="/opt/zi2anki"

TARGET="${1:-all}"
MODE="${2}"

# ============================================================
# 工具函数
# ============================================================

section() { echo ""; echo "====  $1  ===="; }

# tar 管道：本地目录 → 远程目录（排除 node_modules/.git）
tar_sync() {
  local src="$1" dst="$2" label="$3"
  echo "  → $label ..."
  ssh "$SSH_HOST" "mkdir -p $dst"
  tar czf - -C "$src" --exclude='node_modules' --exclude='.git' --exclude='__pycache__' . \
    | ssh "$SSH_HOST" "tar xzf - -C $dst" 2>/dev/null
  echo "    done"
}

# 远端执行
remote() { ssh "$SSH_HOST" "$@"; }

# ============================================================
# molin-wiki
# ============================================================

deploy_wiki_code() {
  section "molin-wiki: 代码"

  # 1. 前端构建（本地）
  echo "  → npm run build ..."
  cd "$WIKI_LOCAL/frontend" && npm run build 2>&1 | tail -2

  # 2. SCP 后端代码（排除 data/，数据走 --full 单独同步）
  tar czf - -C "$WIKI_LOCAL/backend" \
    --exclude='data' --exclude='__pycache__' --exclude='*.pyc' --exclude='.venv' --exclude='.venv-ci' \
    --exclude='.git' --exclude='node_modules' . \
    | ssh "$SSH_HOST" "mkdir -p $WIKI_REMOTE/backend && tar xzf - -C $WIKI_REMOTE/backend" 2>/dev/null
  echo "    done"

  # 3. SCP 前端 dist
  tar_sync "$WIKI_LOCAL/frontend/dist" "$WIKI_REMOTE/frontend/dist" "frontend/dist/"

  # 4. 重启
  echo "  → docker restart ..."
  remote "cd $WIKI_REMOTE/deploy && sudo docker compose restart backend 2>&1 | tail -1"
}

deploy_wiki_data() {
  section "molin-wiki: 数据文件"

  local dirs=(uploads dzi annotated thumbnails seals knowledge/books static)

  for d in "${dirs[@]}"; do
    if [ -d "$WIKI_DATA/$d" ]; then
      local count=$(find "$WIKI_DATA/$d" -type f 2>/dev/null | wc -l)
      echo "  → $d/ ($count 文件)"
      ssh "$SSH_HOST" "mkdir -p $WIKI_REMOTE/backend/data/$d"
      tar czf - -C "$WIKI_DATA/$d" . 2>/dev/null \
        | ssh "$SSH_HOST" "tar xzf - -C $WIKI_REMOTE/backend/data/$d" 2>/dev/null
    fi
  done
  echo "  done"
}

deploy_wiki_db() {
  section "molin-wiki: 数据库"

  for db in calligraphy.db knowledge.db; do
    if [ -f "$WIKI_DATA/$db" ]; then
      echo "  → $db ..."
      python3 -c "
import sqlite3
c=sqlite3.connect('$WIKI_DATA/$db')
c.execute('PRAGMA wal_checkpoint(TRUNCATE)')
c.close()
" 2>/dev/null
      scp -q "$WIKI_DATA/$db" "$SSH_HOST:$WIKI_REMOTE/backend/data/$db"
      # 清理服务器上的 WAL/SHM 残留（旧文件会导致 SQLite 误判或数据不一致）
      ssh "$SSH_HOST" "rm -f $WIKI_REMOTE/backend/data/$db-wal $WIKI_REMOTE/backend/data/$db-shm" 2>/dev/null
    fi
  done
  echo "  done"
}

deploy_wiki() {
  deploy_wiki_code
  if [ "$MODE" = "--full" ]; then
    deploy_wiki_db
    deploy_wiki_data
  fi
  section "molin-wiki: 健康检查"
  local wait=0 code=0
  while [ "$wait" -lt 30 ]; do
    code=$(remote "curl -s -o /dev/null -w '%{http_code}' http://localhost:8001/api/v1/site-settings" 2>/dev/null || echo "000")
    [ "$code" = "200" ] && break
    sleep 2
    wait=$((wait + 2))
  done
  echo "  HTTP $code"
}

# ============================================================
# zi2anki
# ============================================================

deploy_anki_code() {
  section "zi2anki: 代码"

  cd "$ANKI_LOCAL" || { echo "  ❌ $ANKI_LOCAL 不存在"; return 1; }

  # 1. 构建前端
  echo "  → npm run build ..."
  npm run build 2>&1 | tail -2

  # 2. SCP dist + server + package.json
  #    注意：server/data/ 包含 SQLite 数据库文件，必须排除！
  #    否则本地开发数据库会覆盖线上数据库，导致所有用户数据丢失
  tar_sync "$ANKI_LOCAL/dist" "$ANKI_REMOTE/dist" "dist/"
  echo "  → server/（排除 data/）..."
  ssh "$SSH_HOST" "mkdir -p $ANKI_REMOTE/server"
  tar czf - -C "$ANKI_LOCAL/server" \
    --exclude='node_modules' --exclude='.git' --exclude='__pycache__' --exclude='data' . \
    | ssh "$SSH_HOST" "tar xzf - -C $ANKI_REMOTE/server" 2>/dev/null
  echo "    done"
  scp -q "$ANKI_LOCAL/package.json" "$ANKI_LOCAL/package-lock.json" "$SSH_HOST:$ANKI_REMOTE/"

  # 3. 服务器侧 npm install（如果有新依赖）
  remote "cd $ANKI_REMOTE && npm install --omit=dev 2>&1 | tail -1"

  # 4. 重启
  echo "  → pm2 restart ..."
  remote "pm2 restart zi2anki 2>&1 | tail -2"
}

deploy_anki_data() {
  section "zi2anki: 数据文件"
  cd "$ANKI_LOCAL" || return 1

  if [ -d "uploads" ]; then
    local count=$(find uploads -type f 2>/dev/null | wc -l)
    echo "  → uploads/ ($count 文件)"
    tar_sync "$ANKI_LOCAL/uploads" "$ANKI_REMOTE/uploads" "uploads/"
  fi
}

deploy_anki_db() {
  section "zi2anki: 数据库（本地 → 线上）"

  local dump="/tmp/zi2anki-pg-dump.sql"
  local remote_dump="/tmp/zi2anki-pg-dump.sql"

  # 1. 本地 PG dump（Windows 用 PGPASSWORD）
  echo "  → pg_dump from local ..."
  PGPASSWORD=zi2anki_pg_2026 \
  "C:/Program Files/PostgreSQL/16/bin/pg_dump" \
    -h localhost -U zi2anki --no-owner --no-acl \
    --column-inserts --data-only \
    zi2anki > "$dump" 2>&1
  echo "    done ($(wc -c < "$dump") bytes)"

  # 2. SCP 到服务器
  echo "  → scp to server ..."
  scp -q "$dump" "$SSH_HOST:$remote_dump"

  # 3. 恢复
  #    先清空线上数据（保留表结构），再导入
  echo "  → restoring on production PG ..."
  ssh "$SSH_HOST" \
    "PGPASSWORD=zi2anki_pg_2026 psql -h localhost -U zi2anki -d zi2anki <<'SQL'
$(cat <<'SQLEOF'
-- 清空旧数据（保留表结构）
TRUNCATE cards, daily_stats, decks, marketplace_decks, study_sessions,
          user_card_progress, user_subscriptions, users RESTART IDENTITY CASCADE;
SQLEOF
)
"
  ssh "$SSH_HOST" "PGPASSWORD=zi2anki_pg_2026 psql -h localhost -U zi2anki -d zi2anki -f $remote_dump" 2>&1 | tail -3

  # 4. 重新 align admin UUID（加载后 admin 的 UUID 与本地一致，不影响）
  echo "  → fixing subscriptions ..."
  ssh "$SSH_HOST" \
    "PGPASSWORD=zi2anki_pg_2026 psql -h localhost -U zi2anki -d zi2anki <<'SQL'
$(cat <<'SQLEOF'
INSERT INTO user_subscriptions (user_id, deck_id, subscribed_at)
SELECT u.id, d.id, NOW()
FROM users u, decks d
WHERE u.username='admin' AND d.user_id = u.id
ON CONFLICT DO NOTHING;
SQLEOF
)
"

  # 5. 重启应用
  echo "  → pm2 restart ..."
  remote "pm2 restart zi2anki 2>&1 | tail -2"

  # 6. 清理
  rm -f "$dump"
  ssh "$SSH_HOST" "rm -f $remote_dump"
  echo "  ✅ 数据库同步完成"
}

deploy_anki_full() {
  section "zi2anki: 完整部署（含 node_modules）"
  cd "$ANKI_LOCAL" || { echo "  ❌ $ANKI_LOCAL 不存在"; return 1; }

  echo "  → npm install ..."
  npm install 2>&1 | tail -2
  echo "  → npm run build ..."
  npm run build 2>&1 | tail -2

  tar_sync "$ANKI_LOCAL" "$ANKI_REMOTE" "全部文件"
  remote "cd $ANKI_REMOTE && pm2 restart zi2anki 2>&1 | tail -2"
}

deploy_anki() {
  if [ "$MODE" = "--full" ]; then
    deploy_anki_full
  elif [ "$MODE" = "--sync" ]; then
    deploy_anki_code
    deploy_anki_data
    deploy_anki_db
  else
    deploy_anki_code
    deploy_anki_data
  fi
  section "zi2anki: 验证"
  remote "curl -s -o /dev/null -w '%{http_code}' http://localhost:3001/" \
    | xargs -I{} echo "  HTTP {}"
}

# ============================================================
# 主入口
# ============================================================

echo "========================================"
echo "  deploy.sh — SCP only, no GitHub"
echo "========================================"

case "$TARGET" in
  wiki)  deploy_wiki ;;
  anki)  deploy_anki ;;
  all|*) deploy_wiki; deploy_anki ;;
esac

echo ""
echo "========================================"
echo "  ✅ 部署完成"
echo "  https://molin.wiki"
echo "  https://zi2anki.molin.wiki"
echo "========================================"
