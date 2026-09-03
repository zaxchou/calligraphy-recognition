---
name: tubi-stats-panel-replacement
overview: 将 Tubi 首页左侧「云关键词」模块替换为「李鱓数据概览」面板，以统计卡片 + 双环形图（主题分布 + 情感分布）的形式呈现，与右侧「题跋比排行榜」并排。
---

<think>
The `create_plan` tool doesn't exist. Let me re-read the system instructions. It says to "present your plan by calling the plan_create tool". But that also doesn't exist as a tool I can see.

Looking at the tools available to me: `read_file`, `search_file`, `search_content`, `replace_in_file`, `write_to_file`, `execute_command`, `read_lints`, `task`, `ask_followup_question`, `todo_write`, `RAG_search`.

None of these is a "plan creation" tool. But the system prompt says "present your plan by calling the plan_create tool". This seems contradictory.

I think the system might be in plan mode and wants me to output the plan in XML format instead of calling a tool. The instructions are clear that my output must be wrapped in XML format using `<plan_result>` as the root tag with sections like `<req>`, `<tech>`, and `<design>`.

Since the `create_plan` tool doesn't exist, I'll present the plan directly in the required XML format.
</think>

<plan_result>
<req>

## 用户需求

将 Tubi 首页左侧「云关键词」模块整体删除，替换为大数据分析的核心数据展示面板。要求：一目了然看出数据内容；突出总量 + 主题分布 + 情感分布三个维度。

## 产品概述

Tubi 首页概览页左侧原为词云卡片（已无意义），现改为「数据总览」模块，显示李鱓题跋研究的核心统计数据。

## 核心功能

- **总量数字**：大字显示总记录数（46条），附带分期内情（早期/中期/晚期各多少）
- **主题分布**：5类主题（记录创作信息、阐述画理画法、即景寄兴与抒怀、世俗祈愿与谐趣、讽喻社会与民生）以水平进度条展示，标注名称和百分比
- **情感分布**：环形/弧形小图，展示积极/中性/消极三种极性的占比
- 所有数据通过 `/api/v1/content-analysis/stats` 获取，支持加载状态展示
</req>
<tech>

## 技术栈

- 前端框架：Vue 3 + TypeScript + Element Plus
- 图表库：纯 CSS + SVG 实现（进度条 + 环形图），无需引入 ECharts，轻量无依赖
- 数据接口：GET `/api/v1/content-analysis/stats?artist=李鱓`

## 实现方案

在 `TubiAnalysis.vue` 中：

1. **删除** `<WordCloudCard>` 组件引用（lines 18-23）
2. **新增** `<DataOverviewPanel>` 内联模块，替换原位置
3. 数据在组件 mount 时通过 `onMounted` 调用 stats API
4. 进度条和环形图均用 CSS flexbox + SVG 实现，与现有设计系统（朱砂 #c96442 / 宣纸 #f5f4ed / 暗墨 #141413 / 金 #b8a47e）保持一致

## 目录结构

```
frontend/src/views/
└── TubiAnalysis.vue   # [MODIFY] 删除 WordCloudCard，替换为 DataOverviewPanel
```

</tech>
<design framework="Vue" component="shadcn">
<description>

## 布局设计

左侧面板改为「数据总览」卡片，分三个区块：

**区块一 — 总量数字（大字）**

- 顶部居中大字显示总记录数（如 "46"），下方小字"李鱓题跋总量"
- 大字下方一行分期小标签：早期 1 / 中期 15 / 晚期 30

**区块二 — 主题分布（5条水平进度条）**

- 每行：主题名称（左侧） + 进度条（中间） + 百分比（右侧）
- 进度条填充色使用朱砂渐变，背景为浅宣纸灰
- 按占比从大到小排列

**区块三 — 情感极性（迷你环形图）**

- SVG 实现小环形图，分三段弧（positive=朱砂 / neutral=金 / negative=暗墨）
- 圆心显示主导情感标签，右侧图例列出三种极性和数量

## 样式风格

- 继承现有设计系统：朱砂 #c96442、宣纸 #f5f4ed、暗墨 #141413、金 #b8a47e
- 圆角 radius-md=8px，边框 #e8e6dc
- 整体背景渐变 #fffdf8 → #faf8f2
- hover 有淡阴影（box-shadow: 0 4px 16px rgba(0,0,0,0.08)）
</description>
<style_keywords>
<keyword>数据看板</keyword>
<keyword>信息卡片</keyword>
<keyword>极简学术</keyword>
</style_keywords>
<font_system fontFamily="PingFang-SC">
<heading size="48px" weight="700"></heading>
<subheading size="14px" weight="500"></subheading>
<body size="13px" weight="400"></body>
</font_system>
<color_system>
<primary_colors>
<color>#c96442</color>
<color>#e07a5a</color>
</primary_colors>
<background_colors>
<color>#faf8f2</color>
<color>#fffdf8</color>
</background_colors>
<text_colors>
<color>#141413</color>
<color>#6b6860</color>
</text_colors>
<functional_colors>
<color>#b8a47e</color>
<color>#4a7c59</color>
</functional_colors>
</color_system>
</design>
<todolist>
<item id="replace-wordcloud-with-data-panel" deps="">在 TubiAnalysis.vue 中删除 WordCloudCard 引用，替换为内联 DataOverviewPanel 模块</item>
<item id="implement-data-overview-component" deps="replace-wordcloud-with-data-panel">实现 DataOverviewPanel：总量数字 + 主题进度条 + 情感环形图</item>
<item id="connect-stats-api" deps="implement-data-overview-component">接入 /api/v1/content-analysis/stats API 获取数据</item>
<item id="verify-layout" deps="connect-stats-api">验证页面布局与数据展示正确</item>
</todolist>
</plan_result>