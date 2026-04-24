#!/bin/bash
# 干净重置并只提交代码文件
cd "z:/BaiduSync/BaiduSyncdisk/calligraphy-recognition" || exit 1

ORIG_HEAD=$(git rev-parse HEAD)
echo "Original HEAD: $ORIG_HEAD"

echo "=== 1. 硬重置到 origin/master ==="
git reset --hard origin/master

echo "=== 2. 生成代码补丁（不含大文件）==="
git diff origin/master..$ORIG_HEAD \
  -- backend/app/ \
  -- frontend/src/ \
  -- backend/data/seals/ \
  -- .gitignore \
  > /tmp/code_patch.patch 2>/dev/null

PATCH_SIZE=$(wc -c < /tmp/code_patch.patch)
echo "Patch size: $PATCH_SIZE bytes"

echo "=== 3. 应用补丁 ==="
git apply /tmp/code_patch.patch 2>&1 | head -20

echo "=== 4. 状态 ==="
git status --short | head -30

echo "=== 5. 提交并推送 ==="
git add backend/app/ frontend/src/ backend/data/seals/ .gitignore 2>/dev/null
git diff --cached --quiet && echo "Nothing to commit" && exit 0
git commit -m "feat: 印章管理系统 + 一致性修复 + TubiEditDialog印章选择移植"
git push origin master

echo "=== 完成 ==="
