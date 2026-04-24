"""
简单粗暴的方式修复 tubi.py 路由顺序问题
把通配符路由和手动标注路由移到文件最后
"""
import os

file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "api", "tubi.py")

with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# 找到需要移动的部分的开始和结束
# 1. 通配符路由开始标记：@router.get("/{id}")
# 2. 手动标注路由开始标记：@router.patch("/{id}/regions")
# 3. 册页管理 API 开始标记：# ── 册页管理 API ──

wildcard_start = -1
manual_patch_start = -1
album_api_start = -1

for i, line in enumerate(lines):
    if '@router.get("/{id}")' in line:
        wildcard_start = i
    if '@router.patch("/{id}/regions")' in line:
        manual_patch_start = i
    if '# ── 册页管理 API ──' in line:
        album_api_start = i

print(f"通配符路由起始行: {wildcard_start}")
print(f"手动标注路由起始行: {manual_patch_start}")
print(f"册页 API 起始行: {album_api_start}")

if wildcard_start == -1 or album_api_start == -1:
    print("错误：找不到关键标记")
    exit(1)

# 分割内容
# 部分1：从开头到通配符路由之前
part1 = lines[:wildcard_start]

# 部分2：通配符路由 + 手动标注路由（需要移到最后）
# 找到册页 API 开始之前的位置
part2 = lines[wildcard_start:album_api_start]

# 部分3：册页 API + 标签 API + 统计 API（需要留在通配符路由之前）
part3 = lines[album_api_start:]

# 重新组合：part1 + part3 + part2
new_lines = part1 + part3 + part2

# 写回文件
with open(file_path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("路由顺序已修复！")
print(f"  - 通配符路由和手动标注路由已移到文件最后")
print(f"  - 册页/标签/统计 API 现在在通配符路由之前")
