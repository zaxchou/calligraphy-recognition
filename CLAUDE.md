根据您的要求，将翻译内容精简至1000字以内：

# CLAUDE.md

在plan模式下请你在回答前，先问我问题。要求：一次只问一个问题。根据我的回答，继续追问。直到你有95%的信心理解我的真实需求和目标。然后才给出方案

## 1. 先想后做

- 明确说出你的假设。不确定就问。
- 如有多种理解，全部列出——不要偷偷替用户选。
- 如有更简单的方法，直接说。不合理的要质疑。
- 不清楚就停下来，说出困惑并提问。

## 2. 简单至上

- 只写最少代码，不写推测性内容
- 不加未要求的功能、抽象、灵活性、配置
- 不为不可能的场景写错误处理
- 200行能写成50行，就重写

自问：“资深工程师会觉得太复杂吗？” 是，就简化。

## 3. 精准修改

- 不改动无关代码、注释、格式
- 不重构没坏的东西
- 遵循现有风格，即使你偏好不同
- 发现无关废弃代码可提，但别删

你改动后：

- 删除因你的修改变得无用的导入/变量/函数
- 除非用户要求，否则不删已有的废弃代码

检验：每个改动行必须能直接追溯到用户需求。

## 4. 目标驱动执行

把任务转为可验证的目标：

- “加校验” → “为无效输入写测试，然后让测试通过”
- “修bug” → “写复现测试，然后让测试通过”
- “重构X” → “确保测试在前后都通过”

多步任务给简要计划：

```
1. [步骤] → 验证：[检查项]
2. [步骤] → 验证：[检查项]
3. [步骤] → 验证：[检查项]
```

好的成功标准让你能独立循环。模糊的标准（“把它做好”）会让你不断请求澄清。

***

**生效的标志：** 增量的不必要改动减少，因过度复杂导致的重写减少，澄清问题出现在实现之前而非犯错之后。

## 项目记忆（不要忘记）

### 服务器部署
- **服务器 IP:** `124.223.17.29`
- **域名:** `molin.wiki`（已备案，替代 xcx.zhouhouhan.com）
- **SSH 用户:** `ubuntu`，端口 `22`
- **SSH 密钥:** `cali_cloud_20260503.pem`（在项目根目录，已复制到 `~/.ssh/`）
- **SSH 别名:** `xcx`（配置在 `~/.ssh/config`）
- **部署: `bash deploy.sh`** — 自动检测变更，只做必要的事
  - 前端有变更：build + SCP
  - 后端有变更：SCP 源码 + Docker restart（**不需** rebuild）
  - Dockerfile 有变更：自动做完整 Docker rebuild
- 后端代码通过 volume 热挂载进容器，改源码秒级生效
- **服务器路径:** `/opt/molin-wiki`
- **cron 保险:** 服务器每 5 分钟自动检查更新（仅当 deploy.sh 没跑时兜底）
- **nginx 注意:** `location ^~ /api/` 必须优先于图片正则规则

### GitHub
- **仓库:** `https://github.com/zaxchou/molin-wiki.git`
- **默认分支:** `master`
- **GitHub Token:** `GH_TOKEN` 环境变量（已在 `~/.bashrc` 持久化）
- **GitHub CLI:** `gh` v2.93.0，安装在 `C:/Users/zax/.local/bin/gh.exe`
- **推送方式:** `git push origin master`（--force 只在明确要求时用）
- **gh 常用:** `gh repo view`、`gh pr list`、`gh api ...`

### MCP 服务器
- **Memory MCP:** `@modelcontextprotocol/server-memory` — 知识图谱记忆
- **GitHub CLI:** `gh` v2.93.0 — GitHub API 操作（已配 token）

