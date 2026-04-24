"""
文本/图像向量化服务
文本：阿里云百炼 text-embedding-v3（OpenAI 兼容格式，默认 1024 维）
图像：阿里云 DashScope multimodal-embedding-v1（通过 dashscope SDK）

改进 (2026-03-29):
- 改用 requests 同步 HTTP 调用（Python 3.14 上 httpx.AsyncClient 不稳定）
- 通过 asyncio.to_thread 在线程池中运行同步调用
- 基于 content-hash 的 embedding 缓存，避免重复 API 调用
- 指数退避重试

改进 (2026-04-10):
- 图像 embedding 从零向量升级为 DashScope multimodal-embedding-v1 真实向量
- 使用 dashscope SDK（SDK 内部处理文件上传/OSS 签名，HTTP 直接调用会 500）
- 降级开关 DASHSCOPE_MULTIMODAL_ENABLED，false 时回退到零向量
- 文本 embedding 从智谱 embedding-3 切换到阿里云 text-embedding-v3
  （智谱 embedding-3 默认维度从 1024 改为 2048，且需额外指定 dimensions 参数）
  （阿里云 text-embedding-v3 默认 1024 维，与 Qdrant 集合一致，无需额外参数）
"""

import asyncio
import hashlib
import json
import logging
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingResult:
    """向量化结果"""
    embedding: List[float]
    text: Optional[str] = None
    image_url: Optional[str] = None
    dimensions: int = 0
    cache_hit: bool = False  # 是否命中缓存
    
    def __post_init__(self):
        if self.embedding:
            self.dimensions = len(self.embedding)


