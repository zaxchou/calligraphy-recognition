"""
重新审核 knowledge_figure 的图片元数据
========================================
使用 Qwen VL 模型识别每张图的实际内容，修正错误的 artist/artwork_title 标签。

用法:
  python re_audit_figures.py              # 干跑模式，只显示需要修改的条目
  python re_audit_figures.py --apply      # 实际写入修正后的 metadata
  python re_audit_figures.py --apply --sync-qdrant  # 写入 + 同步到 Qdrant
  python re_audit_figures.py --from N     # 从第N张开始（用于断点续传）

依赖: QWEN_API_KEY 已配置在 .env 中
"""

import argparse
import asyncio
import base64
import json
import os
import sys
import time
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image

# ---------------------------------------------------------------------------
# 路径配置
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent  # backend/
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

from app.core.config import get_settings
settings = get_settings()

META_PATH = BASE_DIR / "data" / "knowledge" / "figure_metadata.json"
IMG_BASE_DIR = BASE_DIR / "data" / "knowledge" / "extracted" / "899591682ff741588ba7017d69188ef1"

OUTPUT_PATH = BASE_DIR / "data" / "knowledge" / "figure_metadata_audited.json"

# ---------------------------------------------------------------------------
# LLM 配置
# ---------------------------------------------------------------------------
API_KEY = settings.QWEN_API_KEY or ""
BASE_URL = (settings.QWEN_BASE_URL or "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/")
MODEL = "qwen-vl-plus"  # 性价比高，图片理解够用

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """你是一位中国书画鉴定专家和美术教育专家。你的任务是分析一张来自《中国写意花鸟画教程》PDF的插图，准确判断其内容。

这些图片可能是以下类型之一：
1. **古代名作/大师作品**：如八大山人（朱耷）、吴昌硕、齐白石等人的真迹或临摹图
2. **技法示意图**：展示某种绘画技法（如笔法步骤、构图示范）
3. **教学插图**：展示鸟/花/虫的画法步骤或局部细节

请仔细观察图片，输出 JSON：
{
    "figure_type": "artwork|technique|teaching_illustration|other",
    "artist": "作者名（如果是技法示意图则留空字符串）",
    "artwork_title": "作品名（如果是技法示意图则留空字符串）",
    "era": "朝代/年代（如'明代'、'清代'、'近现代'）",
    "description": "详细描述这张图实际画了什么（30-100字中文）",
    "confidence": 0.9,
    "is_tutorial_figure": true/false  // 是否是教程类插图（技法示意/教学步骤等）
}

规则：
- 如果图中明显是笔画线条、几何图形、笔法演示 → figure_type="technique"，artist 和 artwork_title 为空
- 如果图中是完整的画作（有完整构图）→ 判断是否为某位名家的作品
- 如果是教学步骤图（如"第一步...第二步..."）→ figure_type="teaching_illustration"
- description 必须准确描述图中实际可见的内容
- 不要猜测不确定的信息"""

USER_PROMPT_TEMPLATE = """请分析这张图片。它来自一本关于中国写意花鸟画的教程书籍。
如果这是技法示意图或教学插图，请如实标注，不要编造艺术家名字。
当前（可能有误的）标签信息供参考：{current_label}"""


def encode_image_to_base64(image_path: str, max_size: int = 1024) -> str:
    """将图片缩放并编码为 base64（JPEG 格式以节省 token）"""
    img = Image.open(image_path)
    # 转为 RGB（处理 RGBA/P/L 等模式）
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    w, h = img.size
    # 缩放长边不超过 max_size
    if max(w, h) > max_size:
        scale = max_size / max(w, h)
        new_w, new_h = int(w * scale), int(h * scale)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def call_qwen_vl(image_b64: str, current_label: str) -> dict:
    """调用 Qwen VL 模型分析单张图片"""
    url = f"{BASE_URL}/chat/completions"

    user_content = USER_PROMPT_TEMPLATE.format(current_label=current_label)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_content},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
            ],
        },
    ]

    try:
        resp = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": messages,
                "temperature": 0.1,  # 低温度保证一致性
                "max_tokens": 1024,
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()

        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        # 解析 JSON
        # Qwen VL 可能会在返回文本前后加 ```json ... ``` 或 markdown 标记
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        text = text.strip()

        result = json.loads(text)
        logger.info(f"LLM 返回: type={result.get('figure_type')} artist={result.get('artist')} title={result.get('artwork_title')}")
        return result
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP 错误: {e.response.status_code} - {e.response.text[:200]}")
        return {"error": f"HTTP_{e.response.status_code}"}
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析失败: {e}, 原文: {str(text)[:300]}")
        return {"error": "json_parse_failed", "raw_text": str(text)[:500]}
    except Exception as e:
        logger.error(f"调用失败: {e}")
        return {"error": str(e)}


