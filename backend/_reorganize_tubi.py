"""
重新组织 tubi.py 文件的路由顺序
"""
import os

file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "api", "tubi.py")

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 找到尺寸录入 API 结束的位置（在通配符路由之前）
marker_dimensions_end = '    }'
marker_wildcard_route = '@router.get("/{id}")'

# 找到新增 API 开始的位置
marker_new_apis_start = '# ── 册页管理 API ───────────────────────────────────────────────────────────'

# 分割内容
# 1. 开头到尺寸录入 API 结束
idx_dim_end = content.find(marker_wildcard_route)
part1 = content[:idx_dim_end]

# 2. 通配符路由和手动标注路由（需要保留在最后）
idx_new_apis = content.find(marker_new_apis_start)
part2 = content[idx_dim_end:idx_new_apis]

# 3. 新增的册页、标签、统计 API
part3 = content[idx_new_apis:]

# 重新组合：part1 (原有到尺寸) + part3 (新增API) + part2 (通配符+手动标注)
new_content = part1 + part3 + part2

# 写回文件
with open(file_path, "w", encoding="utf-8") as f:
    f.write(new_content)

print("路由顺序已重新组织！")
print(f"  - 新增 API（册页/标签/统计）已移到通配符路由之前")
