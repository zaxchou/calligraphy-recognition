# Tubi 关键机制备忘

## 颜色规范
- 题跋 inscription：红色
- 画材 painting：蓝色
- 留白 blank：灰色

前端面积指示/区域示意与后端 annotated 叠加图使用同一套语义颜色。

## LLM 供应商（智谱 GLM + 硬切）
- 智谱官方 GLM 配置：`ZHIPU_API_KEY / ZHIPU_BASE_URL / ZHIPU_MODEL / ZHIPU_ENABLED`
- 供应商硬切：`TUBI_LLM_PROVIDER=zhipu|qwen|siliconflow`
  - 设置后将不再 fallback 到其他供应商
  - 无效 provider 会直接失败

## 每张图动态调参（per-image auto params）
目标：不依赖 `.env` 固定参数即可让不同画作场景获得稳定效果。

- 入口：`compute_tubi_params(image_path, width, height, regions)`
- 输出：`paint / insc / expand / seal / metrics`
- 落库：写入 `regions["_meta"]`
  - `auto_params`
  - `auto_metrics`
  - `normalized_regions`

常见分支（自动触发）：
- 深色纸底 / 低边缘：加强画材背景剔除；必要时禁用 expand
- 大片水墨晕染：画材背景剔除更保守；默认禁用 expand
- 印章偏淡：放宽颜色阈值并加强形状过滤

## inscription 优先（regions + mask 双层纠错）
为避免 LLM 把题跋算进画材：
- 在 regions 层先做规则化：`painting_regions -= inscription_regions`
- 在 mask 层最终互斥：`paint_mask -= inscription_mask`

## expand 防“画蛇添足”护栏
`expand_paint_mask_with_edges` 增加约束，避免出现大块误扩张：
- 边缘密度门槛
- 与原 paint_mask 的邻接门槛
- bg_like（纸底相似区域）拒绝
- 新增面积上限（相对 paint 与相对整图）
并输出 debug：`paint_added_roi_rejected.png`、`paint_expand_bg_like.png`

## 题跋精修要点
`refine_inscription_mask_stats`：
- 支持 `ink_mode=and/or`（低对比时可用 `or` 提召回）
- 合并阶段加入 seed 导向约束，降低把远处竹叶误并的概率
- seal 支持红/绿并带形状过滤，且 `seal_mask.png` 总会输出

## 批量重算已上传图片（不重新上传）
脚本：`backend/scripts/dev_reanalyze_existing_uploads.py`

作用：
- 对数据库里已有记录逐张重算并回写：
  - `painting_percent / inscription_percent / blank_percent`
  - `regions`（含 `_meta`）
  - `heatmap_data / position_analysis`
  - 覆盖生成 `data/annotated/annotated_<image_id>.jpg`

推荐运行方式（避免大图卡死）：
- 子进程 + 超时：
  - `TUBI_REANALYZE_USE_SUBPROCESS=true`
  - `TUBI_REANALYZE_TIMEOUT_SEC=900`（可按机器性能调整）
- 失败/超时名单会写到 `backend/data/`：
  - `reanalyze_failed_ids_*.txt`
  - `reanalyze_timeout_ids_*.txt`
- 可用 `TUBI_REANALYZE_ONLY_FAILED_FILE` 只重跑名单里的 id

