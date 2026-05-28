#!/bin/bash
# 墨林百科 一键部署脚本
# 从本地 Windows 执行，自动检测变更并做最快的部署
#
# 用法:
#   bash deploy.sh             — 完整部署（自动检测代码/数据库/文件变更）
#   bash deploy.sh code        — 仅部署程序文件（git push + 构建 + 重启）
#   bash deploy.sh full        — 强制全量部署（含数据库+全部文件同步）
#
# 先决条件:
#   - Git、npm、python3、scp 可用
#   - SSH 别名 xcx 已配置（~/.ssh/config）
#   - 当前工作目录 = 项目根目录

set -o pipefail
cd "$(dirname "$0")" || exit 1

PROJECT="molin-wiki"
SSH_HOST="xcx"
REMOTE_DIR="/opt/$PROJECT"
LOCAL_DATA="backend/data"
REMOTE_DATA="$REMOTE_DIR/backend/data"

# ============================================================
# 工具函数
# ============================================================

section() {
  echo ""
  echo "================================================"
  echo "  $1"
  echo "================================================"
}

check_dep() {
  if ! command -v "$1" &>/dev/null; then
    echo "❌ 缺少依赖: $1，请先安装"
    exit 1
  fi
}

# SQLite WAL checkpoint：确保 -wal 中的修改已写入主文件
checkpoint_db() {
  local db_path="$1"
  local label="$2"
  if [ -f "$db_path" ]; then
    python3 -c "
import sqlite3
c = sqlite3.connect('$db_path')
c.execute('PRAGMA wal_checkpoint(TRUNCATE)')
c.close()
print('  ✔ $label 已 checkpoint')
"
  fi
}

# 验证推荐艺术家（判断数据库是否完整）
verify_featured_artists() {
  local db_path="$1"
  python3 -c "
import sqlite3
c = sqlite3.connect('$db_path')
r = c.execute('SELECT name FROM artists WHERE featured=1').fetchall()
c.close()
print(f'  推荐艺术家: {len(r)} 位: ' + ', '.join(x[0] for x in r))
if len(r) < 5:
  print('  ⚠️  只有 ' + str(len(r)) + ' 位，可能缺 WAL 修改')
  exit(1)
" 2>&1 || {
    echo "  ⚠️  推荐艺术家少于 5 位，是否漏了 checkpoint？继续部署但请注意"
  }
}

# SSH 远程执行
remote() {
  ssh "$SSH_HOST" "$@"
}

# 健康检查
health_check() {
  local port="${1:-8001}"
  local label="${2:-后端}"
  sleep 3
  local code
  code=$(remote "curl -s -o /dev/null -w '%{http_code}' http://localhost:$port/api/v1/site-settings" 2>/dev/null || echo "000")
  if [ "$code" = "200" ]; then
    echo "  ✅ $label 健康检查通过 (HTTP $code)"
    return 0
  else
    echo "  ⚠️  $label 健康检查返回 $code"
    return 1
  fi
}

# ============================================================
# 子流程
# ============================================================

do_git_push() {
  section "1. 推送到 GitHub（仅程序文件）"
  # 仅添加程序源码变更，不包含数据文件
  git add --update
  git add backend/app/ backend/scripts/ backend/requirements.txt frontend/src/ deploy.sh
  if git diff --cached --quiet; then
    echo "  无变更，跳过提交"
  else
    # 提示输入 commit message
    echo -n "  请输入 commit 信息（直接回车用自动信息）: "
    read -r msg
    if [ -z "$msg" ]; then
      msg="deploy: $(date +%Y-%m-%d\ %H:%M)"
    fi
    git commit -m "$msg"
    git push origin master || echo "  ⚠️  推送失败，请检查网络"
  fi
}

do_remote_code_sync() {
  section "2. 服务器拉取代码 + 构建前端"
  remote "
    cd $REMOTE_DIR
    git reset --hard origin/master 2>/dev/null
    git pull origin master
    cd frontend && npm run build 2>&1 | tail -3
  " || {
    echo "  ❌ 远程同步/构建失败"
    exit 1
  }
  echo "  ✔ 代码同步 + 前端构建完成"
}

