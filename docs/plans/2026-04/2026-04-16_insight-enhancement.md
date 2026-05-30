---
name: insight-enhancement
overview: 升级李鱓题跋分析系统的 AI 数据洞察质量：从模型、上下文、prompt 策略、前端展示四个维度全面提升，让洞察从"数据罗列"变为"以小见大的叙事"。
todos:
  - id: upgrade-model
    content: 在 config.py 新增 QWEN_INSIGHT_MODEL 配置，insight 服务改用 qwen-plus-latest
    status: completed
  - id: add-biography
    content: 在 insight_generator.py 新增李鱓生平年表+历史背景+同期画家上下文常量
    status: completed
    dependencies:
      - upgrade-model
  - id: rewrite-summary-prompt
    content: 重写 summary prompt：注入生平上下文，改为叙事驱动风格
    status: completed
    dependencies:
      - add-biography
  - id: rewrite-insight-prompt
    content: 重写 insight prompt：从四段式改为发现-故事-升华三幕结构
    status: completed
    dependencies:
      - add-biography
  - id: enhance-frontend
    content: 重构前端洞察展示：结构化卡片+数据高亮+可折叠章节
    status: completed
    dependencies:
      - rewrite-summary-prompt
      - rewrite-insight-prompt
---

## 用户需求

用户觉得当前 AI 数据洞察"平淡"，难以"以小见大"。根因分析：

1. **模型太轻**：用 `qwen-turbo` 做洞察生成，中国艺术史理解有限
2. **数据太"干"**：只有统计数据，没有李鱓生平、历史背景等叙事上下文
3. **Prompt 策略僵化**：固定四段式填框（空间革命/文本语义/印章/综合画像），不是从数据中发现故事
4. **前端展示单调**：纯文本段落，没有结构化高亮

用户要求按 1→2→3→4 顺序全部做。

## 涉及两个服务

- `inscription_summary_generator.py` — 前端展示的 500 字总结（`/summary` 端点）
- `insight_generator.py` — 深度洞察报告（`/insight` 端点）

## Tech Stack

- **后端**: Python + FastAPI + httpx（DashScope OpenAI Compatible API）
- **前端**: Vue 3 + Element Plus
- **模型**: DashScope Qwen 系列（当前用 qwen-turbo，升级到 qwen-plus-latest）

## 实现方案

### 方向 1：升级模型

- 在 `config.py` 新增 `QWEN_INSIGHT_MODEL` 配置项，默认 `qwen-plus-latest`
- summary 服务保持用 `QWEN_TRANSLATION_MODEL`（qwen-turbo，500字够用）
- insight 服务改用 `QWEN_INSIGHT_MODEL`（qwen-plus-latest，深度分析需要更强模型）
- 可通过环境变量灵活切换模型

### 方向 2：注入叙事上下文

- 在 `insight_generator.py` 新增 `LI_SHAN_BIOGRAPHY` 常量，包含：
- 三期关键事件年表（1714-1722 入宫学蒋 / 1723-1745 出京卖画二次出仕 / 1746-1760 彻底归隐衰年变法）
- 康雍乾三朝政治背景（文字狱、扬州盐商文化）
- 扬州八怪同期画家对比（郑燮、金农、黄慎等）
- 在 prompt 中注入这些上下文，让模型有"故事素材"可以引用

### 方向 3：重写 prompt 策略

- **summary**：从"请写分析报告"改为"请从数据中发现 3 个有趣的故事"，要求用具体作品举例
- **insight**：从固定四段式改为"发现-故事-升华"三幕结构：
- 第一幕：数据中最反直觉的发现（用具体数字+作品举例）
- 第二幕：一个完整的故事（某幅画的年份/主题/情感/面积如何反映李鱓当时的心境）
- 第三幕：这个发现对我们理解李鱓有什么新启示

### 方向 4：增强前端展示

- 洞察区从纯文本改为结构化展示：
- 关键发现卡片（带图标和高亮数字）
- 数据引用高亮（如"1752年18幅"用不同颜色标注）
- 可折叠章节（避免一次性展示太多内容）
- 加载动画优化（显示"正在分析第X个维度..."）

## 关键文件

- `backend/app/core/config.py:126` — 新增 QWEN_INSIGHT_MODEL
- `backend/app/services/inscription_summary_generator.py` — 重写 SUMMARY_PROMPT + 注入上下文
- `backend/app/services/insight_generator.py` — 重写 INSIGHT_USER_PROMPT_TEMPLATE + 注入上下文
- `frontend/src/views/ContentAnalysis.vue:33-61` — 洞察展示区重构

## Agent Extensions

无需要使用的扩展。本次修改全部在现有代码库内完成，不涉及外部工具调用。