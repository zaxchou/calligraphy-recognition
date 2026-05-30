# 2026-04 开发计划索引

> 共 78 个计划文档

| 日期 | 状态 | 计划名称 | 来源 |
|------|------|----------|------|
| 04-07 | ✅ 已完成 | [Tubi 动态调参 + 纠错策略（Plan）](2026-04-07_tubi-dynamic-auto-tuning.md) | trae |
| 04-09 | 🔴 未完成 | [开启绘画区域 mask 精炼功能（GrabCut），使标注图能精确贴合绘画主体边缘，而不是四边形粗略](2026-04-09_tubi-paint-mask-precision.md) | workbuddy |
| 04-09 | ✅ 已完成 | [修改 LLM prompt，让 AI 返回更多点的多边形（15-25点）来描绘绘画区域轮廓，替代 G](2026-04-09_tubi-paint-polygon-precision.md) | workbuddy |
| 04-10 | 🔴 未完成 | [修复标注图中留白区域不显示的问题：让 draw_annotated_image 函数自动计算留白区域](2026-04-10_fix-blank-region-annotation.md) | workbuddy |
| 04-10 | ✅ 已完成 | [升级知识库图像 embedding：从零向量改为 DashScope multimodal-embe](2026-04-10_knowledge-embedding-upgrade.md) | workbuddy |
| 04-10 | ✅ 已完成 | [修复AI概述区"相关配图"关联性差的问题：将主要图片来源从跨模态搜索改为文本结果的associate](2026-04-10_fix-related-images-relevance.md) | workbuddy |
| 04-13 | 🔴 未完成 | [保守方案优化潘天寿构图分析：优化 composition_llm.py 的 prompt 讲评质量 ](2026-04-13_composition-analysis-optimization.md) | workbuddy |
| 04-13 | ✅ 已完成 | [在现有 Tubi 系统上叠加李鱓题跋学术分析模块：数据整理 → LLM 主题/情感分类 → 分期量化](2026-04-13_李鱓题跋学术分析系统.md) | workbuddy |
| 04-14 | ✅ 已完成 | [修 CORS 跨域问题，使前端 localhost:3000 能访问后端 API](2026-04-14_fix-cors-backend.md) | workbuddy |
| 04-14 | ✅ 已完成 | [修复Tubi题跋分析系统4个Bug：图片URL路径错、内容分析跳过已校验记录、校对列表排序错、面积计](2026-04-14_fix-tubi.md) | workbuddy |
| 04-14 | ✅ 已完成 | [为书法题跋分析系统新增：现代文翻译字段、DashScope qwen-plus翻译集成、前端翻译展示](2026-04-14_大数据分析平台增强.md) | workbuddy |
| 04-15 | 🔴 未完成 | [将 Tubi 首页左侧「云关键词」模块替换为「李鱓数据概览」面板，以统计卡片 + 双环形图（主题分布](2026-04-15_tubi-stats-panel-replacement.md) | workbuddy |
| 04-15 | ✅ 已完成 | [新建题跋多边形手动标注工具：前端独立页面 + 后端更新接口，支持从作品详情页和校对页进入，标注结果写](2026-04-15_inscription-annotator.md) | workbuddy |
| 04-15 | 🔴 未完成 | [手动标注保存后，自动调用 V9 分析流程计算 position_analysis、painting/](2026-04-15_tubi-manual-annotation-v9-flow.md) | workbuddy |
| 04-16 | ✅ 已完成 | [简化方案：InscriptionAnnotator 支持同时标注题跋和绘画两个区域，留白自动计算为剩](2026-04-16_tubi-manual-two-regions.md) | workbuddy |
| 04-16 | ✅ 已完成 | [将题跋主题/情感分类从纯LLM提示词驱动升级为时间+画作内容+文本三维信号融合的规则引擎算法](2026-04-16_tiba-multidim-classification-v4.md) | workbuddy |
| 04-16 | ✅ 已完成 | [升级李鱓题跋分析系统的 AI 数据洞察质量：从模型、上下文、prompt 策略、前端展示四个维度全面](2026-04-16_insight-enhancement.md) | workbuddy |
| 04-17 | ✅ 已完成 | [题跋上传可靠性改造：Layer1后端可靠性（Redis降级+Worker看门狗+错误透明化）+ La](2026-04-17_tubi-upload-rebuild.md) | workbuddy |
| 04-17 | ✅ 已完成 | [内容分析批量重跑增加增量/全量选项](2026-04-17_content-analysis-incremental-mode.md) | workbuddy |
| 04-17 | ✅ 已完成 | [对「待确认时间」目录中 87 张李鱓作品图片，通过感知哈希在参考书（752页PDF图）中匹配元数据页](2026-04-17_li_shan_image_rename.md) | workbuddy |
| 04-17 | ✅ 已完成 | [在题跋分析上传流程中增加「纯录入」模式：拖入图片后，点确认时弹出选项「AI 分析（默认）」或「仅录入](2026-04-17_tubi-pure-entry-mode.md) | workbuddy |
| 04-18 | ✅ 已完成 | [新增"AI分析（仅文字）"选项，跳过标注图生成，仅返回文字描述](2026-04-18_analyze-text-only.md) | workbuddy |
| 04-18 | 🔴 未完成 | [修改tubi_worker.py，使"AI文本分析"模式（mode="analyze_text_on](2026-04-18_修复AI文本分析模式功能.md) | workbuddy |
| 04-18 | ✅ 已完成 | [1. 修复AI文本分析模式（跳过区域检测/OCR，仅快速点评）；2. 优化前端上传弹窗为Claude](2026-04-18_修复AI文本分析模式_前端上传弹窗Claude风格优化.md) | workbuddy |
| 04-18 | ✅ 已完成 | [册页与标签功能完整实现文档](2026-04-18_ALBUM_TAG_PLAN.md) | docs |
| 04-18 | ✅ 已完成 | [针对成套册页作品的管理、展示、尺寸录入和统计功能的完整实现方案](2026-04-18_册页功能完整规划.md) | workbuddy |
| 04-18 | ✅ 已完成 | [修复 AlbumManager.vue 创建册页时的 422 错误：添加 @submit.preve](2026-04-18_fix-album-422.md) | workbuddy |
| 04-18 | ✅ 已完成 | [调整 AlbumManager.vue 弹窗和选择区域尺寸，方便多选作品：新建/添加作品弹窗 500](2026-04-18_widen-album-dialogs.md) | workbuddy |
| 04-18 | ✅ 已完成 | [彻底解决 422 错误（移除 @keyup.enter）+ 让选择作品区域真正变宽（移除 el-fo](2026-04-18_fix-422-and-wider-selector.md) | workbuddy |
| 04-18 | ✅ 已完成 | [将 ContentVerify 改造成统一管理后台，整合册页/Tag管理，新增条屏管理功能](2026-04-18_管理后台整合与条屏管理.md) | workbuddy |
| 04-18 | ✅ 已完成 | [彻底解决 id 和 image_id 双 ID 混乱问题，统一使用 image_id (UUID) ](2026-04-18_统一ID使用方案-详细执行计划.md) | workbuddy |
| 04-18 | ✅ 已完成 | [为 InscriptionAnnotator.vue 添加滚轮缩放+拖拽平移功能；修复超宽图片标注定](2026-04-18_题跋标注器缩放_缩略图修复.md) | workbuddy |
| 04-18 | ✅ 已完成 | [为 InscriptionAnnotator.vue 设计并实现缩放/平移功能，确保坐标准确；同时优](2026-04-18_手动标注器缩放方案设计.md) | workbuddy |
| 04-19 | ✅ 已完成 | [作品库图片右下角添加标签显示（册页、条屏等），Claude配色](2026-04-19_gallery-labels.md) | workbuddy |
| 04-19 | ✅ 已完成 | [修复重分析接口的增量逻辑：当 force_reanalyze=false 时跳过已有分析结果的记录，](2026-04-19_incremental-reclassify-fix.md) | workbuddy |
| 04-19 | ✅ 已完成 | [为作品库构建自动标签系统，从AI分析结果和画作尺寸中实时计算标签，前端缩略图右下角显示。](2026-04-19_auto-tags-system.md) | workbuddy |
| 04-19 | 🔴 未完成 | [作品详情页标签可点击，点击后筛选/搜索包含该标签的所有作品](2026-04-19_clickable-detail-tags.md) | workbuddy |
| 04-19 | ✅ 已完成 | [自动标签持久化到tags + 一键清空 + 标签可点击筛选](2026-04-19_auto-tags-merge-reset.md) | workbuddy |
| 04-19 | ✅ 已完成 | [在 ContentAnalysis.vue 中添加力导向网络图，展示主题、情感、分期三维共现关系](2026-04-19_主题-情感-分期三维关系网络图.md) | workbuddy |
| 04-20 | 🔴 未完成 | [实现4个面积数据可视化图表：面积分布直方图、面积-主题堆叠柱状图、面积三元图、面积-尺寸相关性分析](2026-04-20_面积数据可视化方案.md) | workbuddy |
| 04-20 | ✅ 已完成 | [将 3600+ 行的 TubiAnalysis.vue 拆分为多个独立组件，逐步验证确保无 bug](2026-04-20_tubi-analysis-split.md) | workbuddy |
| 04-20 | 🔴 未完成 | [设计并执行新旧 Tubi 组件（TubiHome/TubiDetail vs 旧版内联代码）的性能对](2026-04-20_tubi-new-vs-old-performance-test.md) | workbuddy |
| 04-20 | ✅ 已完成 | [按照 Vercel Composition Patterns 重构 Tubi 相关组件，按优先级顺序](2026-04-20_tubi-component-refactoring.md) | workbuddy |
| 04-21 | ✅ 已完成 | [按优先级重构 ContentVerify.vue：拆出题跋校对组件、提取 SSE composabl](2026-04-21_content-verify-refactor.md) | workbuddy |
| 04-21 | ✅ 已完成 | [修复 TubiImageZoomDialog title prop 生效问题，移除 VerifyPa](2026-04-21_ContentVerify重构收尾.md) | workbuddy |
| 04-21 | ✅ 已完成 | [后端新增作者列表 API（从数据库 DISTINCT 查询），前端4个页面的作者下拉从硬编码改为动态](2026-04-21_DynamicArtistList.md) | workbuddy |
| 04-21 | ✅ 已完成 | [首页 Hero 画廊优化：扩充图片至11张、生成缩略图解决卡顿、标题改白字楷体、移除 badge，并](2026-04-21_home-hero-gallery-v2.md) | workbuddy |
| 04-21 | ✅ 已完成 | [首页全页暗色博物馆风格改版：hero滚动减速、header首页黑底白字、下半部分功能卡片/流程/引用](2026-04-21_home-page-dark-redesign.md) | workbuddy |
| 04-21 | ✅ 已完成 | [首页 Hero 区域新增视频背景切换功能：将生成的博物馆视频作为可选背景，保留现有画廊效果，通过开关](2026-04-21_hero-video-background-toggle.md) | workbuddy |
| 04-21 | ✅ 已完成 | [在校对页面添加「重新分析」单条按钮，后端新增对应 API。](2026-04-21_verify-panel-single-reanalyze.md) | workbuddy |
| 04-21 | ✅ 已完成 | [修复校对页面统计数超过200条时只统计前200条的问题，后端单独返回 verified_count/](2026-04-21_fix-verify-counts-over-200.md) | workbuddy |
| 04-21 | ✅ 已完成 | [修复增量分析筛选条件（应对齐已校对+已翻译），并修复前端limit:200导致VerifyPanel](2026-04-21_fix-batch-incremental-and-verify-count.md) | workbuddy |
| 04-21 | ✅ 已完成 | [修复顶部导航菜单在子路由页面下的高亮状态，确保访问作品详情页等子路由时，对应的父级菜单项正确高亮。](2026-04-21_fix-nav-active-state.md) | workbuddy |
| 04-21 | ✅ 已完成 | [在主页核心功能区域新增"题跋大数据分析"卡片，使功能板块从5个变为6个，布局保持3列2行整齐排列。](2026-04-21_update-home-features.md) | workbuddy |
| 04-21 | ✅ 已完成 | [参考 Notion 重新设计 Home.vue 首页：上半部分暗色 Hero+数据墙+功能卡，下半部](2026-04-21_homepage-notion-redesign.md) | workbuddy |
| 04-22 | ✅ 已完成 | [题跋校对页面增加搜索功能：在当前作者范围内按作品名/年份/题跋文字模糊搜索，弹出结果列表选择后跳转定](2026-04-22_tubi-verify-search.md) | workbuddy |
| 04-22 | ✅ 已完成 | [合并数字定位与搜索功能：删除旧 jumpToId，将搜索框移到 VerifyPanel filter](2026-04-22_tubi-verify-search-merge.md) | workbuddy |
| 04-22 | ✅ 已完成 | [重构题跋分析管道为CV优先架构，全流程采用「相对特征+分群规律+跨群测试」泛化性保障机制，彻底解决过](2026-04-22_泛化优先CV-First题跋分析架构重构.md) | workbuddy |
| 04-22 | 🔴 未完成 | [修复CV-First架构的三个问题：标注图增加蓝色绘画区域叠加、保护手动编辑数据不被覆盖、手动保存接](2026-04-22_cv-first-fixes.md) | workbuddy |
| 04-24 | ✅ 已完成 | [在管理后台 ContentVerify.vue 新增"重新解析"标签页，自动找出 analysis_](2026-04-24_reanalyze-errors-feature.md) | workbuddy |
| 04-24 | ✅ 已完成 | [新建 artists 数据库表，将硬编码的画家元数据/提示词变量提取为可编辑字段，在管理后台新增「作](2026-04-24_artist-info-management.md) | workbuddy |
| 04-26 | 🔴 未完成 | [新增印章管理功能：后端新建 seals 表 + CRUD API + 图片上传 + 数据迁移脚本；前](2026-04-26_seal-management-feature.md) | workbuddy |
| 04-26 | ✅ 已完成 | [李鱓作品分析框架彻底重构：从行为分类改为意图导向分类，修复情感分析通道，批量重跑351幅作品](2026-04-26_lishan-analysis-refactor.md) | workbuddy |
| 04-26 | ✅ 已完成 | [v5.2迭代校准（收紧身世自况、修复早期偏阴问题）+ 生成学术报告（含证据链、置信度、分时期趋势、美](2026-04-26_lishan-v52-and-report.md) | workbuddy |
| 04-26 | ✅ 已完成 | [将学术报告生成器固化为后端服务，替换ContentAnalysis页面的LLM洞察为结构化学术报告展](2026-04-26_academic-report-integration.md) | workbuddy |
| 04-27 | ✅ 已完成 | [将题跋分析的主题/情感算法规则从 inscription_content_analyzer.py 抽](2026-04-27_unify-tibi-analysis-rules.md) | workbuddy |
| 04-27 | ✅ 已完成 | [调整情感基线修正和交游赠答权重，修正rebatch后的摆锤效应和交游赠答虚高](2026-04-27_v5_4-emotion-baseline-tuning.md) | workbuddy |
| 04-27 | ✅ 已完成 | [将题跋图片上传功能从 Tubi 页面迁移到管理后台 ContentVerify 页面，新增"作品上传](2026-04-27_move-upload-to-admin.md) | workbuddy |
| 04-27 | ✅ 已完成 | [将作品上传tab移到最后一个位置](2026-04-27_move-upload-tab-last.md) | workbuddy |
| 04-27 | ✅ 已完成 | [扩展Tubi搜索功能，后端新增inscription_content/inscription_mod](2026-04-27_enhance-tubi-search.md) | workbuddy |
| 04-27 | ✅ 已完成 | [修复 VerifyPanel 搜索结果"跳转"按钮：改为在当前面板内切换记录（不弹新页面），并修复所](2026-04-27_fix-verifypanel-search-jump.md) | workbuddy |
| 04-28 | ✅ 已完成 | [内容 × 面积联动分析 — 数据验证后精简规划](2026-04-28_content-area-correlation-analysis.md) | trae |
| 04-28 | ✅ 已完成 | [自嘲模式情感反转方案](2026-04-28_自嘲模式情感反转方案.md) | trae |
| 04-28 | 🔴 未完成 | [将"批量重跑"按钮从 ContentAnalysis（大数据分析）页面移到 ContentVerif](2026-04-28_batch-reanalyze-button-relocation.md) | workbuddy |
| 04-28 | ✅ 已完成 | ["Phase 2: 文档解析器升级 — 将 MinerU 云 API 集成到 PdfProcesso](2026-04-28_phase2-mineru-integration.md) | workbuddy |
| 04-28 | ✅ 已完成 | [以图搜图 · 作品查重方案](2026-04-28_image-similarity-search-plan.md) | trae |
| 04-29 | ✅ 已完成 | [以图搜图 · 自验证修复 + Qwen3-VL-Embedding 切换 + UI 重构 Plan](2026-04-29_image-search-fix-plan.md) | trae |
| 04-29 | ✅ 已完成 | [写意知识库分屏重构 + PDF.js 修复计划（含调研增强）](2026-04-29_knowledge-search-rebuild-plan.md) | trae |