do_stop_backend() {
  section "3. 停服"
  remote "sudo kill -9 \$(pgrep -f uvicorn) 2>/dev/null; echo '  ✔ 后端已停止'"
}

do_sync_databases() {
  section "4. 同步数据库"

  # 先强制 checkpoint 确保 WAL 合并
  echo "  → 检查本地 SQLite WAL..."
  checkpoint_db "$LOCAL_DATA/calligraphy.db" "calligraphy.db"
  checkpoint_db "$LOCAL_DATA/knowledge.db" "knowledge.db"

  # 验证数据库完整性
  echo "  → 验证本地数据库..."
  verify_featured_artists "$LOCAL_DATA/calligraphy.db"

  # 删除远程旧库（含残留 -wal/-shm）
  echo "  → 清理远程旧数据库..."
  remote "rm -f $REMOTE_DATA/calligraphy.db $REMOTE_DATA/calligraphy.db-shm $REMOTE_DATA/calligraphy.db-wal $REMOTE_DATA/knowledge.db $REMOTE_DATA/knowledge.db-shm $REMOTE_DATA/knowledge.db-wal"

  # 传输新库
  echo "  → 传输 calligraphy.db..."
  scp "$LOCAL_DATA/calligraphy.db" "$SSH_HOST:$REMOTE_DATA/calligraphy.db"

  echo "  → 传输 knowledge.db..."
  scp "$LOCAL_DATA/knowledge.db" "$SSH_HOST:$REMOTE_DATA/knowledge.db"

  # 验证 MD5
  echo "  → 验证传输一致性..."
  local md5_local md5_remote
  md5_local=$(python3 -c "import hashlib; print(hashlib.md5(open('$LOCAL_DATA/calligraphy.db','rb').read()).hexdigest())")
  md5_remote=$(remote "md5sum $REMOTE_DATA/calligraphy.db" | awk '{print $1}')
  if [ "$md5_local" = "$md5_remote" ]; then
    echo "  ✔ calligraphy.db MD5 一致"
  else
    echo "  ❌ calligraphy.db MD5 不一致！($md5_local vs $md5_remote)"
    exit 1
  fi
}

do_sync_files() {
  section "5. 同步静态文件目录"

  local dirs=(
    "seals/*.jpeg:seals/"
    "seals/thumbs/*.jpg:seals/thumbs/"
    "uploads/avatar_*:uploads/"
    "uploads/photo_*:uploads/"
  )

  for entry in "${dirs[@]}"; do
    local pattern="${entry%%:*}"
    local target="${entry##*:}"
    local src="$LOCAL_DATA/$pattern"

    # 检查是否有文件匹配
    local count
    count=$(ls -1 $src 2>/dev/null | wc -l)
    if [ "$count" -gt 0 ]; then
      echo "  → 同步 $target ($count 文件)..."
      remote "mkdir -p $REMOTE_DATA/$target"
      # 用 find + glob 传文件，用 -q 静默
      scp -q $src "$SSH_HOST:$REMOTE_DATA/$target" 2>/dev/null
    fi
  done

  # 同步后核对数量
  echo ""
  echo "  ── 文件数量核对 ──"
  echo "  本地 印章:    $(ls -1 $LOCAL_DATA/seals/*.jpeg 2>/dev/null | wc -l) jpeg"
  echo "  远程 印章:    $(remote \"ls $REMOTE_DATA/seals/*.jpeg 2>/dev/null | wc -l\") jpeg"
  echo "  本地 头像:    $(ls -1 $LOCAL_DATA/uploads/avatar_* 2>/dev/null | wc -l)"
  echo "  远程 头像:    $(remote \"ls $REMOTE_DATA/uploads/avatar_* 2>/dev/null | wc -l\")"
}

do_start_backend() {
  section "6. 重启后端"
  remote "
    cd $REMOTE_DIR/backend
    PYTHONPATH=$REMOTE_DIR/backend nohup /usr/local/bin/python3.12 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 > $REMOTE_DIR/backend/server.log 2>&1 &
    disown
  " && echo "  ✔ 后端已启动（等待就绪...）"
}

