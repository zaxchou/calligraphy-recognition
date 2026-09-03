# -*- coding: utf-8 -*-
import os

path = r'z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\.workbuddy\memory\2026-04-26.md'

append_text = r"""
## PDF 学术论文引文提取工作流（23:00，为论文查找论据）
- **PDF 存放位置**：`Z:\硕士论文\pdf`
- **可用论文清单**：
  - 薛永年《李鱓的家世与早期作品》— 最权威，李鱓研究第一人
  - 吴丽平《工写自如 出新意于法度中——李鱓花鸟画艺术三论》
  - 张君飞《李鱓题画书法研究》— 含题画诗147首统计
  - 尹文《李鱓〈五松图〉的传世画本与家国情怀》— 同一题材分期情感变化
  - 马一芳《李鱓题画书法中的金石气研究》（文件名含弯引号，脚本需跳过）
- **最佳工具**：`pdfminer.six`（对中文PDF支持远好于 pdfplumber；pdfplumber 提取中文常有乱码）
- **脚本位置**：`scripts/extract_by_page.py`（按页提取，可获取准确页码）
- **执行方式**：必须将脚本写入 .py 文件再执行，不能用 `python -c "..."`（PowerShell GBK 编码会导致 SyntaxError）
- **输出**：`scripts/thesis_citations_clean.md`（UTF-8，含页码+引文片段）
- **已应用**：将提取的引文扩充到 `academic_report_service.py` 的 `art_history` 字段，李鱓来源从 2 个扩展到 6 个
- **⚠️ 注意事项**：
  - 提取的文字可能有乱码，引文需用户核对原文确认
  - 文件名含特殊字符（弯引号""）需在脚本中跳过或重命名文件
  - 输出文件若含非 ASCII 字符，`read_file` 可能识别为二进制，需用 `powershell Get-Content -Encoding UTF8` 读取
- **日后调用**：用户需要为论文查找论据时，直接调用 `scripts/extract_by_page.py`，修改 KEYWORDS 列表来搜索不同主题
"""

with open(path, 'a', encoding='utf-8') as f:
    f.write(append_text)

print('Memory appended successfully.')
