# Tubi 动态调参 + 纠错策略（Plan）

## Summary
针对 `annotated_d3778526-699d-4b7b-94f2-29e349ec848a.jpg` 暴露的问题（expand 过度补面积、题跋漏检/误检、画材包含题跋、印章误检/漏检），把当前“靠 .env 固定参数”的方式升级为 **每张图自动估计/动态调参** 的 pipeline，并把“inscription 优先”作为硬规则在 regions/mask 两层同时生效，保证稳定性与可复现。

## Current State Analysis（基于仓库现状与 d377 debug）
### 现有能力
- 画材精修：GrabCut + 白纸/背景过滤 + 形态学清理（`refine_paint_mask_stats`）。
- 题跋精修：基于 seed ROI 的墨迹检测（Otsu + adaptive）+ 连通域合并 + 清理，并可根据 paint_mask 排除画材（`refine_inscription_mask_stats`）。
- 扇子/灰线扩张：Canny 边缘 + 连通域 + hull/fill 追加（`expand_paint_mask_with_edges`）。
- regions 规则化：已存在 seed mask 级别的 `painting_regions -= inscription_regions`（`tubi_worker.py` 中调用 `regions_to_mask` / `mask_to_regions`）。

### d377 具体症状（来自 debug 文件）
- expand 产生了明显“画蛇添足”的巨大补块（见 `paint_added_roi.png` 与 `paint_overlay_expanded.jpg`），属于 hull/fill 把少量边缘扩成大面积的典型问题。
- `paint_mask.png` 里画材包含题跋（LLM 的 `painting_regions` 把题跋算进去了）；`inscription_seed.png` 面积较小且块状，导致后续精修容易漏掉“稀松字”。
- `inscription_overlay.jpg` 中题跋较少且存在误检（用户指出左上角竹叶混入；属于“题跋合并阶段”把邻近绘画笔触合并进来的风险）。
- 印章识别不稳定：当前印章逻辑是题跋精修中的 HSV 红色连通域筛选（对非红章、绿色章或印泥偏淡场景会失败/误检）。

## Goals & Success Criteria
### 目标
1. **每张图自动动态调参**：不再依赖固定 `.env` 参数才能“某一张图很好”。
2. **inscription 优先**：无论 LLM 输出如何，题跋区域在最终结果里都不应被画材吞掉。
3. **expand 只在“确实补回漏检”时生效**：避免 hull/fill 把局部边缘膨胀成大三角/大块。
4. **印章更稳**：至少对红章/绿章/偏淡印泥有可控的召回与噪点。

### 验收标准（以样例图为主）
- d377：`paint_added_roi.png` 不再出现大面积不合理补块；`paint_overlay_expanded.jpg` 的新增面积相对原 paint_mask 增幅受控（阈值可配置/可记录）。
- d377：题跋漏检的“稀松字”明显减少；题跋误检竹叶概率显著下降（debug 叠加图可直观看到）。
- 现有茶壶样例：保持或提升当前效果（不回退）。
- 结果可复现：每张图的“自动选择参数”会落库/可查看（不要求新增 DB 列，优先写入 `regions._meta`）。

## Proposed Changes

### A) 新增：每张图动态调参模块（启发式为主）
**新增文件**
- `backend/app/services/tubi_auto_params.py`

**核心接口**
- `compute_tubi_params(image_path, width, height, regions) -> {paint: {...}, insc: {...}, expand: {...}, seal: {...}, metrics: {...}}`

**启发式输入特征（fast + 可解释）**
- 背景纸色：四角/边缘采样 Lab 中位数 + 方差（用于判断“深色纸底/低对比”）。
- seed 统计：inscription_seed bbox、seed 像素数、seed 的连通性、seed 与 paint_seed 的重叠率。
- 笔画对比：在 inscription_seed bbox 内的灰度直方图、Otsu 阈值、局部对比度（用于选择 `otsu_mult/adaptive_c/dilate` 强度）。
- 边缘强度：在 paint bbox 右侧/扩张 ROI 内的 Canny 密度与方向性（用于决定 expand 是否应启用、以及参数强弱）。

**参数输出策略（例）**
- `paint.bg_deltae/bg_grad_max`：背景越深/越纹理化，deltaE 阈值更保守，避免把纸底当画材。
- `insc.otsu_mult/adaptive_c/dilate_iter`：seed bbox 内对比度低 → 更敏感；对比度高 → 更严格。
- `expand.max_fill_ratio`：当 paint bbox 已接近画面边界或边缘密度低时 → 降低/直接禁用。
- `seal`：根据 seed bbox 内颜色分布判断是否开启红章/绿章通道。

