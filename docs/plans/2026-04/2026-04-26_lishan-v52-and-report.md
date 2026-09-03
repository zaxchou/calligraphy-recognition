---
name: lishan-v52-and-report
overview: v5.2迭代校准（收紧身世自况、修复早期偏阴问题）+ 生成学术报告（含证据链、置信度、分时期趋势、美术史对照）
todos:
  - id: v52-calibration
    content: 修改inscription_content_analyzer.py：身世自况弱信号0.5→0.3并移除归/隐/逸、早期基线修正系数0.5→0.2、咏物寄兴增加归隐类词
    status: completed
  - id: v52-rebatch
    content: 重跑351幅+诊断第一主题分布
    status: completed
    dependencies:
      - v52-calibration
  - id: generate-report
    content: 编写并执行generate_academic_report.py，生成含证据链/分时期趋势/美术史对照/置信度的学术报告
    status: completed
    dependencies:
      - v52-rebatch
---

## 产品概述

对李鱓351幅作品的分析框架进行v5.2迭代校准，并生成可用于论文答辩的学术报告。

## 核心功能

- **v5.2迭代校准**：收紧身世自况弱信号权重、修复早期作品被"懊道人"署名过度拉阴的问题、调整画家情感基线在早期的作用方式
- **学术报告生成**：包含分时期情感趋势、每幅作品的触发词证据链、与美术史研究的对照论证、置信度标注、低置信度边界案例标注
- **报告格式**：Markdown文档，输出到项目根目录，包含数据表格和论证逻辑

## 实现方案

### 1. v5.2 迭代校准（3处修改）

**修改A：身世自况弱信号进一步降权**

- 当前弱信号（老/穷/苦/寒/闷/残/衰/败/倦/遥/叹/慨/惆/悔/恨/归/隐/逸）权重0.5
- v5.2：进一步降到0.3，同时去掉"归""隐""逸"这三个词（它们应归咏物寄兴而非身世自况）
- 预期效果：身世自况从50%降到35-40%

**修改B：早期"懊道人"署名不触发身世自况的情感强制偏阴**

- 当前问题：早期作品（1714-1722）含"懊道人"署名时，画家情感基线-0.5仍然生效，导致早期negative 55.6%偏高
- 修复：在画家情感基线修正逻辑中，早期作品将基线修正系数从0.5降到0.2（早期"懊道人"更多是署名习惯而非真实心境表达）
- 预期效果：早期negative从55.6%降到40-45%

**修改C：咏物寄兴的"归隐"类关键词增强**

- 从身世自况移除"归""隐""逸"后，这些词应在咏物寄兴中体现
- 在咏物寄兴的+1分词中增加"归隐""隐逸""幽居"

### 2. 批量重跑v5.2

- 用rebatch_analyze_li_shan.py重跑351幅
- 用diagnose_primary_theme.py输出第一主题分布

### 3. 学术报告生成

- 编写generate_academic_report.py脚本
- 从数据库提取351幅作品的完整分析数据
- 生成结构化Markdown报告，包含：
- 概述：方法论、数据来源、分类体系
- 主题分布：第一主题+所有主题的分布表
- 情感分布：整体+分时期趋势（核心学术证据）
- 证据链：每幅作品的触发词、emotion_score、special_rules
- 美术史对照：引用故宫博物院/薛永年等学者观点
- 置信度分析：高/中/低置信度的分布
- 边界案例：低置信度作品列表（需人工复核）
- 结论：李鱓的"画像"

### 关键文件

- `backend/app/services/inscription_content_analyzer.py` — 3处规则修改
- `backend/scripts/rebatch_analyze_li_shan.py` — 重跑
- `backend/scripts/generate_academic_report.py` — [NEW] 学术报告生成脚本
- `李鱓题跋分析学术报告_v5.2.md` — [NEW] 报告输出