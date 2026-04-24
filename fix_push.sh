#!/bin/bash
# 重置到远程状态，重新只提交代码文件
cd "z:/BaiduSync/BaiduSyncdisk/calligraphy-recognition" || exit 1

echo "=== 重置到 origin/master ==="
git reset --hard origin/master

echo "=== 重新应用代码改动 ==="
# 从原分支拿代码改动（不拿大文件）
git merge --no-commit --no-ff 19c88c2 -- squash 2>/dev/null || true

# 确保 .gitignore 正确
git checkout HEAD -- .gitignore 2>/dev/null || true

# 取消暂存所有生成文件
git reset HEAD -- backend/data/annotated/ backend/data/uploads/ backend/data/static/ backend/data/thumbnails/ 2>/dev/null || true

echo "=== 状态 ==="
git status --short | head -30

echo "=== 提交 ==="
git commit -m "feat: 印章管理系统 + 一致性修复 + TubiEditDialog印章选择移植（已清理生成文件）" 2>/dev/null || echo "Nothing to commit"

echo "=== 推送 ==="
git push origin master

echo "=== 完成 ==="
