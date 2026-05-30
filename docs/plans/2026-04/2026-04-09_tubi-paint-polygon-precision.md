---
name: tubi-paint-polygon-precision
overview: 修改 LLM prompt，让 AI 返回更多点的多边形（15-25点）来描绘绘画区域轮廓，替代 GrabCut 精修方案
todos:
  - id: modify-prompt
    content: 修改 siliconflow_service.py 的 prompt，要求绘画区域用 15-25 点多边形贴合轮廓
    status: completed
  - id: reanalyze-verify
    content: 重置 217c378e 图像状态并重新触发分析，验证标注图效果
    status: completed
    dependencies:
      - modify-prompt
---

## 产品概述

用户反馈题跋分析中绘画区域的标注只是四边形，没有贴合实际绘画（如树）的边缘轮廓。用户不需要像素级精确描边（GrabCut 太慢），只需要多边形有更多点（如 15-25 个）来大致贴合外轮廓即可。

## 核心功能

- 修改 AI prompt，要求绘画区域返回 15-25 个点的多边形，沿绘画主体外边缘描绘轮廓
- 更新示例 JSON，展示多点多边形（而非 4 点矩形）
- 不开启 GrabCut（保持 `TUBI_REFINE_PAINT_MASK=false`），通过 LLM 返回更精确的多边形来提升轮廓贴合度
- 重新触发分析验证效果

## 技术栈

- 后端：FastAPI + Python
- AI 服务：SiliconFlow LLM（MiniMax-M2.5）
- 面积计算：cv2.fillPoly 光栅化多边形（已支持任意点数的多边形）

## 实现方案

### 问题根因

`siliconflow_service.py` 的 prompt 中对绘画区域要求"大致框选即可，可以有一定溢出"，示例只有 4 个点的矩形。LLM 遵循指令返回 4 点四边形，导致标注图是一大方块。

### 修改策略

只修改 prompt（约 5 处），不开启 GrabCut，不改代码逻辑：

1. **绘画区域要求**：从"粗略框选"改为"用 15-25 个点的多边形沿绘画主体外边缘描绘轮廓"
2. **绘画区域方法**：从"粗略包围"改为"沿绘画可见外缘取点，边缘变化大的地方多取点"
3. **示例 JSON**：painting_regions 从 4 点矩形改为 15+ 点多边形
4. **关键要点**：更新第 1 条，与新的绘画区域要求一致
5. **自检清单**：增加"绘画区域是否有足够多的点来贴合轮廓？"

### 为什么不开启 GrabCut

- GrabCut 需要额外 3-5 秒处理时间
- 用户明确表示不需要像素级精确描边
- 20 个点的多边形已能大致贴合树等不规则轮廓
- LLM 多返回几个点的 token 开销很小

### 面积计算兼容性

`calculate_area_stats_fillpoly` 使用 `cv2.fillPoly` 对多边形做像素级光栅化，无论多边形有 4 个点还是 20 个点都能正确计算面积，无需修改。

## 目录结构

```
backend/
├── app/services/siliconflow_service.py  # [MODIFY] 修改 prompt 中绘画区域的要求和示例（第74-150行）
```

## 实现注意事项

- Prompt 修改后不需要重启 tubi_worker，下次分析任务自动使用新 prompt
- 但如果需要重新分析已有图像，需要将该图像状态重置为 `queued`
- LLM 可能仍然返回较少的点（模型不一定严格遵循点数要求），但 prompt 引导会比当前效果好很多
- 不需要修改 `.env` 中的 `TUBI_REFINE_PAINT_MASK` 配置