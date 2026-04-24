#!/bin/bash
# 根本方案：重新 clone 干净仓库，只复制代码，完全不碰大文件
cd /z/BaiduSync/BaiduSyncdisk/ || exit 1

echo "=== 1. 备份当前代码改动 ==="
# 保存当前 4 个 commit 的代码差异
git diff origin/master..HEAD \
  -- backend/app/ \
  -- frontend/src/ \
  -- backend/data/seals/ \
  -- .gitignore \
  -- backend/data/calligraphy.db \
  > /tmp/code_patch.patch

PATCH_SIZE=$(wc -c < /tmp/code_patch.patch)
echo "Patch size: $PATCH_SIZE bytes"

echo "=== 2. 重新 clone ==="
cd /z/BaiduSync/BaiduSyncdisk/ || exit 1
mv calligraphy-recognition calligraphy-recognition.bak
git clone https://github.com/你的用户名/calligraphy-recognition.git
# 如果上面 URL 不对，手动改

echo "=== 3. 应用代码补丁 ==="
cd calligraphy-recognition || exit 1
git apply /tmp/code_patch.patch 2>&1 | head -20

echo "=== 4. 提交并推送 ==="
git add backend/app/ frontend/src/ backend/data/seals/ .gitignore backend/data/calligraphy.db
git commit -m "feat: 印章管理系统 + 一致性修复 + TubiEditDialog印章选择移植"
git push origin master

echo "=== 完成！以后 push 就快了 ==="
echo "旧目录已备份在 calligraphy-recognition.bak，确认无误后可删除"
