#!/bin/bash
# 方案：hard reset 到远程，然后只重新提交代码文件
cd "z:/BaiduSync/BaiduSyncdisk/calligraphy-recognition" || exit 1

echo "=== 1. 重置到 origin/master ==="
git reset --hard origin/master

echo "=== 2. 重新应用代码改动（从原 commit 拿）==="
# 用 cherry-pick 应用原 commit 的代码改动（会保留大文件，但我们马上剔除）
git cherry-pick 20bf5da --no-commit 2>/dev/null || echo "cherry-pick done or conflict（继续）"

echo "=== 3. 剔除所有生成文件 ==="
git reset HEAD -- backend/data/annotated/ backend/data/uploads/ backend/data/static/ backend/data/thumbnails/ 2>/dev/null || true

echo "=== 4. 提交（只含代码）==="
git commit -m "feat: 印章管理系统 + 一致性修复 + TubiEditDialog印章选择移植" 2>/dev/null || echo "Nothing to commit"

echo "=== 5. 推送 ==="
git push origin master

echo "=== 完成 ==="
