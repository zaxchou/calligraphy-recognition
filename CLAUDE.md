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
- **服务器 IP:** `124.223.17.29`（域名 xcx.zhouhouhan.com 解析到的不是此 IP，部署时必须用 IP）
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

### GitHub
- **仓库:** `https://github.com/zaxchou/molin-wiki.git`
- **默认分支:** `master`
- **GitHub Token:** 已配到 GitHub MCP server 的 env，不写文件里
- **推送方式:** `git push origin master`（--force 只在明确要求时用）

### MCP 服务器
- **Memory MCP:** `@modelcontextprotocol/server-memory` — 知识图谱记忆
- **GitHub MCP:** `@modelcontextprotocol/server-github` — GitHub API 操作（已配 token）
- **两个 server 均已安装并连接成功**

### Claude-Mem（会话记忆服务）
- **用途：** 跨会话持久记忆，记录工作历史和上下文
- **端口：** `http://localhost:37777`
- **启动命令：** `npx claude-mem start`
- **停止命令：** `npx claude-mem stop`
- **状态检查：** `curl -s http://localhost:37777/api/health`
- **每次会话开始时必须检查并启动此服务！**
- **版本：** 13.4.0（插件缓存路径：`C:\Users\zax\.claude\plugins\cache\thedotmack\claude-mem\`）

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
