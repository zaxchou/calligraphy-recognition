# 起承转合工作流报告

> 最后更新: 2026-05-03
> 分支: master (已合并 autoresearch/s-curve-fit)

---

## 一、整体架构

```
用户上传图片 → /api/v1/composition/qczh (或 /arrow-demo-llm)
                │
    ┌───────────▼─────────────────────────────┐
    │ 第一段: qwen3.5-plus (文字分析, 90s, t=0.15)  │
    │                                           │
    │ 输入:                                      │
    │   原图(base64, max_side=1024)               │
    │   写意知识库原文 (Qdrant搜索"起承转合/气韵/虚实") │
    │   用户自定义规则 (data/user_markdown/qczh/*.md) │
    │                                           │
    │ 输出: 起承转合定性文字分析 (~350字)            │
    └────────────┬──────────────────────────────┘
                 │
    ┌────────────▼──────────────────────────────┐
    │ 第二段: qwen3-vl-plus (坐标定位, 60s, t=0.15) │
    │                                           │
    │ 输入:                                      │
    │   原图(base64, 全分辨率)                    │
    │   Qwen 第一段的文字分析 (作为 GUIDED prompt)  │
    │                                           │
    │ 输出:                                      │
    │   qi 起点 + path_points[6-8个] + he 合点    │
    │   百分比坐标 (x,y ∈ [0,100])                │
    │   path_shape (之字形/对角线/C形/S形)          │
    └────────────┬──────────────────────────────┘
                 │
    ┌────────────▼──────────────────────────────┐
    │ 绘制: Catmull-Rom 样条 + S形扰动 + 渐变色    │
    │                                           │
    │   8-12个控制点 → 样条 → S形振幅扰动 → 曲线    │
    │   标签: [起(红), 承(橙), 转(蓝), 合(绿)]      │
    │   位于曲线的 0%/33%/67%/100% 位置              │
    └──────────────────────────────────────────┘
```

## 二、API 端点

| 端点 | 用途 | 核心函数 |
|------|------|---------|
| `POST /api/v1/composition/qczh` | 独立起承转合分析 | `analyze_qichengzhuanhe(img_bgr)` |
| `POST /api/v1/composition/arrow-demo-llm` | 向后兼容别名 | 同上 |
| `GET /api/v1/composition/qczh-history` | 历史记录列表 | `list_records()` |
| `POST /api/v1/composition/qczh-history/batch-delete` | 批量删除 | `batch_delete()` |

**返回结构**（前端关键字段）:
```json
{
  "preview_image": "data:image/jpeg;base64,...",
  "arrows": [[sx,sy,ex,ey], ...],
  "arrow_labels": ["起","承","转","合"],
  "llm_analysis": "第一段Qwen文字分析",
  "qwen_analysis": "第一段Qwen原始输出(调试)",
  "path_type": "S形上升",
  "model": "qwen3-vl-plus",
  "points": {"qi": {...}, "mid": [...], "he": {...}}
}
```

## 三、两段 Prompt

### 第一段 QWEN_QCZH_PRE_PROMPT (L707-722)

```
你是中国画构图分析专家。请基于以下知识分析起承转合：

【写意知识库原文（潘天寿 + 写意花鸟画教程）】
{knowledge_context}

【用户自定义起承转合知识】
{user_markdown}

分析：
1. 起：视觉从哪里进入画面？对应物象是什么？
2. 承：视线如何承接发展？经过哪些关键物象？
3. 转：何处发生方向或节奏转折？什么元素造成？
4. 合：如何收束？与题款/印章关系？
5. 整体走势形态：之字形/对角线/C形/S形等？

直接描述，不要JSON，控制在400字以内。
```

### 第二段 GUIDED_QCZH_PROMPT_TEMPLATE (L124-145)

```
你是中国画构图专家。基于以下专家讲评标注曲线路径。

【构图分析】
{llm_analysis}

输出 8-12 个节点 (百分比坐标):

【关键约束】
1. 起(qi)：必须从物象生长根源出发(树根/石基/主枝干入画处)，
    绝不从题跋/叶/花/果实开始。若题跋在边缘，忽略它。
2. 承(path_points[0..N/2])：沿主干推进，必经画眼(鸟/大果实/主花头)
3. 转(path_points[N/2..N])：方向/节奏突变处
4. 合(he)：留白回旋处或主物象收束气口，穷款不当作合点
5. 序列：qi → path_points[0..N] → he，共8-12个点

【坐标域提示——严格遵守】
- 起点 x 位于墨色最重最粗枝干/石块边缘，严禁落题跋/文字区域
  若题跋在右侧→qi.x<30；若题跋在左侧→qi.x>70
- 合在留白回旋处，穷款文字区不作合

返回JSON: {"qi":{"x":,"y":,"label":"起·"}, "path_points":[{"x":,"y":,"label":""},...], "he":{...}, "path_shape":"之字形"}
```

