---
name: analyze-text-only
overview: 新增"AI分析（仅文字）"选项，跳过标注图生成，仅返回文字描述
todos:
  - id: backend-mode-support
    content: 后端：batch-auto-analyze 端点支持 mode="analyze_text_only"
    status: completed
  - id: worker-skip-annotated
    content: tubi_worker：根据 mode 判断是否生成标注图和面积统计
    status: completed
    dependencies:
      - backend-mode-support
  - id: frontend-two-stage-dialog
    content: 前端：两阶段对话框选择（是否AI分析 / 是否生成标注图）
    status: completed
    dependencies:
      - worker-skip-annotated
  - id: test-and-commit
    content: 自测并提交代码
    status: completed
    dependencies:
      - frontend-two-stage-dialog
---

## 产品概述

在现有的"仅录入"和"AI分析（标注图）"之间新增"AI分析（仅文字分析）"选项，支持用户选择只获取文字描述而不生成标注图。

## 核心功能

- 前端：两阶段对话框，先选择是否进行AI分析，再选择是否生成标注图
- 后端：支持 mode="analyze_text_only"，跳过标注图生成
- Worker：根据 mode 决定是否生成标注图和面积统计

## 技术栈

- 前端：Vue3 + ElementPlus
- 后端：FastAPI (Python)
- Worker：Python

## 实现方案

### 前端改动

- 修改批量上传后对话框为两阶段选择
- 第一阶段：是否进行AI分析（仅录入/AI分析）
- 第二阶段：AI分析模式选择（仅文字/含标注图）

### 后端改动

- `/tubi/batch-auto-analyze` 端点支持 mode="analyze_text_only"
- 保留现有 "analyze" 和 "manual" 模式兼容

### Worker改动

- 在 process_job 中增加 mode 判断逻辑
- mode="analyze_text_only" 时跳过：
- 标注图生成（draw_annotated_image）
- 面积统计（calculate_area_stats）
- 保留：
- regions 提取（analyze_image_regions）
- 题跋分析（analyze_inscription_position）
- OCR文字提取
- analysis_note 保存

## 架构设计

现有三层架构保持不变，仅在模式选择和处理流程上增加分支判断，确保向后兼容。

## 目录结构

```
frontend/src/views/TubiAnalysis.vue  [MODIFY] - 两阶段选择对话框
backend/app/api/tubi.py             [MODIFY] - 支持 mode="analyze_text_only"
backend/tubi_worker.py             [MODIFY] - mode 判断跳过标注图
```