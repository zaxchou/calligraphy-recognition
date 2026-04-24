"""
阿里云百炼智能体调用服务
使用 DashScope SDK 的 Application.call() 方法
支持流式输出和多轮对话（session_id）

注意：DashScope SDK 的 Application.call() 是同步接口，
在 FastAPI async 端点中通过 asyncio.Queue + 线程池桥接，
实现真正的实时流式输出，避免阻塞事件循环。
"""

import os
import json
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

# 百炼智能体配置
BAILIAN_APP_ID = "b259c13c595445d59bb35efd2afc818f"

# 专用线程池（避免阻塞 uvicorn 事件循环）
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="bailian")

# 队列哨兵：标记流结束
_SENTINEL = None


def _call_stream_to_queue(prompt: str, session_id: str, queue: asyncio.Queue):
    """
    在线程池中运行同步的 DashScope SDK 调用，
    将每个 SSE 事件实时放入 asyncio.Queue
    """
    from http import HTTPStatus
    from dashscope import Application

    try:
        api_key = os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY", "")
        if not api_key:
            queue.put_nowait(_sse_event("error", {"message": "API Key 未配置 (QWEN_API_KEY)"}))
            return

        kwargs = {
            "api_key": api_key,
            "app_id": BAILIAN_APP_ID,
            "prompt": prompt,
            "stream": True,
            "incremental_output": True,
        }
        if session_id:
            kwargs["session_id"] = session_id

        responses = Application.call(**kwargs)

        for response in responses:
            if response.status_code != HTTPStatus.OK:
                logger.error(
                    "百炼智能体调用失败: request_id=%s, code=%s, message=%s",
                    response.request_id, response.status_code, response.message
                )
                queue.put_nowait(_sse_event("error", {
                    "message": response.message or "调用失败",
                    "code": str(response.status_code),
                }))
                return

            # 提取文本和 session_id
            text = response.output.text if response.output else ""
            new_session_id = response.output.session_id if response.output else ""

            if text:
                queue.put_nowait(_sse_event("text", {"content": text}))

            # 在最后一个 chunk 发送 session_id（finish_reason == "stop"）
            if response.output and response.output.finish_reason == "stop":
                queue.put_nowait(_sse_event("done", {
                    "session_id": new_session_id,
                    "finish_reason": "stop",
                }))

    except Exception as e:
        logger.error("百炼智能体流式调用异常: %s", e, exc_info=True)
        try:
            queue.put_nowait(_sse_event("error", {"message": f"服务异常: {str(e)}"}))
        except Exception:
            pass
    finally:
        # 发送结束哨兵
        queue.put_nowait(_SENTINEL)


async def chat_stream(prompt: str, session_id: str = None) -> AsyncGenerator[str, None]:
    """
    调用百炼智能体，流式返回 SSE 事件

    通过 asyncio.Queue + ThreadPoolExecutor 桥接同步 SDK 和异步框架，
    实现 DashScope 流式响应的实时转发。

    Args:
        prompt: 用户输入文本
        session_id: 会话 ID（首轮不传，后续从上一轮响应中获取）

    Yields:
        SSE 格式的事件字符串
    """
    loop = asyncio.get_event_loop()
    queue = asyncio.Queue()

    # 在线程池中启动同步调用
    loop.run_in_executor(
        _executor,
        _call_stream_to_queue,
        prompt,
        session_id,
        queue,
    )

    # 从队列实时读取事件
    while True:
        event = await queue.get()
        if event is _SENTINEL:
            break
        yield event


def _sse_event(event: str, data: dict) -> str:
    """格式化 SSE 事件"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