def get_current_label(item: dict) -> str:
    """获取当前的标签信息作为参考"""
    artist = item.get("artist", "")
    title = item.get("artwork_title", "")
    desc = item.get("description", "")
    ft = item.get("figure_type", "")
    page = item.get("page", "")
    parts = []
    if ft:
        parts.append(f"type={ft}")
    if artist:
        parts.append(artist)
    if title:
        parts.append(f"《{title}》")
    if desc:
        parts.append(f"desc={desc}")
    if page:
        parts.append(f"page={page}")
    return ", ".join(parts) if parts else "(无标签)"


def needs_audit(item: dict) -> bool:
    """
    判断该条目是否需要审核修正。
    需要审核的条件：
    1. 有 artist 或 artwork_title 但 figure_type=technique（矛盾标签）
    2. 有 artist/artwork_title 但文件名不是中文（"图一等"格式的是正确的作品引用）
    3. 文件存在且可读
    """
    fn = item.get("filename", "")
    artist = item.get("artist", "")
    title = item.get("artwork_title", "")
    ft = item.get("figure_type", "")

    # 文件不存在的不审核
    if fn and not (IMG_BASE_DIR / fn).exists():
        return False

    # technique 类型有 artist/title 的 → 可能错误
    if ft == "technique" and (artist or title):
        return True

    # artwork 类型但文件名不是中文"图X"格式的 → 需要验证
    if ft == "artwork":
        # 中文命名的如"图一一"、"图一二"等通常是正确的作品引用
        if fn.startswith("图"):
            return False  # 这些可能是正确的
        # 有 artist/title 的需要验证
        if artist or title:
            return True

    # unknown 类型有标签的
    if ft == "unknown" and (artist or title):
        return True

    return False


