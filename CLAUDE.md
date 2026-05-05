根据您的要求，将翻译内容精简至1000字以内：

# CLAUDE.md

减少大语言模型常见编码错误的行为准则。可按需与项目说明合并。

**权衡：** 本准则重谨慎、轻速度。琐碎任务请自行判断。

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
- **部署流程:**
  - `bash deploy.sh` — 完整部署（前端 build + SCP + 后端 restart，**不需** Docker rebuild）
  - `bash deploy.sh fast` — 仅前端（约 15s）
  - `bash deploy.sh --rebuild` — 完整部署 + Docker 重构（改 pip 包时用）
- 后端代码通过 volume 热挂载进容器，改源码只需 `restart`，极快
- 首次部署或改 Dockerfile 需要用 `--rebuild`
- **服务器路径:** `/opt/calligraphy-recognition`
- **cron 保险:** 服务器每 5 分钟自动检查更新（仅当 deploy.sh 没跑时兜底）

### GitHub
- **仓库:** `https://github.com/zaxchou/calligraphy-recognition.git`
- **默认分支:** `master`
- **GitHub Token:** 已配到 GitHub MCP server 的 env，不写文件里
- **推送方式:** `git push origin master`（--force 只在明确要求时用）

### MCP 服务器
- **Memory MCP:** `@modelcontextprotocol/server-memory` — 知识图谱记忆
- **GitHub MCP:** `@modelcontextprotocol/server-github` — GitHub API 操作（已配 token）
- **两个 server 均已安装并连接成功**

### Admin 密码
- 前端管理面板密码: `ilovehouhan`（存在 `useAdminAuth` composable 中，localStorage 缓存 24h）
