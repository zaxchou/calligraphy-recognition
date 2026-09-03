---
name: auto-tags-system
overview: 为作品库构建自动标签系统，从AI分析结果和画作尺寸中实时计算标签，前端缩略图右下角显示。
todos:
  - id: create-auto-tags-service
    content: 新建 auto_tags.py 服务层，实现情感/尺幅/题材/时期/主题5类标签计算逻辑
    status: completed
  - id: inject-computed-tags-api
    content: 修改 tubi.py API，在 get_all_results 和 get_result 中注入 computed_tags 字段
    status: completed
    dependencies:
      - create-auto-tags-service
  - id: merge-tags-frontend
    content: 修改 TubiAnalysis.vue，前端合并 computed_tags 和手动 tags，支持多标签行内展示
    status: completed
    dependencies:
      - inject-computed-tags-api
  - id: optimize-tags-css
    content: 优化 TubiAnalysis.css 标签样式，支持多标签紧凑排列
    status: completed
    dependencies:
      - merge-tags-frontend
  - id: test-and-verify
    content: 启动后端验证 computed_tags 数据，重启前端确认标签显示正确
    status: completed
    dependencies:
      - optimize-tags-css
---

## 用户需求

在作品库缩略图右下角（gallery-labels 区域）自动显示标签，无需手动填写。具体来源：

1. **画材**：material_tags 字段已有，直接关联
2. **尺幅**：根据 artwork_height_cm / artwork_width_cm 换算为传统术语（四尺三开等）
3. **情感**：AI 已有 emotion_score 分值，按5档映射
4. **题材**：从 material_tags 和 title 推断（如"梅"、"松"、"牡丹"）
5. **时期**：period_phase（早期/中期/晚期）
6. **主题**：content_analysis.themes（已有主题标签）

## 关键约束

- 下次 AI 重新分析时标签自动同步（API 层实时计算，不存库）
- 标签可重复，非唯一
- computed_tags（自动）+ tags（手动）前端合并展示
- 已验证情感分值范围 -3.55 ~ 7.35（174条样本）
- 已获取国画传统尺寸术语标准数据

## 技术方案

### 架构设计

- **新增服务层**：`backend/app/services/auto_tags.py` — 纯函数计算，自动标签逻辑集中管理
- **API 层**：`tubi.py` 的 `get_all_results` 和 `get_result` 中调用计算函数，注入 `computed_tags` 字段返回
- **前端**：TubiAnalysis.vue 新增 `computed` 合并 `computed_tags` 和 `tags`，画廊模板支持多标签展示

### 自动标签生成规则

#### 情感标签（5档，基于174条数据分布）

| 阈值 | 标签名 | 说明 |
| --- | --- | --- |
| emotion ≤ -2.0 | 愤慨/压抑 | 消极低沉 |
| -2.0 < e ≤ -0.5 | 恬淡悠然 | 归隐心态 |
| -0.5 < e ≤ 0.5 | 平静 | 中性 |
| 0.5 < e ≤ 2.0 | 旷达 | 积极旷放 |
| e > 2.0 | 昂扬向上 | 热情昂扬 |


#### 尺幅标签（基于北兰亭国画尺寸标准）

按最长边和面积换算：

- 面积 ≤ 2 平方尺 → 小品
- 2 < 面积 ≤ 4 平方尺 → 四开/斗方
- 4 < 面积 ≤ 8 平方尺 → 四尺三开/四尺对开
- 8 < 面积 ≤ 15 平方尺 → 四尺整纸/五尺整纸
- 15 < 面积 ≤ 27 平方尺 → 六尺整纸
- 27 < 面积 ≤ 48 平方尺 → 八尺整纸
- 面积 > 48 平方尺 → 丈二及以上

#### 题材标签

从 material_tags（逗号分隔字符串）直接读取并拆分为独立标签，如 "墨荷,枯木" → ["墨荷", "枯木"]
从 title 关键词补充（如标题含"梅"但 material_tags 无"梅"时追加）

#### 时期标签

直接读取 period_phase 字段：早期 / 中期 / 晚期

#### 主题标签

从 content_analysis.themes 提取各主题的 name 字段

### 实现文件

| 文件 | 操作 | 说明 |
| --- | --- | --- |
| `backend/app/services/auto_tags.py` | 新建 | 自动标签计算逻辑 |
| `backend/app/api/tubi.py` | 修改 | 调用计算函数，注入 computed_tags 字段 |
| `frontend/src/views/TubiAnalysis.vue` | 修改 | 合并 computed_tags 和 tags，更新画廊标签展示 |
| `frontend/src/tubi/TubiAnalysis.css` | 修改 | 标签样式优化（行内显示等） |


# Agent Extensions

无新增扩展。