#!/bin/bash
# 干净方案：从 origin/master 重新 apply 代码，完全不碰大文件
cd "z:/BaiduSync/BaiduSyncdisk/calligraphy-recognition" || exit 1

echo "=== 1. 重置到 origin/master（硬重置，丢弃所有本地历史）==="
git reset --hard origin/master

echo "=== 2. 从原 commit 里 extract 代码改动（不含大文件）==="
# 只拿代码文件，不打大文件
git merge 20bf5da --no-commit --no-ff 2>/dev/null || true
# 如果 merge 冲突，abort
git merge --abort 2>/dev/null || true

# 改用 cherry-pick 拿代码（只拿 commit 差异，不含二进制大文件）
# 直接手动重新做改动更简单，我们先看看要改哪些文件
echo "=== 需要重新做的改动，参考原 commit 差异：==="
git diff origin/master..20bf5da --name-only | grep -v "annotated\|uploads\|static\|thumbnails\|ps1\|sh" | head -30

echo ""
echo "=== 请手动编辑这些文件，然后：==="
echo "git add <文件>"
echo 'git commit -m "feat: 印章管理系统 + 一致性修复 + TubiEditDialog"'
echo "git push origin master"
