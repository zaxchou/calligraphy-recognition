#!/bin/bash
# 一键重建干净仓库，只含代码，不含任何大文件
set -e

WORK_DIR="/z/BaiduSync/BaiduSyncdisk"
REPO="calligraphy-recognition"
REMOTE="https://github.com/zaxchou/calligraphy-recognition.git"

echo "=== 1. 备份当前代码改动（生成补丁）==="
cd "$WORK_DIR/$REPO" || exit 1
ORIG_HEAD=$(git rev-parse HEAD)
echo "Original HEAD: $ORIG_HEAD"

# 生成代码补丁（只含代码文件，不含数据文件）
git diff origin/master..$ORIG_HEAD \
  -- backend/app/ \
  -- backend/data/seals/ \
  -- backend/data/calligraphy.db \
  -- frontend/src/ \
  -- .gitignore \
  -- backend/app/api/ \
  > /tmp/code_patch.patch 2>/dev/null || true

PATCH_SIZE=$(wc -c < /tmp/code_patch.patch)
echo "Patch size: $PATCH_SIZE bytes"

echo "=== 2. 重新 clone 干净仓库 ==="
cd "$WORK_DIR" || exit 1
mv "$REPO" "${REPO}.bak"
git clone "$REMOTE" "$REPO"

echo "=== 3. 应用代码补丁 ==="
cd "$WORK_DIR/$REPO" || exit 1
git apply /tmp/code_patch.patch 2>&1 | head -20 || echo "补丁应用完成（可能有小冲突请手动处理）"

echo "=== 4. 查看状态 ==="
git status --short | head -30

echo ""
echo "=== 5. 请检查以上状态，确认无误后执行：==="
echo "git add -A"
echo 'git commit -m "feat: 印章管理系统 + 一致性修复 + TubiEditDialog 印章选择移植"'
echo "git push origin master"
echo ""
echo "旧目录已备份在 ${REPO}.bak，确认无误后可删除"
