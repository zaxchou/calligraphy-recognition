# 起承转合：用户自定义Markdown知识注入 + LLM/GLM分工优化

## 一、目标

1. **用户自定义起承转合markdown** 作为额外知识来源，与现有Qdrant知识库一起注入LLM prompt
2. **LLM（Qwen）专注定性文字分析**：说清楚起承转合分别在图像的什么位置、为什么，不再输出精确坐标JSON
3. **GLM Turbo V 专注定量坐标定位**：接收LLM文字分析作为引导，输出精确坐标并生成标注图
4. **Prompt展示**：可选功能，报告中显示/隐藏LLM分析时使用的prompt

## 二、架构调整

```
当前管线:
  Qdrant搜索 ─┐
  pan.md规则 ─┼──→ Qwen Prompt ──→ 文字分析 + 坐标JSON ──→ 报告
  原图base64 ─┘                         │
                                  GLM提取坐标（回退）

新管线:
  Qdrant搜索 ──────┐
  pan.md规则 ──────┤
  用户markdown ────┼──→ Qwen Prompt ──→ 纯文字分析 ──→ 报告
  原图base64 ──────┘                         │
                                        GLM Turbo V ← 文字分析引导
                                           │
                                           └──→ 精确坐标 + 标注图
```

## 三、实现步骤

### Step 1: 用户自定义Markdown的管理

**文件**: `backend/app/modules/pantianshou_composition/user_markdown.py`（新建）

- 定义 markdown 文件存放目录：`data/user_markdown/qczh/`
- 扫描该目录下所有 `.md` 文件
- 提供 `load_user_qczh_markdowns()` 函数：读取所有markdown内容，返回 `List[Dict]` 格式：
  ```python
  [{"filename": "起承转合原理.md", "content": "..."}, ...]
  ```
- 文件变更时（用户增删改md），无需重启即可生效（每次分析时扫描）

### Step 2: 将用户markdown注入Qwen Prompt

**修改文件**: `backend/app/modules/pantianshou_composition/stages.py`

在 `write_llm_narrative()` 中：
- 调用 `load_user_qczh_markdowns()` 获取用户自定义内容
- 将用户markdown内容追加到 `context_knowledge` 或作为独立字段传入

**修改文件**: `backend/app/modules/pantianshou_composition/composition_llm.py`

在 `generate_composition_narrative()` 中：
- 新增参数 `user_qczh_markdowns: List[Dict] | None = None`
- 在 prompt 中新增一个段落：

```
【用户自定义起承转合知识（来自用户整理的markdown笔记）】
{用户markdown内容拼接}
```

### Step 3: 调整Qwen Prompt — 专注定性分析

**修改文件**: `backend/app/modules/pantianshou_composition/composition_llm.py`

核心变更：
- **移除** prompt 中的起承转合坐标JSON输出要求（不再要求 `{"qi":{"x":...}}` 格式）
- **新增** 起承转合定性描述要求：

```
【起承转合分析要求】
请基于图像内容、知识库原文和用户自定义起承转合知识，分析本幅作品的起承转合：

1. **起**：势能起点在哪里？视觉注意力首先被什么吸引？（描述具体位置和物象）
2. **承**：势能如何承接发展？视线如何从起点流动？
3. **转**：势能在哪里转折变化？什么元素造成了方向或节奏的改变？
4. **合**：势能如何收束？画面如何达到平衡？
5. **路径形状**：整体走势呈什么形态？（之字形/对角线/三段式/边角/中心辐射/纵横/全景等）
6. **关键位置描述**：用自然语言描述四个关键位置的画面特征（如"起在左下角石头的顶端""转在右上方花头的朝向变化处"）

请确保分析有明确的知识依据，引用知识库原文或用户笔记中的判定标准。
```

### Step 4: 调整GLM Turbo V Prompt — 接收文字分析引导

**修改文件**: `backend/app/modules/pantianshou_composition/stages.py`

修改 `_extract_qczh_from_glm()` 函数：
- 新增参数 `llm_analysis_text: str | None = None`（Qwen的文字分析）
- 将LLM分析文本注入GLM prompt：

```
你是中国画构图专家。请基于以下分析在画面上标注起承转合四个关键位置的精确坐标。

【构图分析】
{llm_analysis_text}

请根据以上分析，在画面上找到四个关键点：

- 起(qi)：整个画面势能的起点
- 承(cheng)：势能承接发展的关键点
- 转(zhuan)：势能转折变化的转折点
- 合(he)：势能收束的终点

只返回JSON：{"qi":{"x":数字,"y":数字,"label":"起·描述"},"cheng":{"x":数字,"y":数字,"label":"承·描述"},"zhuan":{"x":数字,"y":数字,"label":"转·描述"},"he":{"x":数字,"y":数字,"label":"合·描述"},"path_shape":"形状"}
```

- 从Qwen分析文本中自动提取起承转合四点的定性描述作为label
- 坐标范围为0-100（百分比坐标，当前已有归一化逻辑）

### Step 5: 调整管线流程

**修改文件**: `backend/app/modules/pantianshou_composition/stages.py` 和 `tasks.py`

将 `draw_qczh_from_llm()` 修改为：
1. 从 `ctx.llm.text` 获取Qwen的完整分析文本
2. 将分析文本传给 `_extract_qczh_from_glm()` 作为引导
3. GLM返回精确坐标后绘制箭头覆盖图
4. 不再回退到从Qwen输出中提取JSON（因为Qwen不再输出坐标JSON）

关键流程变更：
```
llm_narrative (Qwen) → 纯文字分析 → 存入 ctx.llm.text
                                        ↓
arrow_analysis (GLM) ← 读取 ctx.llm.text 作为引导
                                        ↓
                            输出精确坐标 → 绘制标注图
```

### Step 6: LLM Prompt展示（可选功能）

**修改文件**: 
- `backend/app/modules/pantianshou_composition/composition_llm.py` — 在返回结果中附带完整的prompt文本
- `backend/app/modules/pantianshou_composition/report_builder.py` — 在report JSON中新增可选字段 `llm_prompt`
- 前端 `CompositionAnalyze.vue` — 新增折叠面板显示prompt（默认隐藏）

```python
# composition_llm.py 返回结构新增
return {
    "ok": True,
    "text": cleaned_text,
    "prompt": prompt,           # ← 完整prompt文本
    "model": model,
}
```

前端展示：在"智能专家分析"区域下方增加可折叠的"查看分析提示词"

### Step 7: 数据目录初始化

- 创建 `data/user_markdown/qczh/` 目录
- 放入一个示例markdown文件作为模板
- 用户后续可自行添加/修改该目录下的md文件

## 四、验证方式

1. 在 `data/user_markdown/qczh/` 放入测试markdown
2. 上传一张作品图片进行构图分析
3. 检查Qwen输出中的起承转合分析是否引用了用户markdown内容
4. 检查GLM标注图坐标是否与文字描述一致

## 五、涉及文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `user_markdown.py` | **新建** | 用户markdown加载模块 |
| `composition_llm.py` | 修改 | Prompt重构 + 新增参数 + 返回prompt |
| `stages.py` | 修改 | 管线调整 + GLM prompt改造 |
| `tasks.py` | 可能修改 | 管线阶段参数调整 |
| `report_builder.py` | 修改 | 新增llm_prompt字段 |
| `CompositionAnalyze.vue` | 修改 | 可选prompt展示面板 |
| `data/user_markdown/qczh/` | **新建目录** | 用户markdown存放目录 |