**落库（可复现）**
- 写入 `regions["_meta"]`（不改 DB schema）：
  - `regions["_meta"]["auto_params"] = {...}`
  - `regions["_meta"]["auto_metrics"] = {...}`
  - `regions["_meta"]["provider"] = ...`
  - `regions["_meta"]["normalized_regions"] = true/false`

### B) expand 防“画蛇添足”护栏（强约束 + 评分）
**修改文件**
- `backend/app/services/tubi_mask_refiner.py`（`expand_paint_mask_with_edges`）

**新增判定（用于 d377 这种大补块）**
- **边缘密度门槛**：对每个候选 filled/hull，要求 `edge_pixels_inside / filled_area >= min_edge_density`，否则拒绝。
- **邻接门槛**：候选新增区域必须与原 paint_mask 的膨胀边界相邻（`dilate(paint_mask) ∩ added > 0`），否则拒绝。
- **面积上限动态化**：上限不再仅用 `roi_area * max_fill_ratio`，同时受 `paint_area`、`seed_overlap`、`edge_density` 约束。
- **输出更多 debug**：保存 `paint_added_roi_rejected.png`（可选）与 `expand_metrics.json`（或写入 `_meta`）。

### C) 题跋漏检/误检：从“只靠全局参数”改成“seed 导向合并”
**修改文件**
- `backend/app/services/tubi_mask_refiner.py`（`refine_inscription_mask_stats`）

**改进点**
- **seed 距离约束**：grow 合并阶段，候选 component 必须满足：
  - 与 seed 的膨胀区域有交集（`comp ∩ dilate(seed_roi) > 0`），或
  - 距离 seed bbox 不超过 `max_dx/max_dy` 的更严格版本（避免把远处竹叶合并进来）。
- **墨迹生成策略自适应**：根据 seed bbox 内对比度选择 `AND` 或 `OR`（`ink = sensitive & adaptive` vs `ink = sensitive | adaptive`），并记录选择原因到 `_meta`。
- **paint 排除策略自适应**：当 `paint_seed` 与 `inscription_seed` 重叠很高时，避免“先 subtract 导致题跋墨迹归零”；并记录触发原因到 `_meta`。

### D) 印章：从“只识别红章”扩展到红/绿/不确定，并尽量依赖 LLM seed
**修改文件**
- `backend/app/services/tubi_mask_refiner.py`（题跋精修里的 seal 逻辑）

**策略**
- 默认优先依赖 LLM 的 `inscription_regions`（印章属于题跋的一部分），seal 颜色检测只作为补充。
- seal 颜色检测增加绿色通道（HSV hue 范围可配置/自适应），并加入更强的形状特征：
  - rectangularity（外接矩形面积比）
  - solidity（面积/凸包面积）
  - size gate（面积上下限随图尺寸变化）
- debug 输出：`seal_mask.png` 必须始终输出（即使为空也写 0 图），便于排查。

### E) Worker 接入动态调参 + regions 规则化（inscription 优先）
**修改文件**
- `backend/tubi_worker.py`

**接入点**
- LLM 返回 regions 后：
  1) 先做 `painting_regions -= inscription_regions` 的规则化（已有逻辑，补充 debug/落库 meta）。
  2) 调用 `compute_tubi_params(...)` 得到 per-image 参数。
  3) refine_paint / refine_inscription / expand 全部使用 per-image 参数。
  4) 将 `regions["_meta"]` 写回 DB。

## Assumptions & Decisions
- 动态调参选择“快速启发式”为主（用户已选），但允许增加计算量用于提取更丰富的统计特征（用户可接受明显增加处理时间）。
- 不新增 DB 列，参数落在 `regions._meta` 保持低成本可复现；如后续需要更规范可再迁移到专用列。
- expand 默认更保守：宁可少补，也不允许出现明显大块误扩张（用户对 d377 的反馈明确）。

## Verification Plan
1. 本地脚本复现：
   - 用 `TUBI_IMAGE_ID=d377...` 跑 `scripts/dev_refine_tubi_masks.py`，检查：
     - `paint_added_roi.png` 不再出现巨大补块
     - `inscription_overlay.jpg` 稀松字补回、竹叶误检下降
     - `regions._meta.auto_params` 输出可读
2. 回归样例（茶壶图、深色背景图）：
   - 确保题跋/画材比例不发生明显回退；expand 不引入新伪影。
3. Worker 端到端：
   - 重启 worker 后对同一 image_id 重新分析，前端 annotated 与 tubi_debug overlay 对齐。

