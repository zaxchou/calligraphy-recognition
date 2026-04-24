#!/bin/bash
# 干净方案：完全不碰历史，从 origin/master 重新 apply 代码改动
cd "z:/BaiduSync/BaiduSyncdisk/calligraphy-recognition" || exit 1

echo "=== 1. 硬重置到 origin/master（丢弃所有本地历史）==="
git reset --hard origin/master

echo "=== 2. 生成代码改动补丁（不含大文件）==="
# 对比原 4 个 commit 和 origin/master 的差异，只取代码文件
git diff origin/master..20bf5da --diff-filter=ACMR \
  -- backend/app/ backend/frontend/src/ backend/data/seals/ .gitignore backend/data/calligraphy.db \
  > /tmp/code_patch.patch 2>/dev/null || true

echo "=== 3. 应用补丁 ==="
git apply /tmp/code_patch.patch 2>/dev/null || echo "apply 可能有小冲突，手动处理"

echo "=== 4. 查看状态 ==="
git status --short | head -30

echo ""
echo "=== 5. 手动操作后：==="
echo "git add -A"
echo 'git commit -m "feat: 印章管理系统 + 一致性修复 + TubiEditDialog 印章选择移植"'
echo "git push origin master"
