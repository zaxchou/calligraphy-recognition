"""Remove the ineffective scoped tab centering rule from ContentVerify.vue"""
file_path = r"z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\frontend\src\views\ContentVerify.vue"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

old = """::deep(.admin-tabs .el-tabs__header) {
  margin-bottom: 20px;
}

::deep(.admin-tabs .el-tabs__nav-wrap) {
  display: flex;
  justify-content: center;
}

::deep(.admin-tabs .el-tabs__nav-wrap::after) {"""

new = """::deep(.admin-tabs .el-tabs__header) {
  margin-bottom: 20px;
}

::deep(.admin-tabs .el-tabs__nav-wrap::after) {"""

if old in content:
    content = content.replace(old, new, 1)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Done: removed ineffective scoped centering rule")
else:
    print("Pattern not found (may already be clean)")
