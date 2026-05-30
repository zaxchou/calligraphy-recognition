---
name: reanalyze-errors-feature
overview: 在管理后台 ContentVerify.vue 新增"重新解析"标签页，自动找出 analysis_note 含错误文本的记录并重新入队 LLM 文本分析
todos:
  - id: backend-error-list
    content: 后端 tubi.py 新增 GET /tubi/error-analysis-list 端点（SQL LIKE 查询错误关键词，返回 image_id/title/analysis_note/status/created_at）
    status: completed
  - id: frontend-tab
    content: 前端 ContentVerify.vue 新增「重新解析」tab（el-tab-pane + 内联表格 + 统计数字 + 全部重新解析按钮）
    status: completed
    dependencies:
      - backend-error-list
  - id: test-flow
    content: 测试完整流程：查询错误记录 → 入队 → tubi_worker 处理 → analysis_note 更新
    status: completed
    dependencies:
      - frontend-tab
---

## 用户需求

在管理后台（ContentVerify.vue）新增「重新解析」标签页，从 `analysis_note` 字段检测包含错误文本的记录，批量重新跑 LLM 文本分析。

## 核心功能

1. **检测错误记录**：查询 `analysis_note` 字段包含错误文本（JSON解析失败/解析失败/Error/error/异常/失败）的记录
2. **展示问题列表**：显示 image_id、title、analysis_note 预览、status、created_at
3. **批量重跑**：点击后用 `mode="analyze_text_only"` 入队，复用现有 tubi_worker 流程
4. **复用现有能力**：不新建子组件，不改 tubi_worker，复用 `/batch-auto-analyze` 端点

## 技术方案

### 后端修改

**文件**：`backend/app/api/tubi.py`

新增端点：

```python
@router.get("/error-analysis-list")
async def get_error_analysis_list(db: Session = Depends(get_db)):
    """
    获取 analysis_note 包含错误文本的记录列表
    用于「重新解析」功能
    """
    # SQL: LIKE 查询错误关键词
    # 返回: [{image_id, title, analysis_note, status, created_at}]
```

错误关键词黑名单：

- `JSON解析失败`、`解析失败`、`Error`、`error`、`异常`、`失败`、`None`

### 前端修改**文件**：`frontend/src/views/ContentVerify.vue`

1. 新增 tab：

```html
<el-tab-pane label="重新解析" name="reanalyze">
  <!-- 内联实现 -->
</el-tab-pane>
```

2. 内联逻辑（参考现有 tabs 风格）：

- 页面加载时自动调用 `GET /tubi/error-analysis-list`
- 显示统计数字：共 N 条错误记录
- 表格展示（image_id、title、错误内容预览、状态、时间）
- "全部重新解析" 按钮：调用 `POST /tubi/batch-auto-analyze` + `{image_ids: [...], mode: "analyze_text_only"}`
- 单条重新解析按钮（可选）

### 数据流

```
用户点击"重新解析"tab  → GET /tubi/error-analysis-list
  → 返回错误记录列表
  → 前端展示表格
  → 用户点击"全部重新解析"
  → POST /batch-auto-analyze {image_ids: [...], mode: "analyze_text_only"}
  → tubi_worker 处理（mode=analyze_text_only → 只跑 AI 点评）
  → analysis_note 更新
```

## 关键代码位置

- tubi.py 路由顺序：注意 `/{id}` 通配符在最后，`/error-analysis-list` 必须在它前面
- tubi_worker.py line 224：`if mode == "analyze_text_only":` 已支持
- ContentVerify.vue line 37-475：参考现有 tab 实现风格