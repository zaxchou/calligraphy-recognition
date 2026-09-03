with open('.workbuddy/memory/2026-04-27.md', 'a', encoding='utf-8') as f:
    f.write('\n## 管理后台 UI 调整\n')
    f.write('- 标注校对 tab 改名为「标注图校对」\n')
    f.write('- Tab 重排：题跋校对 → 标注图校对 → 尺寸录入 → 印章管理 → 册页管理 → 条屏管理 → 标签管理 → 作者信息\n')
    f.write('- Tab 居中尝试失败（Element Plus 内部样式干扰），已恢复原样\n')
    f.write('- 踩坑：read_file 显示 :::deep() 但文件实际是 ::deep()（两个冒号），导致 replace_in_file 匹配失败\n')
print('Done')
