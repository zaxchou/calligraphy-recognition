# app/llm — LLM 统一网关（v2.0 §2.4）

全项目所有 Chat Completions 调用的唯一出口。

## 用法

```python
from app.llm import chat_completion, chat_completion_async, LLMError, parse_json_loose

# 异步（FastAPI 路由内）
data = await chat_completion_async(messages=[{"role": "user", "content": "..."}],
                                   max_tokens=1000)
# 指定供应商/模型
data = await chat_completion_async(messages=..., provider="qwen", model="qwen3.5-plus")

# LLM 输出 JSON 的宽松解析（容忍 ```json 围栏与前后缀文本）
result = parse_json_loose(data["choices"][0]["message"]["content"])
```

失败语义：**抛 `LLMError`**（重试 2 次耗尽 / 不可重试错误），不再返回 `{"error": ...}` 字典。

## 内置能力

| 能力 | 说明 |
|---|---|
| 供应商解析 | providers.py 配置驱动：auto=deepseek→qwen→zhipu；body_defaults 处理各家思考模式差异 |
| 连接复用 | 模块级 httpx 客户端单例（旧实现每次调用新建连接） |
| 重试 | 429/5xx/网络错误指数退避 + 抖动，默认 2 次重试 |
| 计量 | usage.py：每次调用记录 provider/model/延迟/tokens/成败（结构化日志 + 进程内计数器） |
| JSON 修复 | parse_json_loose |

## 存量服务迁移路线（分批进行）

| 批次 | 文件 | 状态 |
|---|---|---|
| 1（样板） | `services/qwen_llm_client.py` → 网关薄封装 | ✅ 已完成 |
| 2 | `services/deepseek_service.py`（requests 同步 → 网关） | 待做 |
| 3 | `services/siliconflow_service.py` / `siliconflow_recognition_service.py` | 待做 |
| 4 | `services/inscription_*` 系列（8 个，各自拼 prompt+调 LLM） | 待做 |
| 5 | `services/baidu_ocr_service.py`、`baidu_crawler.py`（消灭剩余同步 requests） | 待做 |
| 6 | emotion_lexicon v1/v2 并存收敛（v3 为主） | 待做 |

迁移规则：旧模块改为网关薄封装（保留旧函数签名，内部调 app.llm）；禁止在服务层直接 new httpx/requests。
