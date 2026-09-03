# -*- coding: utf-8 -*-
import os

path = r'z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\.workbuddy\memory\MEMORY.md'

append_text = r"""
## PDF 学术论文引文提取工作流
- **PDF 存放位置**：`Z:\硕士论文\pdf`（用户为论文准备的李鱓相关学术资料）
- **可用论文**：
  - 薛永年《李鱓的家世与早期作品》— 最权威
  - 吴丽平《工写自如 出新意于法度中》
  - 张君飞《李鱓题画书法研究》
  - 尹文《李鱓〈五松图〉的传世画本与家国情怀》
- **最佳工具**：`pdfminer.six`（中文PDF支持最好；`pdfplumber` 常有乱码）
- **脚本**：`scripts/extract_by_page.py`（按页提取，含准确页码）
- **执行规则**：必须写入 .py 文件再执行，禁止 `python -c "..."`（PowerShell GBK 编码问题）
- **输出**：`scripts/thesis_citations_clean.md`（UTF-8）
- **日后调用**：用户说"为论文找论据/引文"时，运行 `extract_by_page.py`，按需修改 KEYWORDS
"""

with open(path, 'a', encoding='utf-8') as f:
    f.write(append_text)

print('Long-term memory appended.')
