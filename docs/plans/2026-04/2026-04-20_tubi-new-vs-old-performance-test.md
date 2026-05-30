---
name: tubi-new-vs-old-performance-test
overview: 设计并执行新旧 Tubi 组件（TubiHome/TubiDetail vs 旧版内联代码）的性能对比测试，覆盖加载时间、渲染性能、内存占用等维度。
todos:
  - id: create-benchmark-composable
    content: 创建 useTubiBenchmark.js composable，实现完整的性能计时、内存快照、DOM 统计和 A/B 对比逻辑
    status: pending
  - id: integrate-benchmark
    content: 在 TubiAnalysis.vue 中集成 Benchmark 模块，注入计时点和结果展示浮层
    status: pending
    dependencies:
      - create-benchmark-composable
  - id: test-and-report
    content: 启动 Dev Server 运行 benchmark 测试，记录并分析新旧模式性能对比结果
    status: pending
    dependencies:
      - integrate-benchmark
---

## 产品概述

为 TubiHome/TubiDetail 组件集成创建性能基准测试工具，对比新旧两种渲染模式在实际使用中的性能差异。

## 核心功能

- 首页首次加载渲染时间对比（FCP / 组件挂载耗时）
- 详情页切换渲染时间对比（home → detail 切换响应速度）
- 内存占用快照对比（Vue 组件实例数 + DOM 节点数）
- JS Bundle 大小分析（新旧模式各自的 chunk 贡献）
- ECharts 图表初始化时间对比（趋势图/饼图/关系图）
- 可视化结果展示表格，支持一键切换 flag 并重新测试
- 测试结果自动输出到控制台日志，便于复制记录

## 测试方法

通过修改 `TubiAnalysis.vue` 注入 Performance Benchmark 代码，利用 `performance.now()` 高精度计时 API，分别对 `useNewHomeDetail = true` 和 `useNewHomeDetail = false` 两种模式进行 A/B 对比测试。

## Tech Stack

- **前端框架**: Vue 3 (Composition API + `<script setup>`)
- **构建工具**: Vite 5
- **计时API**: `performance.now()` 高精度时间戳
- **内存监控**: `performance.memory` (Chrome) + `window.performance` API
- **DOM统计**: `document.querySelectorAll('*').length`
- **结果展示**: Element Plus 表格 + 控制台 JSON 输出

## 实现方式

### 方案：注入式 Benchmark 模块

在 `TubiAnalysis.vue` 中添加一个可开关的 Benchmark 系统：

1. **Benchmark 开关**: `const enableBenchmark = ref(false)` — 默认关闭，不影响生产使用
2. **测试流程**：

- 页面加载时记录 T0（路由进入时刻）
- `onMounted` 完成后记录 T1（数据就绪）
- `nextTick` 后记录 T2（首次渲染完成）
- 用户点击作品进入详情时记录 T3（详情渲染完成）
- 每个阶段用 `performance.now()` 计算耗时

3. **A/B 切换**：提供一个测试按钮，自动将 `useNewHomeDetail` 取反、刷新页面、等待稳定后收集指标
4. **内存检测**：记录各阶段的 `performance.memory?.usedJSHeapSize`（Chrome 特有）
5. **Bundle 分析**：通过动态 `import()` 对比两个子组件的模块大小

### 架构设计

```
TubiAnalysis.vue (父组件)
├── Benchmark Controller (新增)
│   ├── timing marks (T0-T5)
│   ├── memory snapshots
│   ├── DOM node counts
│   └── result collector
├── useNewHomeDetail = true → TubiHome / TubiDetail
└── useNewHomeDetail = false → inline templates (旧代码)
```

### 关键测量的性能指标

| 指标 | 测量点 | 说明 |
| --- | --- | --- |
| **页面总加载时间** | T0 → T2 | 路由进入到首页渲染完成 |
| **数据获取耗时** | T0 → T1 | API 请求历史列表时间 |
| **首屏渲染耗时** | T1 → T2 | 数据到位后 Vue 渲染 DOM 时间 |
| **详情页切换耗时** | T3 → T4 | 点击作品到详情页完全展示 |
| **ECharts 初始化** | T_echarts | 趋势图/饼图从 mount 到 setOption 完成 |
| **内存增量** | Δheap | 各阶段 heap 使用量变化 |
| **DOM 节点数** | nodeCount | 首页/详情页各自 DOM 节点总数 |


## 实现细节

- Benchmark 代码以独立 `<script>` 块或 composable 函数形式存在，便于后续移除
- 结果同时显示在页面浮层（方便查看）和控制台（方便复制）
- 自动运行 3 轮取平均值，减少单次误差
- 支持 URL 参数 `?benchmark=1` 自动开启测试模式
- 测试完成后生成 Markdown 格式的报告文本

## 目录结构

```
frontend/src/views/
├── TubiAnalysis.vue              # [MODIFY] 注入 Benchmark 代码（约100行）
└── useTubiBenchmark.js           # [NEW] Benchmark composable（约200行）
    └── 包含所有计时、内存统计、结果收集逻辑
```

## 注意事项

- `performance.memory` 仅 Chrome 启用 `--enable-precise-memory-info` 后可用，需做降级处理
- 旧模式下的 echarts 实例（pieChart/trendChart/friendCircleChart）由父组件管理；新模式下 pieChart 在 TubiDetail 内、trendChart 在 TubiHome 内、friendCircleChart 仍在父组件——这是重要的架构差异点
- 由于 v-if 互斥，同一时间只有一套 UI 被渲染到 DOM，不会出现双份 DOM