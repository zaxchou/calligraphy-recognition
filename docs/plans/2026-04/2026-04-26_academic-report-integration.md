---
name: academic-report-integration
overview: 将学术报告生成器固化为后端服务，替换ContentAnalysis页面的LLM洞察为结构化学术报告展示
todos:
  - id: create-report-service
    content: 创建 academic_report_service.py，将 standalone 脚本固化为可复用服务
    status: completed
  - id: replace-summary-api
    content: 修改 /summary 端点，从 LLM 改为确定性学术报告服务，返回结构化 JSON + Markdown
    status: completed
    dependencies:
      - create-report-service
  - id: refactor-frontend-card
    content: 重构 ContentAnalysis.vue 的 AI 洞察卡片为学术分析报告分章节展示组件
    status: completed
    dependencies:
      - replace-summary-api
  - id: integration-test
    content: 联调测试：验证各画家切换、缓存命中、报告渲染、导出功能
    status: completed
    dependencies:
      - refactor-frontend-card
---

## 产品概述

将之前生成的李鱓题跋学术报告（v5.3）固化到系统架构中，彻底替换前端"大数据分析"页面的"AI 数据洞察"功能。现有洞察基于 Qwen LLM 生成叙事文本，用户要求改为确定性规则生成的结构化学术报告，更有学术说服力。

## 核心功能

- **后端服务固化**：将 standalone 脚本 `generate_academic_report.py` 转换为可复用的 `academic_report_service`，支持按 `artist` 参数生成
- **API 替换**：修改 `POST /content-analysis/summary`，从调用 LLM 改为调用确定性学术报告服务，返回结构化 JSON + Markdown
- **前端展示重构**：`ContentAnalysis.vue` 顶部的 "AI 数据洞察" `el-card` 改为 "学术分析报告"，分章节渲染（摘要/主题分布/情感演进/美术史互证/局限与回应/结论）
- **缓存复用**：继续利用 `analysis_summary` 表缓存报告，避免重复计算

## 用户已确认

- 直接替换，不保留原有 LLM 洞察
- 报告显示在大数据分析页面
- 数据集固定，报告不需要频繁更新
- 需要固化报告生成逻辑，不是临时脚本

## Tech Stack

- **Backend**: Python + FastAPI + SQLite
- **Frontend**: Vue 3 + Element Plus + ECharts（已有图表保留）
- **Report Generation**: 纯规则引擎（无 LLM），基于 `inscription_content_analyzer.py` 的分类结果聚合统计

## Implementation Approach

### Backend

1. **新建 `app/services/academic_report_service.py`**：

- 提取 `backend/scripts/generate_academic_report.py` 的核心逻辑
- 改为 `generate_academic_report(artist, db_path)` 函数，支持任意画家
- 返回结构化字典：`{title, abstract, sections: [{id, title, content, type}], markdown, stats}`
- `type` 字段区分 `markdown` / `table` / `list`，便于前端渲染

2. **修改 `app/api/content_analysis.py` 的 `/summary` 端点**：

- 移除 `from app.services.inscription_summary_generator import generate_summary` 及其 LLM 调用
- 改为调用 `academic_report_service.generate_academic_report`
- 更新 `SummaryResponse` 模型：增加 `report` 字段（结构化 JSON），保留 `summary` 字段（Markdown 字符串，向后兼容）
- 缓存逻辑不变：`analysis_summary` 表的 `summary` 字段继续存储 Markdown，`stats_snapshot` 存储 `report` 的 JSON

### Frontend

3. **修改 `frontend/src/views/ContentAnalysis.vue`**：

- 替换第 24-58 行的 `summary-card` 模板
- 新结构：
    - 卡片标题：`学术分析报告`（移除 `qwen-plus` badge）
    - 摘要区：高亮显示，大号字体，独立背景
    - 章节区：使用 `el-collapse` 或独立卡片，逐章展示 `主题分布 / 情感演进 / 分时期趋势 / 美术史互证 / 方法局限 / 结论`
    - 操作栏：`重新生成` 按钮 + `导出 Markdown` 按钮
- `loadCachedSummary` 和 `generateSummary` 函数：适配新 API 响应结构（解析 `report` 字段）
- 保留现有图表区域（饼图/柱状图）不变，报告文字与图表互补

### 架构设计

```
┌─────────────────────────────────────────┐
│  ContentAnalysis.vue                    │
│  ┌─────────────────────────────────────┐│
│  │  学术分析报告 (el-card)              ││
│  │  ├─ 摘要 (高亮)                     ││
│  │  ├─ 主题分布表格                    ││
│  │  ├─ 情感演进表格                    ││
│  │  ├─ 美术史互证                      ││
│  │  ├─ 局限与答辩回应                  ││
│  │  └─ 结论                            ││
│  └─────────────────────────────────────┘│
│  ┌─────────────────────────────────────┐│
│  │  现有图表区域（保留不变）            ││
│  └─────────────────────────────────────┘│
└─────────────────────────────────────────┘
            ↓ POST /content-analysis/summary
┌─────────────────────────────────────────┐
│  content_analysis.py /summary           │
│  ├─ 查 analysis_summary 缓存            │
│  ├─ 命中 → 返回缓存                     │
│  └─ 未命中 → academic_report_service    │
│       └─ 查询 tubi_analyses → 聚合统计  │
│       └─ 返回 {markdown, report}        │
└─────────────────────────────────────────┘
```

## Implementation Notes

- **向后兼容**：`SummaryResponse.summary` 继续返回 Markdown 字符串，前端优先使用 `report` 字段渲染
- **性能**：规则生成 351 条记录约 1-2 秒，与 LLM 相当但无需外部 API，更稳定
- **多画家支持**：`academic_report_service` 通过 `artist` 参数过滤 `tubi_analyses`，报告模板中的美术史互证内容根据画家动态调整（当前先实现李鱓完整版，其他画家降级为通用模板）
- **Blast radius 控制**：仅修改 `/summary` 端点，不影响 `/stats`、 `/correlation`、 `/insight` 等其他端点
- **调试脚本保留**：`backend/scripts/generate_academic_report.py` 保留，改为调用 service 函数生成文件，便于离线调试

## Directory Structure

```
backend/
├── app/
│   ├── services/
│   │   ├── academic_report_service.py   # [NEW] 学术报告生成服务
│   │   └── inscription_summary_generator.py  # [保留但不再被/summary调用]
│   └── api/
│       └── content_analysis.py          # [MODIFY] /summary端点替换LLM调用
frontend/
└── src/
    └── views/
        └── ContentAnalysis.vue          # [MODIFY] 替换AI洞察卡片为学术报告
```