## 四、绘制参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 样条 | Catmull-Rom, 60段 | 穿过所有控制点的平滑曲线 |
| S扰动振幅 | `total_path * 0.08`, 最低20px | 总弧长的8%为振幅 |
| 扰动函数 | `amplitude * (t-t²) * 4 * (0.5-t) * 3.2` | 三次多项式, 起点/终点不动 |
| 线条粗细 | `max(5, 6*scale)` | 自适应 |
| 渐变色 | 红→橙→蓝→绿 | 起→承→转→合 |
| 标签位置 | `[0, n//3, 2*n//3, n-1]` | 曲线 0%/33%/67%/100% |

## 五、用户规则文件

`data/user_markdown/qczh/` 下两个文件自动加载（按字母序）：

| 文件 | 优先级 | 内容 |
|------|--------|------|
| `00_曲线定义.md` | **最高** | S/C/V曲线、主线提取、主势归纳 |
| `画面气韵与视线流转规则.md` | 第二 | 起(生长根源)、合(穷款不强做)、画眼识别、阴阳哲学 |

每次分析自动扫描，无需重启。

## 六、模型与成本

| 段 | 模型 | timeout | API | 计费 |
|----|------|---------|-----|------|
| 文字分析 | `qwen3.5-plus` | 90s | DashScope | 阿里云计费中心 |
| 坐标定位 | `qwen3-vl-plus` | 60s | DashScope | 同上 |

## 七、关键代码位置

```
backend/app/modules/pantianshou_composition/
├── qichengzhuanhe.py         # 核心：两段LLM调用 + 曲线绘制 + 解析
│   ├── QWEN_QCZH_PRE_PROMPT           # 第一段 prompt 模板
│   ├── GUIDED_QCZH_PROMPT_TEMPLATE    # 第二段 prompt 模板
│   ├── _catmull_rom_spline()          # 样条函数
│   ├── draw_arrows_on_lineart()       # 绘制(折线/曲线双模式)
│   ├── _parse_llm_result()            # JSON解析(引导/自主双模式)
│   ├── _qwen_qczh_pre_analysis()      # 第一段 LLM
│   └── analyze_qichengzhuanhe()       # 入口函数
├── qichengzhuanhe_api.py     # FastAPI 路由 (/qczh, /qczh-history)
├── user_markdown.py          # 用户MD加载
└── qdrant_client.py          # Qdrant 知识库搜索
frontend/src/modules/pantianshou-composition/pages/
└── ArrowDemo.vue             # 起承转合前端页面
data/user_markdown/qczh/
├── 00_曲线定义.md
└── 画面气韵与视线流转的规则文本（补充）.md
```

## 八、小程序同步要点

1. 调用 `POST /api/v1/composition/qczh`，传 `multipart/form-data`，字段 `file`
2. 预计耗时 **50-70秒**（qwen3.5-plus ~35-45s + qwen3-vl-plus ~15s）
3. 显示进度可以参考 `ArrowDemo.vue` 的 `PROGRESS_STAGES` 模拟条
4. 结果中的 `preview_image` 是 data URI，可直接 `<image>` 显示
5. 曲线图可能有 1200px 宽，小程序需设 `max-width:100%; height:auto`
6. `qwen_analysis` 字段是调试面板内容，初期可显示在结果页

## 九、历史问题修复记录

| 问题 | 根因 | 修复 |
|------|------|------|
| 显示"Qwen VL" | docstring 过时 | 改为"智能系统" |
| 图片太小 | max_side=800 | → 1600 |
| 标签被裁剪 | 坐标未钳位 | clamp 到画布内 |
| 箭头交叉 | 承转按距离重排 | 引导模式去掉重排 |
| 曲线僵直 | S扰动用两点跨度算 | → 总弧长算振幅 |
| 起从题跋开始 | 第二段空间偏置 | 坐标域硬约束 qi.x<30 |
| 删除弹窗不关闭 | onConfirm 未关 show | 包一层 await+关闭 |
| GLM思考模式空内容 | reasoning_content | 切到全Qwen |
| 随机性大 | temperature=0.3 | → 0.15 |
| 知识库每次都搜Qdrant | 结果固定无意义 | 固化到 _cached_knowledge.md |
| MD规则从未加载 | user_markdown.py 路径少一层 | 修复路径 |
| 知识库被注入两次 | _cached_knowledge.md 被MD扫描重复 | 跳过 `_` 前缀文件 |
| 水墨淡彩底丢失 | 代码被覆盖回 generate_lineart | 恢复 generate_faded_bg |