### Claude-Mem（会话记忆服务）
- **用途：** 跨会话持久记忆，记录工作历史和上下文
- **端口：** `http://localhost:37777`
- **启动命令：** `npx claude-mem start`
- **停止命令：** `npx claude-mem stop`
- **状态检查：** `curl -s http://localhost:37777/api/health`
- **每次会话开始时必须检查并启动此服务！**
- **版本：** 13.4.0（所在路径：`C:\Users\zax\.claude\plugins\marketplaces\thedotmack\plugin\`）
- **重要：当用户说"启动服务"时，必须同时做两件事：** (1) `npx claude-mem start` (2) 触发 hooks 加载context。一步到位，不要让用户说第二次。
- **已知坑：** hooks 命令中的路径必须指向 `marketplaces` 目录（不是 `cache`），cache 目录已删掉避免混乱

### 权限模型

```
角色          可以编辑/删除        可以提交修改建议    可以上传作品
──────────────────────────────────────────────────────────────────
super_admin   所有作品              ✅                  ✅
admin         所有作品              ✅                  ✅
editor        仅自己的作品          ✅                  ✅
reader        ❌                   ✅                  ❌
guest         ❌                   ❌                  ❌
```

- "自己的作品" = `item.owner_id === authStore.userId`
- 所有编辑/删除按钮在前端使用 `canEditItem(item)` 函数判断：`authStore.isAdmin || (authStore.isEditor && item.owner_id === authStore.userId)`
- admin 账号: 手机号 `13800138000`，密码 `ilovehouhan`，角色 `super_admin`（通过 JWT 登录）

### 知识库搜索（Qdrant）数据一致性问题

#### 根因（曾导致搜索返回 0 条结果）
- Qdrant 重建（`deploy/fast_reindex.py`）时会给每条文本块**生成新的 UUID 作为 `vector_id`**
- 但 SQLite `text_chunks` 表的 `vector_id` 列仍保留**旧的 UUID**
- 后端搜索时先查到 Qdrant 向量（新 UUID），再去 SQLite 查 `book_id + vector_id` 匹配 → **0/20 匹配** → 所有结果被当成"孤立向量"过滤掉

#### 预防措施（换服务器 / 重建 Qdrant 后）
1. **核心原则：** 重建 Qdrant 后必须让 `text_chunks.vector_id` 与 Qdrant 的 `id` 同步
2. **正确做法：**
   ```
   跑完 fast_reindex.py 后，执行以下 SQL 更新 vector_id：
   UPDATE text_chunks SET vector_id = ( 
     SELECT SUBSTR(id, 1, 36) FROM knowledge_texts_scroll 
     WHERE payload->>'$.book_id' = text_chunks.book_id 
       AND payload->>'$.chunk_index' = CAST(text_chunks.chunk_index AS TEXT) 
   ) WHERE EXISTS ( ...匹配条件... );
   ```
   （实际操作用 Python 脚本：从 Qdrant scroll 出所有 `id + book_id + chunk_index`，逐条更新 SQLite）
3. **应急方案（已实现）：** 后端 `knowledge_api.py` 有"孤立向量回退"逻辑——当 SQLite 查不到匹配时，直接从 Qdrant 的 payload 构建搜索结果（含书名、配图、上下文）。此方案能工作但依赖 payload 的完整性
4. **判断是否发生此问题：** 搜索知识库返回 `results: []` 但 `ai_summary` 有内容，日志中出现 `"跳过孤立向量"` 或 `"孤立向量"`

### 情感分析架构（重要！不要搞混）

**核心原则：LLM 为主，词库兜底。**

```
优先级：LLM 独立判断 > 词库引擎基线
```

- 有 LLM 分析 → 直接用 LLM 绝对分（-8到+8）作为最终维度分
- 无 LLM（调用失败/超时） → 降级到词库引擎基线分
- **不要用** `apply_corrections`（词库基线 + LLM delta 的混合模式），那是旧架构

**分数计算公式：**
```
combined_score = Σ(wᵢ × cᵢ × sᵢ) / Σ(wᵢ × cᵢ)
vader_normalized = combined_score / √(combined_score² + 8)
```
- wᵢ = 维度权重（存储在 `combined_sentiment.weights`）
- cᵢ = 维度置信度（存储在 `combined_sentiment.dimension_confidence`）
- sᵢ = 维度分数（LLM 绝对分，或词库基线分）

**数据流：**
1. `correct_dimensions()` → LLM 返回 `{scores: {text: {score, reasoning}, ...}, summary, polarity}`
2. 用 LLM scores 做加权平均 → `combined_score` + `vader_normalized`
3. 存入 `combined_sentiment`（维度分 + 归一化分 + weights + dimension_confidence）
4. 存入 `llm_analysis`（corrections + summary + meta）

**前端 formula-table：**
- 维度分 = `combined_sentiment.text_score` 等（LLM 绝对分）
- 权重 = `combined_sentiment.weights`
- 置信度 = `combined_sentiment.dimension_confidence`（不是 has_data）
- 展开行 = 词库信号 + LLM reasoning

**batch 脚本（batch_absolute_reanalyze.py）：**
- 和 production 路径用同一个 SYSTEM_PROMPT
- 用加权平均（不是简单平均）计算 combined_score
- 存储 dimension_confidence 和 weights

## Obsidian 记忆库（E:\mynote\Project\）

**自动写入机制：**
- **会话结束时**：Stop hook 自动提醒检查并写入
- **每天 22:03**：cron 任务从 claude-mem 数据库汇总当天工作写入（7天过期，需续期）

每次对话结束前，检查是否有需要写入记忆库的内容。目录结构见 `E:\mynote\Project\AGENTS.md`。

### 记忆写入规则
当出现以下内容时，写入 `E:\mynote\Project\` 对应目录：
- **长期有效的项目决策** → `decisions/<决策名>.md` + 更新 `memory/decisions.md` 索引
- **用户明确确认的偏好** → `memory/goals.md` 或 `memory/decisions.md`
- **已经验证有效的工作流** → `memory/style-guide.md` 或 `templates/`
- **被否定的方案及原因** → `decisions/<决策名>.md`（"被否决的方案"章节）
- **内容模板、Prompt模板、脚本模板** → `templates/<模板名>.md`
- **项目目录结构和命名规范** → `projects/<项目名>/README.md`

### 不要写入
APIKey、密码（admin 账号除外）、支付信息、银行信息、私人聊天、临时想法、未确认的猜测。

### 写入格式
每个 .md 文件开头加 Obsidian frontmatter：
```yaml
---
tags: [memory, <分类>]
created: YYYY-MM-DD
---
```

<!-- superpowers-zh:begin (do not edit between these markers) -->
# Superpowers-ZH 中文增强版

本项目已安装 superpowers-zh 技能框架（20 个 skills）。

## 核心规则

1. **收到任务时，先检查是否有匹配的 skill** — 哪怕只有 1% 的可能性也要检查
2. **设计先于编码** — 收到功能需求时，先用 brainstorming skill 做需求分析
3. **测试先于实现** — 写代码前先写测试（TDD）
4. **验证先于完成** — 声称完成前必须运行验证命令

## 可用 Skills

Skills 位于 `.claude/skills/` 目录，每个 skill 有独立的 `SKILL.md` 文件。

- **brainstorming**: 在任何创造性工作之前必须使用此技能——创建功能、构建组件、添加功能或修改行为。在实现之前先探索用户意图、需求和设计。
- **chinese-code-review**: 中文 review 沟通参考——话术模板、分级标注（必须修复/建议修改/仅供参考）、国内团队常见反模式应对。仅在用户显式 /chinese-code-review 时调用，不要根据上下文自动触发。
- **chinese-commit-conventions**: 中文 commit 与 changelog 配置参考——Conventional Commits 中文适配、commitlint/husky/commitizen 中文模板、conventional-changelog 中文配置。仅在用户显式 /chinese-commit-conventions 时调用，不要根据上下文自动触发。
- **chinese-documentation**: 中文文档排版参考——中英文空格、全半角标点、术语保留、链接格式、中文文案排版指北约定。仅在用户显式 /chinese-documentation 时调用，不要根据上下文自动触发。
- **chinese-git-workflow**: 国内 Git 平台配置参考——Gitee、Coding.net、极狐 GitLab、CNB 的 SSH/HTTPS/凭据/CI 接入差异与镜像同步配置。仅在用户显式 /chinese-git-workflow 时调用，不要根据上下文自动触发。
- **dispatching-parallel-agents**: 当面对 2 个以上可以独立进行、无共享状态或顺序依赖的任务时使用
- **executing-plans**: 当你有一份书面实现计划需要在单独的会话中执行，并设有审查检查点时使用
- **finishing-a-development-branch**: 当实现完成、所有测试通过、需要决定如何集成工作时使用——通过提供合并、PR 或清理等结构化选项来引导开发工作的收尾
- **mcp-builder**: MCP 服务器构建方法论 — 系统化构建生产级 MCP 工具，让 AI 助手连接外部能力
- **receiving-code-review**: 收到代码审查反馈后、实施建议之前使用，尤其当反馈不明确或技术上有疑问时——需要技术严谨性和验证，而非敷衍附和或盲目执行
- **requesting-code-review**: 完成任务、实现重要功能或合并前使用，用于验证工作成果是否符合要求
- **subagent-driven-development**: 当在当前会话中执行包含独立任务的实现计划时使用
- **systematic-debugging**: 遇到任何 bug、测试失败或异常行为时使用，在提出修复方案之前执行
- **test-driven-development**: 在实现任何功能或修复 bug 时使用，在编写实现代码之前
- **using-git-worktrees**: 当需要开始与当前工作区隔离的功能开发，或在执行实现计划之前使用——通过原生工具或 git worktree 回退机制确保隔离工作区存在
- **using-superpowers**: 在开始任何对话时使用——确立如何查找和使用技能，要求在任何响应（包括澄清性问题）之前调用 Skill 工具
- **verification-before-completion**: 在宣称工作完成、已修复或测试通过之前使用，在提交或创建 PR 之前——必须运行验证命令并确认输出后才能声称成功；始终用证据支撑断言
- **workflow-runner**: 在 Claude Code / OpenClaw / Cursor 中直接运行 agency-orchestrator YAML 工作流——无需 API key，使用当前会话的 LLM 作为执行引擎。当用户提供 .yaml 工作流文件或要求多角色协作完成任务时触发。
- **writing-plans**: 当你有规格说明或需求用于多步骤任务时使用，在动手写代码之前
- **writing-skills**: 当创建新技能、编辑现有技能或在部署前验证技能是否有效时使用

## 如何使用

当任务匹配某个 skill 时，使用 `Skill` 工具加载对应 skill 并严格遵循其流程。绝不要用 Read 工具读取 SKILL.md 文件。

如果你认为哪怕只有 1% 的可能性某个 skill 适用于你正在做的事情，你必须调用该 skill 检查。
<!-- superpowers-zh:end -->
