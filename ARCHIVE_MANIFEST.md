# 归档清单 (Archive Manifest)

> 归档日期：2026-04-26
> 归档原因：清理工作目录中的无头文件、无用测试脚本、备份文件和重复文件
> 归档目录：`archive/`（已加入 .gitignore，不会被 git 跟踪）

## 归档统计

| 目录 | 文件数 | 说明 |
|---|---|---|
| `databases/` | 4 | 备份数据库（~35MB） |
| `pdfs/` | 2 | 重复 PDF 文件（~33MB） |
| `orphan-vue/` | 3 | 无任何代码引用的 Vue 组件 |
| `orphan-backend-modules/` | 3 | 无任何代码引用的后端模块 |
| `root-scripts/` | 11 | 根目录调试/测试脚本 |
| `backend-scripts/` | 137 | backend/ 根目录一次性脚本 |
| `scripts-dir/` | 22 | scripts/ 目录旧版本脚本 |
| `temp-output/` | 1 | 临时输出文件 |
| `old-versions/` | 2 | 版本旧脚本（fix_clean2.sh, fix_push2.sh） |
| `training-docs/` | 10 | 根目录训练/分析文档 |
| `training-json/` | 8 | 训练结果 JSON 文件 |
| `misc/` | 3 | 杂项文件（readme.me, _build_log.txt, qczh_history.json） |
| **合计** | **206** | |

## 详细清单

### databases/ — 备份数据库
- `calligraphy_2026-04-15.db` (11.78 MB)
- `calligraphy_backup_2026-04-15.db` (11.78 MB)
- `calligraphy_backup_2026-04-16.db` (11.78 MB)
- `calligraphy_data_root.db` (328 KB — 原 data/calligraphy.db)

### pdfs/ — 重复 PDF
- `56154fd4..._中国写意花鸟画教程终版.pdf` (23.2 MB — 与 2625a19d 版重复)
- `e66f7850..._潘天寿《关于构图问题》(2).pdf` (10.28 MB — 与 ae4f7a84 版重复)

### orphan-vue/ — 孤儿 Vue 组件
- `NewTubiLayout.vue` — 从未被导入
- `TubiHistoryDialog.vue` — 从未被导入
- `ContentVerify_VerifyPanel.vue` — 占位文件，仅含 el-alert

### orphan-backend-modules/ — 孤儿后端模块
- `caption_ocr.py` — 无 import 引用
- `parse_figure_metadata.py` — 无 import 引用
- `figure_caption_matcher.py` — 无 import 引用

### root-scripts/ — 根目录调试/测试脚本
- `_test_import.py`, `_check_procs.py`, `_wait_analysis.py`
- `check_worker.py`, `debug_recognition.py`, `debug_wrong_recognition.py`
- `fix_paths.py`, `init_database.py`
- `test_db_poll.py`, `test_dual.py`, `test_worker.bat`

### backend-scripts/ — backend/ 一次性脚本（137个）
包含所有 `batch_*`, `_check_*`, `_debug*`, `_fix_*`, `_test_*`, `_backfill_*`, `auto_annotate*`, `reclassify_*`, `re_embed_*`, `validate_*`, `vl_*`, `verify_*`, `monitor_*`, `restart_*`, `reset_*`, `retry_*`, `regenerate_*`, `recompute_*`, `re_audit_*`, `rename_*`, `reupload_*`, `sync_*`, `crop_*`, `ingest_*`, `process_*`, `update_*`, `backfill_*`, `migrate_*`, `add_*`, `clear_*`, `list_*`, `print_*`, `call_*`, `check_*`, `debug_*`, `fix_*`, `sift_*`, `match_*`, `analyze_*`, `reanalyze_*`, `reprocess_*`, `manual_*` 等一次性脚本。

### scripts-dir/ — scripts/ 目录（22个）
- `qichengzhuanhe_v3.py` ~ `v9.py` + `v9_backup.py`（仅 v9 是最新）
- `qichengzhuanhe_learn.py`, `qichengzhuanhe_training.py`, `v2.py`, `qichengzhuanhe_validate.py`
- `apply_phase2.py`, `apply_to_production.py`, `check_images.py`, `check_qdrant.py`
- `dev_find_tubi.py`, `dev_reanalyze_existing_uploads.py`, `dev_refine_tubi_masks.py`, `dev_refine_tubi_paint.py`
- `fix_image_associations.py`, `patch_v9_fewshot.py`

### temp-output/ — 临时输出文件
- `reanalyze_timeout_ids_20260406_060104.txt`

### old-versions/ — 版本旧脚本
- `fix_clean2.sh` — 与 fix_clean.sh 重复
- `fix_push2.sh` — 与 fix_push.sh 重复

### training-docs/ — 训练/分析文档
- `CODE_REVIEW.md`, `KNOWLEDGE_IMPROVEMENT_PLAN.md`, `KNOWLEDGE_UPGRADE_PLAN.md`
- `pan.md`, `panplus.md`, `PAN_BOOK_ANALYSIS.md`, `README_TUBI_ANALYSIS.md`
- `tibacontents.md`, `training_learn_result.md`, `training_report.md`

### training-json/ — 训练结果 JSON
- `training_phase1_results.json` ~ `training_v8_results.json`（7个）
- `test_dual_result.json`

### misc/ — 杂项
- `readme.me` — 应为 readme.md，包含潘天寿构图模块规划
- `_build_log.txt` — 构建日志
- `qczh_history.json` — 空文件（仅 `[]`）

## 恢复方法

如需恢复某个文件，从 `archive/` 对应子目录移回原位即可：

```powershell
# 示例：恢复某个文件
Move-Item "archive\backend-scripts\some_script.py" "backend\"

# 示例：恢复整个目录
Get-ChildItem "archive\scripts-dir" | Move-Item "backend\scripts\"
```

## 已同步更新的 .gitignore

新增忽略规则：
- `archive/` — 归档目录不提交
- `.trae/` — IDE 工具目录
- `work-logs/` — 工作日志
- `data/.embedding_cache/` — Embedding 缓存（~13MB）
- `skills/` — Skills 目录
