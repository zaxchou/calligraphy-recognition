# 书法识别项目 · 开发计划文档库


> 最后更新: 2026-05-27 | 共 104 个计划 | ✅ 92 已完成 | 🔴 12 未完成


## 文档结构

```
docs/plans/
├── README.md          ← 你在这里
├── 2026-04/              ← 78 个计划
├── 2026-05/              ← 26 个计划
│   └── _index.md      ← 月度索引
└── templates/
    └── plan-template.md
```


## 月度索引

### [2026-04](2026-04/_index.md) — 78 个计划（✅ 66 已完成）

| 日期 | 状态 | 计划 |
|------|------|------|
| 04-07 | ✅ | [Tubi 动态调参 + 纠错策略（Plan）](2026-04/2026-04-07_tubi-dynamic-auto-tuning.md) |
| 04-09 | 🔴 | [开启绘画区域 mask 精炼功能（GrabCut），使标注图能精确贴合绘画主体边缘，而不是四边形粗略框选](2026-04/2026-04-09_tubi-paint-mask-precision.md) |
| 04-09 | ✅ | [修改 LLM prompt，让 AI 返回更多点的多边形（15-25点）来描绘绘画区域轮廓，替代 GrabCut 精修方](2026-04/2026-04-09_tubi-paint-polygon-precision.md) |
| 04-10 | 🔴 | [修复标注图中留白区域不显示的问题：让 draw_annotated_image 函数自动计算留白区域（100% - 绘画](2026-04/2026-04-10_fix-blank-region-annotation.md) |
| 04-10 | ✅ | [升级知识库图像 embedding：从零向量改为 DashScope multimodal-embedding-v1 真](2026-04/2026-04-10_knowledge-embedding-upgrade.md) |
| 04-10 | ✅ | [修复AI概述区"相关配图"关联性差的问题：将主要图片来源从跨模态搜索改为文本结果的associated_images，跨](2026-04/2026-04-10_fix-related-images-relevance.md) |
| 04-13 | 🔴 | [保守方案优化潘天寿构图分析：优化 composition_llm.py 的 prompt 讲评质量 + 扩充 panpl](2026-04/2026-04-13_composition-analysis-optimization.md) |
| 04-13 | ✅ | [在现有 Tubi 系统上叠加李鱓题跋学术分析模块：数据整理 → LLM 主题/情感分类 → 分期量化统计 → 内容-形式](2026-04/2026-04-13_李鱓题跋学术分析系统.md) |
| 04-14 | ✅ | [修 CORS 跨域问题，使前端 localhost:3000 能访问后端 API](2026-04/2026-04-14_fix-cors-backend.md) |
| 04-14 | ✅ | [修复Tubi题跋分析系统4个Bug：图片URL路径错、内容分析跳过已校验记录、校对列表排序错、面积计算覆盖错误](2026-04/2026-04-14_fix-tubi.md) |
| 04-14 | ✅ | [为书法题跋分析系统新增：现代文翻译字段、DashScope qwen-plus翻译集成、前端翻译展示、以及大数据分析页面](2026-04/2026-04-14_大数据分析平台增强.md) |
| 04-15 | 🔴 | [将 Tubi 首页左侧「云关键词」模块替换为「李鱓数据概览」面板，以统计卡片 + 双环形图（主题分布 + 情感分布）的形](2026-04/2026-04-15_tubi-stats-panel-replacement.md) |
| 04-15 | ✅ | [新建题跋多边形手动标注工具：前端独立页面 + 后端更新接口，支持从作品详情页和校对页进入，标注结果写入 tubi_ana](2026-04/2026-04-15_inscription-annotator.md) |
| 04-15 | 🔴 | [手动标注保存后，自动调用 V9 分析流程计算 position_analysis、painting/blank 区域，并](2026-04/2026-04-15_tubi-manual-annotation-v9-flow.md) |
| 04-16 | ✅ | [简化方案：InscriptionAnnotator 支持同时标注题跋和绘画两个区域，留白自动计算为剩余部分，生成三色标注](2026-04/2026-04-16_tubi-manual-two-regions.md) |
| 04-16 | ✅ | [将题跋主题/情感分类从纯LLM提示词驱动升级为时间+画作内容+文本三维信号融合的规则引擎算法](2026-04/2026-04-16_tiba-multidim-classification-v4.md) |
| 04-16 | ✅ | [升级李鱓题跋分析系统的 AI 数据洞察质量：从模型、上下文、prompt 策略、前端展示四个维度全面提升，让洞察从"数据](2026-04/2026-04-16_insight-enhancement.md) |
| 04-17 | ✅ | [题跋上传可靠性改造：Layer1后端可靠性（Redis降级+Worker看门狗+错误透明化）+ Layer2前端透明化（](2026-04/2026-04-17_tubi-upload-rebuild.md) |
| 04-17 | ✅ | [内容分析批量重跑增加增量/全量选项](2026-04/2026-04-17_content-analysis-incremental-mode.md) |
| 04-17 | ✅ | [对「待确认时间」目录中 87 张李鱓作品图片，通过感知哈希在参考书（752页PDF图）中匹配元数据页，提取作品名和创作时](2026-04/2026-04-17_li_shan_image_rename.md) |
| 04-17 | ✅ | [在题跋分析上传流程中增加「纯录入」模式：拖入图片后，点确认时弹出选项「AI 分析（默认）」或「仅录入（后续手动标注）」。](2026-04/2026-04-17_tubi-pure-entry-mode.md) |
| 04-18 | ✅ | [新增"AI分析（仅文字）"选项，跳过标注图生成，仅返回文字描述](2026-04/2026-04-18_analyze-text-only.md) |
| 04-18 | 🔴 | [修改tubi_worker.py，使"AI文本分析"模式（mode="analyze_text_only"）跳过图像区域](2026-04/2026-04-18_修复AI文本分析模式功能.md) |
| 04-18 | ✅ | [1. 修复AI文本分析模式（跳过区域检测/OCR，仅快速点评）；2. 优化前端上传弹窗为Claude风格（卡片式选项、统](2026-04/2026-04-18_修复AI文本分析模式_前端上传弹窗Claude风格优化.md) |
| 04-18 | ✅ | [册页与标签功能完整实现文档](2026-04/2026-04-18_ALBUM_TAG_PLAN.md) |
| 04-18 | ✅ | [针对成套册页作品的管理、展示、尺寸录入和统计功能的完整实现方案](2026-04/2026-04-18_册页功能完整规划.md) |
| 04-18 | ✅ | [修复 AlbumManager.vue 创建册页时的 422 错误：添加 @submit.prevent 防止原生表单提](2026-04/2026-04-18_fix-album-422.md) |
| 04-18 | ✅ | [调整 AlbumManager.vue 弹窗和选择区域尺寸，方便多选作品：新建/添加作品弹窗 500/600px→900](2026-04/2026-04-18_widen-album-dialogs.md) |
| 04-18 | ✅ | [彻底解决 422 错误（移除 @keyup.enter）+ 让选择作品区域真正变宽（移除 el-form-item 宽度](2026-04/2026-04-18_fix-422-and-wider-selector.md) |
| 04-18 | ✅ | [将 ContentVerify 改造成统一管理后台，整合册页/Tag管理，新增条屏管理功能](2026-04/2026-04-18_管理后台整合与条屏管理.md) |
| 04-18 | ✅ | [彻底解决 id 和 image_id 双 ID 混乱问题，统一使用 image_id (UUID) 作为外部唯一标识，修](2026-04/2026-04-18_统一ID使用方案-详细执行计划.md) |
| 04-18 | ✅ | [为 InscriptionAnnotator.vue 添加滚轮缩放+拖拽平移功能；修复超宽图片标注定位不准问题；改进缩略](2026-04/2026-04-18_题跋标注器缩放_缩略图修复.md) |
| 04-18 | ✅ | [为 InscriptionAnnotator.vue 设计并实现缩放/平移功能，确保坐标准确；同时优化过宽/过高图的显示](2026-04/2026-04-18_手动标注器缩放方案设计.md) |
| 04-19 | ✅ | [作品库图片右下角添加标签显示（册页、条屏等），Claude配色](2026-04/2026-04-19_gallery-labels.md) |
| 04-19 | ✅ | [修复重分析接口的增量逻辑：当 force_reanalyze=false 时跳过已有分析结果的记录，只分析新增/未分析的](2026-04/2026-04-19_incremental-reclassify-fix.md) |
| 04-19 | ✅ | [为作品库构建自动标签系统，从AI分析结果和画作尺寸中实时计算标签，前端缩略图右下角显示。](2026-04/2026-04-19_auto-tags-system.md) |
| 04-19 | 🔴 | [作品详情页标签可点击，点击后筛选/搜索包含该标签的所有作品](2026-04/2026-04-19_clickable-detail-tags.md) |
| 04-19 | ✅ | [自动标签持久化到tags + 一键清空 + 标签可点击筛选](2026-04/2026-04-19_auto-tags-merge-reset.md) |
| 04-19 | ✅ | [在 ContentAnalysis.vue 中添加力导向网络图，展示主题、情感、分期三维共现关系](2026-04/2026-04-19_主题-情感-分期三维关系网络图.md) |
| 04-20 | 🔴 | [实现4个面积数据可视化图表：面积分布直方图、面积-主题堆叠柱状图、面积三元图、面积-尺寸相关性分析](2026-04/2026-04-20_面积数据可视化方案.md) |
| 04-20 | ✅ | [将 3600+ 行的 TubiAnalysis.vue 拆分为多个独立组件，逐步验证确保无 bug](2026-04/2026-04-20_tubi-analysis-split.md) |
| 04-20 | 🔴 | [设计并执行新旧 Tubi 组件（TubiHome/TubiDetail vs 旧版内联代码）的性能对比测试，覆盖加载时间](2026-04/2026-04-20_tubi-new-vs-old-performance-test.md) |
| 04-20 | ✅ | [按照 Vercel Composition Patterns 重构 Tubi 相关组件，按优先级顺序执行：1. Tubi](2026-04/2026-04-20_tubi-component-refactoring.md) |
| 04-21 | ✅ | [按优先级重构 ContentVerify.vue：拆出题跋校对组件、提取 SSE composable、合并重复函数、复](2026-04/2026-04-21_content-verify-refactor.md) |
| 04-21 | ✅ | [修复 TubiImageZoomDialog title prop 生效问题，移除 VerifyPanel 硬编码 AP](2026-04/2026-04-21_ContentVerify重构收尾.md) |
| 04-21 | ✅ | [后端新增作者列表 API（从数据库 DISTINCT 查询），前端4个页面的作者下拉从硬编码改为动态获取](2026-04/2026-04-21_DynamicArtistList.md) |
| 04-21 | ✅ | [首页 Hero 画廊优化：扩充图片至11张、生成缩略图解决卡顿、标题改白字楷体、移除 badge，并评估可选动画增强方案](2026-04/2026-04-21_home-hero-gallery-v2.md) |
| 04-21 | ✅ | [首页全页暗色博物馆风格改版：hero滚动减速、header首页黑底白字、下半部分功能卡片/流程/引用区统一暗色设计。](2026-04/2026-04-21_home-page-dark-redesign.md) |
| 04-21 | ✅ | [首页 Hero 区域新增视频背景切换功能：将生成的博物馆视频作为可选背景，保留现有画廊效果，通过开关一键切换。](2026-04/2026-04-21_hero-video-background-toggle.md) |
| 04-21 | ✅ | [在校对页面添加「重新分析」单条按钮，后端新增对应 API。](2026-04/2026-04-21_verify-panel-single-reanalyze.md) |
| 04-21 | ✅ | [修复校对页面统计数超过200条时只统计前200条的问题，后端单独返回 verified_count/translated](2026-04/2026-04-21_fix-verify-counts-over-200.md) |
| 04-21 | ✅ | [修复增量分析筛选条件（应对齐已校对+已翻译），并修复前端limit:200导致VerifyPanel校对数与顶部统计不一](2026-04/2026-04-21_fix-batch-incremental-and-verify-count.md) |
| 04-21 | ✅ | [修复顶部导航菜单在子路由页面下的高亮状态，确保访问作品详情页等子路由时，对应的父级菜单项正确高亮。](2026-04/2026-04-21_fix-nav-active-state.md) |
| 04-21 | ✅ | [在主页核心功能区域新增"题跋大数据分析"卡片，使功能板块从5个变为6个，布局保持3列2行整齐排列。](2026-04/2026-04-21_update-home-features.md) |
| 04-21 | ✅ | [参考 Notion 重新设计 Home.vue 首页：上半部分暗色 Hero+数据墙+功能卡，下半部分亮色 Claude](2026-04/2026-04-21_homepage-notion-redesign.md) |
| 04-22 | ✅ | [题跋校对页面增加搜索功能：在当前作者范围内按作品名/年份/题跋文字模糊搜索，弹出结果列表选择后跳转定位](2026-04/2026-04-22_tubi-verify-search.md) |
| 04-22 | ✅ | [合并数字定位与搜索功能：删除旧 jumpToId，将搜索框移到 VerifyPanel filter-row，搜索同时支](2026-04/2026-04-22_tubi-verify-search-merge.md) |
| 04-22 | ✅ | [重构题跋分析管道为CV优先架构，全流程采用「相对特征+分群规律+跨群测试」泛化性保障机制，彻底解决过拟合问题，支持暗底/](2026-04/2026-04-22_泛化优先CV-First题跋分析架构重构.md) |
| 04-22 | 🔴 | [修复CV-First架构的三个问题：标注图增加蓝色绘画区域叠加、保护手动编辑数据不被覆盖、手动保存接口标记user_ed](2026-04/2026-04-22_cv-first-fixes.md) |
| 04-24 | ✅ | [在管理后台 ContentVerify.vue 新增"重新解析"标签页，自动找出 analysis_note 含错误文本](2026-04/2026-04-24_reanalyze-errors-feature.md) |
| 04-24 | ✅ | [新建 artists 数据库表，将硬编码的画家元数据/提示词变量提取为可编辑字段，在管理后台新增「作者信息」Tab 支持](2026-04/2026-04-24_artist-info-management.md) |
| 04-26 | 🔴 | [新增印章管理功能：后端新建 seals 表 + CRUD API + 图片上传 + 数据迁移脚本；前端新增 SealMa](2026-04/2026-04-26_seal-management-feature.md) |
| 04-26 | ✅ | [李鱓作品分析框架彻底重构：从行为分类改为意图导向分类，修复情感分析通道，批量重跑351幅作品](2026-04/2026-04-26_lishan-analysis-refactor.md) |
| 04-26 | ✅ | [v5.2迭代校准（收紧身世自况、修复早期偏阴问题）+ 生成学术报告（含证据链、置信度、分时期趋势、美术史对照）](2026-04/2026-04-26_lishan-v52-and-report.md) |
| 04-26 | ✅ | [将学术报告生成器固化为后端服务，替换ContentAnalysis页面的LLM洞察为结构化学术报告展示](2026-04/2026-04-26_academic-report-integration.md) |
| 04-27 | ✅ | [将题跋分析的主题/情感算法规则从 inscription_content_analyzer.py 抽离到独立规则中心模块](2026-04/2026-04-27_unify-tibi-analysis-rules.md) |
| 04-27 | ✅ | [调整情感基线修正和交游赠答权重，修正rebatch后的摆锤效应和交游赠答虚高](2026-04/2026-04-27_v5_4-emotion-baseline-tuning.md) |
| 04-27 | ✅ | [将题跋图片上传功能从 Tubi 页面迁移到管理后台 ContentVerify 页面，新增"作品上传"tab](2026-04/2026-04-27_move-upload-to-admin.md) |
| 04-27 | ✅ | [将作品上传tab移到最后一个位置](2026-04/2026-04-27_move-upload-tab-last.md) |
| 04-27 | ✅ | [扩展Tubi搜索功能，后端新增inscription_content/inscription_modern/seal_c](2026-04/2026-04-27_enhance-tubi-search.md) |
| 04-27 | ✅ | [修复 VerifyPanel 搜索结果"跳转"按钮：改为在当前面板内切换记录（不弹新页面），并修复所有搜索结果都跳到同一](2026-04/2026-04-27_fix-verifypanel-search-jump.md) |
| 04-28 | ✅ | [内容 × 面积联动分析 — 数据验证后精简规划](2026-04/2026-04-28_content-area-correlation-analysis.md) |
| 04-28 | ✅ | [自嘲模式情感反转方案](2026-04/2026-04-28_自嘲模式情感反转方案.md) |
| 04-28 | 🔴 | [将"批量重跑"按钮从 ContentAnalysis（大数据分析）页面移到 ContentVerify（管理后台）页面，](2026-04/2026-04-28_batch-reanalyze-button-relocation.md) |
| 04-28 | ✅ | ["Phase 2: 文档解析器升级 — 将 MinerU 云 API 集成到 PdfProcessor，替代本地 PyM](2026-04/2026-04-28_phase2-mineru-integration.md) |
| 04-28 | ✅ | [以图搜图 · 作品查重方案](2026-04/2026-04-28_image-similarity-search-plan.md) |
| 04-29 | ✅ | [以图搜图 · 自验证修复 + Qwen3-VL-Embedding 切换 + UI 重构 Plan](2026-04/2026-04-29_image-search-fix-plan.md) |
| 04-29 | ✅ | [写意知识库分屏重构 + PDF.js 修复计划（含调研增强）](2026-04/2026-04-29_knowledge-search-rebuild-plan.md) |

### [2026-05](2026-05/_index.md) — 26 个计划（✅ 26 已完成）

| 日期 | 状态 | 计划 |
|------|------|------|
| 05-01 | ✅ | [Composition 模块优化方案](2026-05/2026-05-01_plan_composition_optimize.md) |
| 05-01 | ✅ | [Plan: 插图查找链路彻底修复](2026-05/2026-05-01_plan_figure_fix.md) |
| 05-01 | ✅ | [Plan: 报告插图修复 + 起承转合改版](2026-05/2026-05-01_plan_qczh_revamp.md) |
| 05-01 | ✅ | [写意知识库工作日志 · 2026-04-29 ~ 2026-04-30](2026-05/2026-05-01_summary_2026-04-30.md) |
| 05-01 | ✅ | [Composition 模块优化工作总结 · 2026-04-30](2026-05/2026-05-01_summary_2026-04-30_composition_optimization.md) |
| 05-02 | ✅ | [起承转合：用户自定义Markdown知识注入 + LLM/GLM分工优化](2026-05/2026-05-02_plan_qczh_user_markdown.md) |
| 05-05 | ✅ | [微信小程序转化方案 · 初步调研报告 v1](2026-05/2026-05-05_plan_miniprogram_v1_research.md) |
| 05-05 | ✅ | [微信小程序转化方案 · V2 深入规划（两模块聚焦）](2026-05/2026-05-05_plan_miniprogram_v2_twomods.md) |
| 05-05 | ✅ | [微信小程序转化方案 · V3 潘天寿构图技术深入](2026-05/2026-05-05_plan_miniprogram_v3_pantianshou_tech.md) |
| 05-05 | ✅ | [微信小程序转化方案 · V4 技术决议 + 注册指南](2026-05/2026-05-05_plan_miniprogram_v4_decisions_guide.md) |
| 05-05 | ✅ | [微信小程序转化方案 · V5 Demo 构建 + 部署调研](2026-05/2026-05-05_plan_miniprogram_v5_demo_deploy.md) |
| 05-05 | ✅ | [微信小程序 · V6 架构重构方案](2026-05/2026-05-05_plan_miniprogram_v6_architecture.md) |
| 05-05 | ✅ | [起承转合工作流报告](2026-05/2026-05-05_qczh-workflow-report.md) |
| 05-16 | ✅ | [画家百科页面 — 实施规划](2026-05/2026-05-16_artist-encyclopedia-plan.md) |
| 05-16 | ✅ | [画家百科独立页面 — 实施规划](2026-05/2026-05-16_画家百科独立页面-实施规划.md) |
| 05-17 | ✅ | [ArtistList 全面重构计划](2026-05/2026-05-17_artist-list-redesign-plan.md) |
| 05-18 | ✅ | [OpenSeadragon 集成方案](2026-05/2026-05-18_OpenSeadragon-integration-plan.md) |
| 05-19 | ✅ | [印章功能增强：来源引用 + 多版本图库 + 前端画廊](2026-05/2026-05-19_seal-source-and-gallery.md) |
| 05-20 | ✅ | [ArtistWorks 改进 + 画作/书法分类](2026-05/2026-05-20_artist-works-improvement.md) |
| 05-20 | ✅ | [Plan: 合并作品上传到作品库](2026-05/2026-05-20_consolidate-upload-into-library.md) |
| 05-20 | ✅ | [作品上传流程合并计划 v2](2026-05/2026-05-20_upload-consolidation-plan.md) |
| 05-21 | ✅ | [侧边栏导航重构：作品库 → 树形菜单](2026-05/2026-05-21_plan_sidebar_restructure.md) |
| 05-27 | ✅ | [数据库优化计划](2026-05/2026-05-27_db-optimization-plan.md) |
| 05-27 | ✅ | [后端代码审查报告](2026-05/2026-05-27_BACKEND_REVIEW.md) |
| 05-27 | ✅ | [情感评分系统完整改造计划](2026-05/2026-05-27_sentiment-scoring-plan.md) |
| 05-27 | ✅ | [墨林情绪引擎 (Molin Emotion Engine)](2026-05/2026-05-27_molin-emotion-engine-plan.md) |

---

## 开发管理规范


### 创建新计划

1. 复制 `templates/plan-template.md`
2. 命名格式: `YYYY-MM-DD_功能名称.md`
3. 放入对应的月份文件夹
4. 更新月度 `_index.md`


### 状态标记

- `✅ 已完成` — 所有 todo 已完成
- `🔴 未完成` — 仍有 pending/in_progress 的 todo


### 来源说明

本文档库整合了以下工具生成的计划文档：

| 来源 | 说明 | 时间范围 | 数量 |
|------|------|----------|------|
| workbuddy | WorkBuddy agent 生成的详细执行计划 | 2026-04 ~ 2026-04 | 71 |
| trae | Trae IDE 生成的设计方案 | 2026-04 ~ 2026-05 | 17 |
| docs | 项目 docs/ 目录的 plan 文档 | 2026-04 ~ 2026-05 | 5 |
| reports | 项目 reports/ 目录的规划报告 | 2026-04 ~ 2026-05 | 11 |
| backend | 后端相关审查文档 | 2026-05 | 1 |

原始文件保留在原位置未删除，本目录是整合后的副本。
