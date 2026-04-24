#!/usr/bin/env python3
"""
重新向量化 knowledge_texts 集合中的所有文本块

原因：文本 embedding 从智谱 embedding-3 切换到阿里云 text-embedding-v3，
两个模型的向量空间不同，不能混用搜索。

用法：
  python re_embed_texts.py              # 实际执行
  python re_embed_texts.py --dry-run    # 只统计，不写入
"""

import asyncio
import sys
import os
import time
import logging

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def re_embed_all(dry_run: bool = False):
    from app.modules.pantianshou_composition.embedding_service import EmbeddingService
    from app.modules.pantianshou_composition import qdrant_client

    # 1. 初始化 embedding 服务（现在用阿里云 text-embedding-v3）
    embedding_service = EmbeddingService()
    logger.info("Embedding 模型: %s", embedding_service.model)

    # 2. 统计 Qdrant 中的点数
    total = qdrant_client.count_collection(qdrant_client.KNOWLEDGE_TEXTS_COLLECTION)
    logger.info("knowledge_texts 集合中共有 %d 个点", total)

    if total == 0:
        logger.info("集合为空，无需重入库")
        return

    # 3. 分页读取所有点（需要 vector 来判断旧维度，需要 payload 来获取 content）
    all_points = []
    offset = None
    batch_size = 100
    while True:
        result = qdrant_client.scroll_collection(
            qdrant_client.KNOWLEDGE_TEXTS_COLLECTION,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vector=True,  # 需要旧向量来判断维度
        )
        points = result.get("points", [])
        all_points.extend(points)
        offset = result.get("next_page_offset")
        if not offset or not points:
            break
        logger.info("已读取 %d/%d 个点...", len(all_points), total)

    logger.info("共读取 %d 个点", len(all_points))

    # 4. 检查旧向量维度
    old_dims = set()
    for p in all_points:
        vec = p.get("vector", [])
        if vec:
            old_dims.add(len(vec))
    logger.info("旧向量维度分布: %s", old_dims)

    # 5. 提取所有文本内容
    texts = []
    for p in all_points:
        payload = p.get("payload", {})
        content = payload.get("content", "")
        if content:
            texts.append(content)
        else:
            texts.append("")  # 空内容的占位

    non_empty = sum(1 for t in texts if t)
    logger.info("非空文本: %d / %d", non_empty, len(texts))

    if dry_run:
        logger.info("[DRY RUN] 不执行重入库，退出")
        return

    # 6. 批量重新向量化
    logger.info("开始重新向量化 %d 条文本...", len(texts))
    start_time = time.time()

    results = await embedding_service.embed_texts(texts, batch_size=10)

    elapsed = time.time() - start_time
    logger.info("向量化完成，耗时 %.1f 秒", elapsed)

    # 7. 构建新的 points 并 upsert
    new_points = []
    for i, (point, embed_result) in enumerate(zip(all_points, results)):
        new_points.append({
            "id": point["id"],
            "vector": embed_result.embedding,
            "payload": point.get("payload", {}),
        })

    # 分批 upsert（每批 50 个）
    upsert_batch_size = 50
    success_count = 0
    fail_count = 0
    for i in range(0, len(new_points), upsert_batch_size):
        batch = new_points[i:i + upsert_batch_size]
        ok = qdrant_client.upsert_points(qdrant_client.KNOWLEDGE_TEXTS_COLLECTION, batch)
        if ok:
            success_count += len(batch)
        else:
            fail_count += len(batch)
            logger.error("Upsert 失败: 第 %d-%d 条", i, i + len(batch))
        logger.info("Upsert 进度: %d/%d", min(i + upsert_batch_size, len(new_points)), len(new_points))

    logger.info("重入库完成！成功: %d, 失败: %d, 耗时: %.1f 秒", success_count, fail_count, time.time() - start_time)


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    asyncio.run(re_embed_all(dry_run))