class EmbeddingService:
    """向量化服务

    改进点:
    - requests 同步调用 + asyncio.to_thread（Python 3.14 兼容）
    - 基于 content-hash 的 embedding 缓存
    - 指数退避重试
    - 文本和图像统一使用阿里云百炼平台（QWEN_API_KEY）
    """

    # 阿里云百炼文本 Embedding API（OpenAI 兼容格式）— 文本用
    DASHSCOPE_TEXT_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings"
    # 阿里云 DashScope 多模态 Embedding API — 图像用
    DASHSCOPE_MULTIMODAL_API_URL = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/multimodal-embedding/multimodal-embedding"
    DEFAULT_MODEL = "text-embedding-v3"  # 默认 1024 维
    MULTIMODAL_MODEL = "multimodal-embedding-v1"
    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 1.0  # 秒
    HTTP_TIMEOUT = 60  # 秒

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        初始化向量化服务

        Args:
            api_key: 阿里云百炼 API Key，默认从环境变量 QWEN_API_KEY 读取
            model: 文本 Embedding 模型名称，默认 text-embedding-v3
        """
        # 阿里云百炼 API Key（文本 + 图像 embedding 共用 QWEN_API_KEY）
        if api_key:
            self.api_key = api_key
        else:
            try:
                from app.core.config import get_settings
                settings = get_settings()
                self.api_key = settings.QWEN_API_KEY
            except Exception:
                self.api_key = None

            if not self.api_key:
                self.api_key = os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY", "")

        if not self.api_key:
            raise ValueError("阿里云百炼 API Key 未设置（请设置 QWEN_API_KEY 环境变量）")

        # DashScope 多模态开关（图像 embedding 用）
        try:
            from app.core.config import get_settings
            settings = get_settings()
            self.multimodal_enabled = settings.DASHSCOPE_MULTIMODAL_ENABLED
        except Exception:
            self.multimodal_enabled = os.getenv("DASHSCOPE_MULTIMODAL_ENABLED", "true").lower() in ("1", "true", "yes", "y")

        self.model = model or self.DEFAULT_MODEL
        # 统一使用阿里云百炼 API Key 的 headers
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        # embedding 缓存: hash(str) -> List[float]
        self._cache: Dict[str, List[float]] = {}
        self._cache_hits = 0
        self._cache_misses = 0
        # 持久化缓存路径
        self._cache_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "data", ".embedding_cache")
        self._load_persistent_cache()
    
    def _load_persistent_cache(self):
        """从磁盘加载持久化缓存"""
        try:
            cache_file = os.path.join(self._cache_dir, f"{self.model}.json")
            if os.path.exists(cache_file):
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._cache = data.get("cache", {})
                logger.info("加载 embedding 持久化缓存: %d 条 (model=%s)", len(self._cache), self.model)
        except Exception as e:
            logger.warning("加载 embedding 持久化缓存失败: %s", e)
            self._cache = {}
    
    def _save_persistent_cache(self):
        """将缓存持久化到磁盘"""
        try:
            os.makedirs(self._cache_dir, exist_ok=True)
            cache_file = os.path.join(self._cache_dir, f"{self.model}.json")
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump({"cache": self._cache, "model": self.model}, f, ensure_ascii=False)
            logger.debug("保存 embedding 持久化缓存: %d 条", len(self._cache))
        except Exception as e:
            logger.warning("保存 embedding 持久化缓存失败: %s", e)

    def _sync_post(self, url: str, headers: dict, json_data: dict) -> dict:
        """同步 POST 请求（在线程池中运行）"""
        response = requests.post(url, headers=headers, json=json_data, timeout=self.HTTP_TIMEOUT)
        if response.status_code != 200:
            # 记录详细错误信息
            logger.error("API 请求失败: status=%d, url=%s, body=%s",
                        response.status_code, url, response.text[:500])
        response.raise_for_status()
        return response.json()
    
    def _text_hash(self, text: str) -> str:
        """计算文本内容的 hash，用于缓存（包含模型名，切换模型后缓存自动失效）"""
        return hashlib.sha256(f"{self.model}:{text}".encode("utf-8")).hexdigest()
    
    def _image_hash(self, image_path: str) -> str:
        """计算图像文件的 hash，用于缓存"""
        # 用文件路径 + 修改时间作为缓存键（轻量级，无需读取文件）
        try:
            mtime = os.path.getmtime(image_path)
            return hashlib.sha256(f"{self.model}:{image_path}:{mtime}".encode("utf-8")).hexdigest()
        except OSError:
            return hashlib.sha256(f"{self.model}:{image_path}".encode("utf-8")).hexdigest()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total * 100) if total > 0 else 0
        return {
            "cache_size": len(self._cache),
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "hit_rate": f"{hit_rate:.1f}%",
        }
    
    async def embed_texts(self, 
                          texts: List[str], 
                          batch_size: int = 10) -> List[EmbeddingResult]:
        """
        批量文本向量化
        
        Args:
            texts: 文本列表
            batch_size: 批处理大小
        
        Returns:
            向量化结果列表
        """
        results = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            # 先检查缓存
            cached_results = []
            uncached_texts = []
            uncached_indices = []
            
            for idx, text in enumerate(batch):
                h = self._text_hash(text)
                if h in self._cache:
                    self._cache_hits += 1
                    cached_results.append((idx, EmbeddingResult(
                        embedding=self._cache[h],
                        text=text,
                        dimensions=len(self._cache[h]),
                        cache_hit=True,
                    )))
                else:
                    self._cache_misses += 1
                    uncached_texts.append(text)
                    uncached_indices.append(idx)
            
            # 对未命中的文本调用 API
            if uncached_texts:
                batch_results = await self._embed_batch_with_retry(uncached_texts)
                
                # 写入缓存
                for text, result in zip(uncached_texts, batch_results):
                    h = self._text_hash(text)
                    self._cache[h] = result.embedding
                
                for idx, result in zip(uncached_indices, batch_results):
                    cached_results.append((idx, result))
            
            # 按原始顺序排列
            cached_results.sort(key=lambda x: x[0])
            results.extend([r for _, r in cached_results])
            
            # 异步限流，避免请求过快
            if i + batch_size < len(texts):
                await asyncio.sleep(0.1)
        
        if results:
            logger.debug("embed_texts 完成: %d 条, 缓存统计: %s", 
                        len(results), self.get_cache_stats())
        
        # 批量结束后持久化缓存（如果有新数据）
        if self._cache_misses > 0:
            self._save_persistent_cache()
        
        return results
    
    async def _embed_batch_with_retry(self, texts: List[str]) -> List[EmbeddingResult]:
        """带指数退避重试的批量嵌入"""
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                return await self._embed_batch(texts)
            except Exception as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning("Embedding API 请求失败 (尝试 %d/%d), %s 秒后重试: %s",
                                  attempt + 1, self.MAX_RETRIES, delay, e)
                    await asyncio.sleep(delay)
                else:
                    logger.error("Embedding API 重试 %d 次均失败: %s", self.MAX_RETRIES, e)
        raise last_error  # type: ignore

    async def _embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        """批量嵌入内部实现（使用 requests 同步调用 + asyncio.to_thread）
        使用阿里云百炼 text-embedding-v3（OpenAI 兼容格式），默认 1024 维
        """
        payload = {
            "model": self.model,
            "input": texts,
            "encoding_format": "float",
        }

        # 使用 asyncio.to_thread 在线程池中运行同步 requests 调用
        data = await asyncio.to_thread(self._sync_post, self.DASHSCOPE_TEXT_API_URL, self.headers, payload)

        if "data" not in data:
            raise Exception(f"Embedding API 返回格式错误: {data}")

        embeddings = data["data"]

        results = []
        for idx, emb in enumerate(embeddings):
            results.append(EmbeddingResult(
                embedding=emb["embedding"],
                text=texts[idx] if idx < len(texts) else None,
                dimensions=len(emb["embedding"])
            ))

        return results
    
    async def embed_text(self, text: str) -> EmbeddingResult:
        """
        单条文本向量化
        
        Args:
            text: 输入文本
        
        Returns:
            向量化结果
        """
        results = await self.embed_texts([text])
        return results[0]
    
    async def embed_image(self, image_path: str) -> EmbeddingResult:
        """
        图像向量化

        优先使用 DashScope multimodal-embedding-v1 API 获取真实图像向量。
        若 DASHSCOPE_MULTIMODAL_ENABLED=false 或 API 调用失败，降级到零向量。

        Args:
            image_path: 图像文件路径

        Returns:
            向量化结果（1024 维）
        """
        # 检查降级开关
        if not self.multimodal_enabled:
            logger.debug("DashScope 多模态 Embedding 已禁用，降级到零向量: %s", image_path)
            return EmbeddingResult(
                embedding=[0.0] * 1024,
                image_url=image_path,
                dimensions=1024,
            )

        # 检查 API Key（现在文本和图像统一使用 QWEN_API_KEY）
        if not self.api_key:
            logger.warning("DashScope API Key 未设置（QWEN_API_KEY），图像 embedding 降级到零向量: %s", image_path)
            return EmbeddingResult(
                embedding=[0.0] * 1024,
                image_url=image_path,
                dimensions=1024,
            )

        # 检查缓存
        h = self._image_hash(image_path)
        cache_key = f"img:{h}"
        if cache_key in self._cache:
            self._cache_hits += 1
            return EmbeddingResult(
                embedding=self._cache[cache_key],
                image_url=image_path,
                dimensions=len(self._cache[cache_key]),
                cache_hit=True,
            )

        self._cache_misses += 1

        # 调用 DashScope multimodal API
        try:
            result = await self._embed_image_dashscope(image_path)
            if result and result.embedding and len(result.embedding) == 1024:
                # 写入缓存
                self._cache[cache_key] = result.embedding
                self._save_persistent_cache()
                return result
            else:
                logger.warning("DashScope 图像 embedding 返回维度异常: %d，降级到零向量: %s",
                             len(result.embedding) if result else 0, image_path)
                return EmbeddingResult(embedding=[0.0] * 1024, image_url=image_path, dimensions=1024)
        except Exception as e:
            logger.error("DashScope 图像 embedding 失败: %s，降级到零向量: %s", e, image_path)
            return EmbeddingResult(embedding=[0.0] * 1024, image_url=image_path, dimensions=1024)

    async def _embed_image_dashscope(self, image_path: str) -> EmbeddingResult:
        """
        调用 DashScope multimodal-embedding-v1 SDK 获取图像向量

        使用 dashscope SDK（而非 HTTP 直接调用），因为 SDK 内部处理文件上传/OSS 签名。
        支持本地图片路径和 URL 图片。
        输出固定 1024 维，与 knowledge_images collection 兼容。

        Args:
            image_path: 图像文件路径或 URL

        Returns:
            EmbeddingResult
        """
        import dashscope
        from dashscope import MultiModalEmbedding
        from dashscope.embeddings.multimodal_embedding import MultiModalEmbeddingItemImage

        # 设置 API Key
        dashscope.api_key = self.api_key

        # 本地文件需要用绝对路径
        if not image_path.startswith(("http://", "https://")):
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"图像文件不存在: {image_path}")
            image_input = os.path.abspath(image_path)
        else:
            image_input = image_path

        # 带重试的 SDK 调用
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                # SDK 是同步调用，包装到线程池
                result = await asyncio.to_thread(
                    MultiModalEmbedding.call,
                    model=self.MULTIMODAL_MODEL,
                    input=[MultiModalEmbeddingItemImage(image=image_input, factor=1.0)],
                )
                break
            except Exception as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning("DashScope 图像 embedding 请求失败 (尝试 %d/%d), %s 秒后重试: %s",
                                  attempt + 1, self.MAX_RETRIES, delay, e)
                    await asyncio.sleep(delay)
                else:
                    raise last_error

        # 检查 SDK 返回状态
        if result.status_code != 200:
            raise Exception(f"DashScope API 错误: code={result.code}, message={result.message}")

        # 解析响应
        embeddings = result.output.get("embeddings", [])
        if not embeddings:
            raise Exception(f"DashScope API 返回空 embeddings")

        vec = embeddings[0].get("embedding", [])
        if not vec:
            raise Exception(f"DashScope API 返回空向量: {embeddings[0]}")

        logger.info("DashScope 图像 embedding 成功: %s, 维度=%d", image_path, len(vec))
        return EmbeddingResult(
            embedding=vec,
            image_url=image_path,
            dimensions=len(vec),
        )
    
    def embed_texts_sync(self, texts: List[str], batch_size: int = 10) -> List[EmbeddingResult]:
        """同步版本：批量文本向量化"""
        return asyncio.run(self.embed_texts(texts, batch_size))

    def embed_text_sync(self, text: str) -> EmbeddingResult:
        """同步版本：单条文本向量化"""
        return asyncio.run(self.embed_text(text))

    def embed_image_sync(self, image_path: str) -> EmbeddingResult:
        """同步版本：图像向量化（用于 Celery worker 等非异步环境）"""
        return asyncio.run(self.embed_image(image_path))


# 便捷函数
async def get_embeddings(texts: List[str], 
                         api_key: Optional[str] = None) -> List[List[float]]:
    """
    获取文本嵌入向量的便捷函数
    
    Args:
        texts: 文本列表
        api_key: API Key（可选）
    
    Returns:
        向量列表
    """
    service = EmbeddingService(api_key=api_key)
    results = await service.embed_texts(texts)
    return [r.embedding for r in results]


def get_embeddings_sync(texts: List[str], 
                        api_key: Optional[str] = None) -> List[List[float]]:
    """同步版本"""
    import asyncio
    return asyncio.run(get_embeddings(texts, api_key))


# 测试代码
if __name__ == "__main__":
    import asyncio
    
    async def test():
        # 测试文本向量化
        texts = [
            "中国写意花鸟画注重笔墨情趣",
            "构图是绘画的重要元素",
            "墨分五色，浓淡干湿焦",
        ]
        
        service = EmbeddingService()
        results = await service.embed_texts(texts)
        
        for idx, result in enumerate(results):
            print(f"[{idx}] 维度: {result.dimensions}")
            print(f"    前5个值: {result.embedding[:5]}")
            print(f"    文本: {result.text[:30]}...")
            print()
    
    # 运行测试
    asyncio.run(test())