async def main():
    parser = argparse.ArgumentParser(description="重新审核 knowledge_figure 图片元数据")
    parser.add_argument("--apply", action="store_true", help="实际写入修正后的 metadata")
    parser.add_argument("--sync-qdrant", action="store_true", help="同步更新到 Qdrant")
    parser.add_argument("--from", dest="start_from", type=int, default=0, help="从第N张开始")
    args = parser.parse_args()

    # 加载 metadata
    with open(META_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"[INFO] 共 {len(data)} 条 metadata")
    print(f"[INFO] API: {BASE_URL}, Model: {MODEL}")

    # 找出需要审核的条目
    items_to_audit = []
    for key, item in data.items():
        if isinstance(item, dict) and needs_audit(item):
            fn = item.get("filename", "")
            fpath = IMG_BASE_DIR / fn if fn else None
            if fpath and fpath.exists():
                items_to_audit.append((key, item, fpath))

    print(f"\n[INFO] 需要审核的条目: {len(items_to_audit)} 张")

    if not items_to_audit:
        print("[INFO] 没有需要审核的条目")
        return

    if not args.apply:
        print("[DRY-RUN] 使用 --apply 参数来实际执行修改\n")

    results = []  # 存储所有审核结果
    errors = []

    for idx, (key, item, fpath) in enumerate(items_to_audit):
        if idx < args.start_from:
            continue

        fn = item.get("filename", key)
        current_label = get_current_label(item)
        seq_num = idx + 1
        total = len(items_to_audit)

        print(f"\n[{seq_num}/{total}] 审核: {fn}")
        print(f"       当前标签: {current_label}")

        # 编码图片
        try:
            image_b64 = encode_image_to_base64(str(fpath))
            print(f"       图片大小: ~{len(image_b64) // 1024}KB (base64)")
        except Exception as e:
            print(f"       [WARN] image read failed: {e}")
            errors.append({"key": key, "filename": fn, "error": f"img_read_fail: {e}"})
            continue

        # 调用 LLM
        t0 = time.time()
        llm_result = call_qwen_vl(image_b64, current_label)
        elapsed = time.time() - t0

        if "error" in llm_result:
            print(f"       [FAIL] LLM failed ({elapsed:.1f}s): {llm_result['error']}")
            errors.append({"key": key, "filename": fn, "error": llm_result["error"]})
            time.sleep(2)  # 失败后稍等再继续
            continue

        new_ft = llm_result.get("figure_type", item.get("figure_type", ""))
        new_artist = llm_result.get("artist", "") or ""
        new_title = llm_result.get("artwork_title", "") or ""
        new_desc = llm_result.get("description", "")
        new_era = llm_result.get("era", "") or ""
        conf = llm_result.get("confidence", 0)
        is_tutorial = llm_result.get("is_tutorial_figure", False)

        old_artist = item.get("artist", "")
        old_title = item.get("artwork_title", "")

        changed = (
            new_artist != old_artist
            or new_title != old_title
            or new_ft != item.get("figure_type", "")
        )

        status = "[CHANGED]" if changed else "[KEEP]"
        print(f"       [{status}] ({elapsed:.1f}s)")
        print(f"       新: type={new_ft} | artist={new_artist or '(无)'} | title={new_title or '(无)'} | era={new_era}")
        print(f"       描述: {new_desc[:80]}...")
        print(f"       教程图: {is_tutorial} | 置信度: {conf}")

        results.append({
            "key": key,
            "filename": fn,
            "old": {"artist": old_artist, "title": old_title, "type": item.get("figure_type", "")},
            "new": {
                "figure_type": new_ft,
                "artist": new_artist,
                "artwork_title": new_title,
                "era": new_era,
                "description": new_desc,
                "confidence": conf,
                "is_tutorial_figure": is_tutorial,
            },
            "changed": changed,
        })

        if args.apply and changed:
            # 更新内存中的 data
            data[key]["figure_type"] = new_ft
            if new_artist:
                data[key]["artist"] = new_artist
            elif "artist" in data[key]:
                del data[key]["artist"]
            if new_title:
                data[key]["artwork_title"] = new_title
            elif "artwork_title" in data[key]:
                del data[key]["artwork_title"]
            if new_era:
                data[key]["era"] = new_era
            if new_desc:
                data[key]["description"] = new_desc
            # 更新 caption_source
            data[key]["caption_source"] = "qwen-vl-audit-2026-04-10"

        # 限速：避免触发 API 限制
        time.sleep(1.5)

    # -----------------------------------------------------------------------
    # 输出统计
    # -----------------------------------------------------------------------
    changed_count = sum(1 for r in results if r["changed"])
    unchanged_count = sum(1 for r in results if not r["changed"])

    print(f"\n{'='*60}")
    print(f"审核完成!")
    print(f"  总计审核: {len(results)} 张")
    print(f"  需要变更: {changed_count}")
    print(f"  保持不变: {unchanged_count}")
    print(f"  失败: {len(errors)}")

    if errors:
        print(f"\nFailed items:")
        for e in errors:
            print(f"  [WARN] {e.get('filename', e.get('key'))}: {e.get('error')}")

    # -----------------------------------------------------------------------
    # 保存结果
    # -----------------------------------------------------------------------
    if args.apply:
        # 备份原文件
        backup_path = META_PATH.with_suffix(".json.bak")
        import shutil
        shutil.copy2(META_PATH, backup_path)
        print(f"\n[INFO] 已备份原始文件到: {backup_path}")

        # 写入修正后的 metadata
        with open(META_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[INFO] 已更新: {META_PATH}")

        # 同时保存一份 audited 版本（带审核记录）
        audit_record = {
            "audit_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "model": MODEL,
            "total_audited": len(results),
            "changed": changed_count,
            "unchanged": unchanged_count,
            "errors": errors,
            "results": results,
        }
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(audit_record, f, ensure_ascii=False, indent=2)
        print(f"[INFO] 审核记录已保存到: {OUTPUT_PATH}")

    # -----------------------------------------------------------------------
    # 同步 Qdrant
    # -----------------------------------------------------------------------
    if args.apply and args.sync_qdrant:
        print(f"\n[SYNC] 开始同步 Qdrant payload...")
        sync_qdrant(data, results)
        print(f"[SYNC] Qdrant 同步完成")


def sync_qdrant(metadata: dict, audit_results: list):
    """同步修正后的 metadata 到 Qdrant knowledge_images 集合"""
    try:
        from app.modules.pantianshou_composition.qdrant_client import _get_client
        client = _get_client()
        collection = "knowledge_images"

        changed_results = [r for r in audit_results if r["changed"]]
        synced = 0

        for r in changed_results:
            key = r["key"]
            if key not in metadata:
                continue
            item = metadata[key]
            figure_id = item.get("figure_id", "")

            # 构建 Qdrant point ID（通常用 figure_id）
            if not figure_id:
                continue

            # 构建更新的 payload 字段
            payload_update = {}
            if "figure_type" in item:
                payload_update["figure_type"] = item["figure_type"]
            if "artist" in item:
                payload_update["artist"] = item["artist"]
            else:
                payload_update["artist"] = ""  # 清空
            if "artwork_title" in item:
                payload_update["artwork_title"] = item["artwork_title"]
            else:
                payload_update["artwork_title"] = ""
            if "era" in item:
                payload_update["era"] = item["era"]
            if "description" in item:
                payload_update["description"] = item["description"]

            try:
                client.set_payload(
                    collection_name=collection,
                    points=[figure_id],
                    payload=payload_update,
                )
                synced += 1
                print(f"  [OK] synced: {item.get('filename', figure_id)}")
            except Exception as e:
                print(f"  [FAIL] sync failed {figure_id}: {e}")

        print(f"[SYNC] 成功同步 {synced}/{len(changed_results)} 条到 Qdrant")

    except ImportError:
        print("[SYNC] 无法导入 qdrant_client，跳过 Qdrant 同步")
    except Exception as e:
        print(f"[SYNC] Qdrant 同步出错: {e}")


# 日志
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("audit_figures")


if __name__ == "__main__":
    asyncio.run(main())