do_verify() {
  section "7. 健康检查"

  # 等待后端启动（最多等 30 秒）
  local wait=0
  while [ "$wait" -lt 30 ]; do
    health_check 8001 && break
    sleep 3
    wait=$((wait + 3))
  done

  if [ "$wait" -ge 30 ]; then
    echo "  ❌ 后端启动超时，请检查远程日志:"
    echo "     ssh xcx \"tail -30 $REMOTE_DIR/backend/server.log\""
    exit 1
  fi

  echo ""
  echo "  ── API 验证 ──"
  remote "curl -s http://localhost:8001/api/v1/artists?featured=1" | python3 -c "
import sys, json
d = json.load(sys.stdin)
artists = d.get('artists', [])
print(f'  推荐艺术家: {len(artists)} 位')
for a in artists:
    print(f'    - {a[\"name\"]}')
" 2>/dev/null || echo "  ⚠️  推荐艺术家 API 异常"

  local seal_count
  seal_count=$(remote "curl -s http://localhost:8001/api/v1/seals" | python3 -c "import sys,json; print(json.load(sys.stdin).get('total', '?'))" 2>/dev/null || echo "?")
  echo "  印章总数: $seal_count"
}

# ============================================================
# 主流程
# ============================================================

# 依赖检查
check_dep git
check_dep npm
check_dep python3
check_dep scp

MODE="${1:-auto}"

case "$MODE" in
  code)
    # 仅代码部署
    do_git_push
    do_remote_code_sync
    do_stop_backend
    do_start_backend
    do_verify
    ;;
  full)
    # 强制全量部署
    do_git_push
    do_remote_code_sync
    do_stop_backend
    do_sync_databases
    do_sync_files
    do_start_backend
    do_verify
    ;;
  auto|*)
    # 自动模式：检测变更范围
    section "🔍 自动检测部署范围"

    # 检查本地是否有未提交的 db 或文件变更
    local db_changed=0
    local file_changed=0
    local code_changed=0

    if git status --porcelain "$LOCAL_DATA/" 2>/dev/null | grep -q .; then
      db_changed=1
    fi
    # 检查最近一次 commit 是否含 data/ 变更
    if git diff --name-only HEAD~1..HEAD 2>/dev/null | grep -q "^backend/data/"; then
      db_changed=1
    fi
    # 检查文件数量是否变化
    local local_jpeg remote_jpeg
    local_jpeg=$(ls -1 "$LOCAL_DATA/seals/"*.jpeg 2>/dev/null | wc -l)
    remote_jpeg=$(remote "ls $REMOTE_DATA/seals/*.jpeg 2>/dev/null | wc -l" 2>/dev/null || echo "0")
    if [ "$local_jpeg" -ne "$remote_jpeg" ] 2>/dev/null; then
      file_changed=1
    fi
    local local_avatars remote_avatars
    local_avatars=$(ls -1 "$LOCAL_DATA/uploads/avatar_"* 2>/dev/null | wc -l)
    remote_avatars=$(remote "ls $REMOTE_DATA/uploads/avatar_* 2>/dev/null | wc -l" 2>/dev/null || echo "0")
    if [ "$local_avatars" -ne "$remote_avatars" ] 2>/dev/null; then
      file_changed=1
    fi

    echo "  检测结果:"
    echo "    代码变更: 是（默认含 git push）"
    echo "    数据库变更: $([ "$db_changed" = 1 ] && echo '是' || echo '否')"
    echo "    静态文件变更: $([ "$file_changed" = 1 ] && echo '是' || echo '否')"

    # 执行流程
    do_git_push
    do_remote_code_sync
    do_stop_backend
    [ "$db_changed" = 1 ] && do_sync_databases
    [ "$file_changed" = 1 ] && do_sync_files
    do_start_backend
    do_verify

    echo ""
    echo "================================================"
    echo "  ✅ 部署完成"
    echo "  https://124.223.17.29"
    echo "================================================"
    ;;
esac
