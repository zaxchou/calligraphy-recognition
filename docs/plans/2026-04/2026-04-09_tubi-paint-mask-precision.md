---
name: tubi-paint-mask-precision
overview: 开启绘画区域 mask 精炼功能（GrabCut），使标注图能精确贴合绘画主体边缘，而不是四边形粗略框选
todos:
  - id: enable-refine-config
    content: 在 .env 中取消注释 TUBI_REFINE_PAINT_MASK=true、TUBI_REFINE_INSCRIPTION_MASK=true、TUBI_DEBUG_SAVE_IMAGES=true
    status: pending
  - id: restart-worker-reanalyze
    content: 重启 tubi_worker 并重新触发 217c378e 图像分析
    status: pending
    dependencies:
      - enable-refine-config
  - id: verify-result
    content: 验证标注图是否精确贴合绘画轮廓，检查调试图
    status: pending
    dependencies:
      - restart-worker-reanalyze
---

## 产品概述

用户反馈题跋分析中绘画区域的标注不够精确——当前标注只是四边形，没有贴合实际绘画（如树的）边缘轮廓。需要开启已有的 mask 精炼功能，使绘画和留白区域都能精确到像素级轮廓。

## 核心功能

- 开启 `TUBI_REFINE_PAINT_MASK` 配置，让 GrabCut + 颜色过滤精修绘画区域 mask，从四边形变为像素级精确轮廓
- 开启 `TUBI_REFINE_INSCRIPTION_MASK` 配置，让墨迹检测精修题跋区域
- 开启调试模式方便验证效果
- 重新触发分析并验证标注图效果

## 技术栈

- 后端：FastAPI + Python + OpenCV (GrabCut)
- 配置：`.env` 环境变量
- 任务队列：Redis + `tubi_worker.py` 独立进程

## 实现方案

### 问题根因

AI (SiliconFlow) 返回的 `painting_regions` 只有4个点（四边形），无法贴合不规则绘画轮廓。项目已有 `refine_paint_mask_stats`（GrabCut 精修）和 `refine_inscription_mask_stats`（墨迹检测），但 `.env` 中对应的开关被注释掉了，所以这些精修逻辑从未执行。

### 修改策略

只需在 `.env` 中取消注释两个开关即可启用已有功能，无需编写新代码：

1. **取消注释 `TUBI_REFINE_PAINT_MASK=true`** — 启用 GrabCut 精修绘画 mask

- 工作流程：AI 四边形 → 取 bbox → GrabCut 分割 → 移除白色区域 → LAB 背景色过滤 → 形态学清理 → 连通域过滤 → 像素级精确 mask

2. **取消注释 `TUBI_REFINE_INSCRIPTION_MASK=true`** — 启用墨迹检测精修题跋
3. **开启 `TUBI_DEBUG_SAVE_IMAGES=true`** — 保存中间调试图到 `data/tubi_debug/<image_id>/`，方便验证
4. 重启 `tubi_worker.py`，重新触发分析验证

### 精修后的标注图流程

mask 精炼开启后，`tubi_worker.py` 会走 cv2 路径（非 PIL），直接用精确的 paint_mask 和 inscription_mask 渲染三色标注图，留白 = 全图 - 绘画 - 题跋，自然精确。

## 目录结构

```
backend/
├── .env                          # [MODIFY] 取消注释 TUBI_REFINE_PAINT_MASK、TUBI_REFINE_INSCRIPTION_MASK、TUBI_DEBUG_SAVE_IMAGES
├── tubi_worker.py                # 无需修改（已支持 mask 精炼路径 + 三色标注）
├── app/services/tubi_mask_refiner.py  # 无需修改（GrabCut 精修逻辑已完备）
└── app/core/config.py            # 无需修改（默认 false，读 .env 覆盖）
```

## 实现注意事项

- `.env` 修改后需要重启 `tubi_worker.py` 才能生效（config 在进程启动时读取）
- FastAPI 服务不需要重启（它不读这些配置，只由 tubi_worker 消费）
- 重启前先杀掉旧的 tubi_worker 进程，避免多个 worker 竞争 Redis 锁
- 对已有分析记录，需要重置状态为 `queued` 才能重新触发分析
- GrabCut 精修会增加约 3-5 秒处理时间（取决于图像尺寸），但换来像素级精度