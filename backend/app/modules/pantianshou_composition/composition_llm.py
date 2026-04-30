from __future__ import annotations

import base64
import io
import json
import logging
import re
from typing import Any, Dict, List, Optional

import httpx
from PIL import Image

logger = logging.getLogger(__name__)

from app.core.config import get_settings

settings = get_settings()


def _encode_image_to_base64(image_path: str, max_side: int = 1024, quality: int = 80) -> str:
    with Image.open(image_path) as img:
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        width, height = img.size
        longest = max(width, height)
        if longest > max_side:
            scale = max_side / float(longest)
            new_w = max(1, int(width * scale))
            new_h = max(1, int(height * scale))
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        data = buf.getvalue()
        return base64.b64encode(data).decode("utf-8")


def _build_chat_url(base_url: str) -> str:
    base = (base_url or "").rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def _safe_json(obj: Any, max_len: int = 4000) -> str:
    s = json.dumps(obj, ensure_ascii=False)
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def _safe_knowledge(chunks: List[str] | None, max_total: int = 2000) -> str:
    if not chunks:
        return "暂无相关原文"
    lines = []
    total = 0
    for i, c in enumerate(chunks):
        text = (c or "").strip()[:250]
        if not text:
            continue
        line = f"[{i+1}] {text}"
        if total + len(line) > max_total:
            lines.append(f"[{i+1}] ...(已截断，共{len(chunks)}段原文可达)")
            break
        lines.append(line)
        total += len(line)
    return "\n".join(lines) if lines else "暂无相关原文"


def _slim_example_images(images: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Only keep essential fields for example images to save tokens."""
    out = []
    for img in (images or []):
        out.append({
            "title": img.get("title", ""),
            "url": img.get("image_url", img.get("url", "")),
            "caption": img.get("caption", ""),
            "note": img.get("note", ""),
        })
    return out


def _slim_comparisons(comparisons: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Trim comparison objects to essential fields."""
    out = []
    for c in (comparisons or []):
        out.append({
            "dimension": c.get("dimension", ""),
            "current": c.get("current", ""),
            "reference": c.get("reference", ""),
            "diff": c.get("diff", ""),
        })
    return out


def _build_score_table(dimension_scores: Optional[Dict[str, Any]]) -> str:
    if not dimension_scores:
        return "暂无系统评分数据，请根据分析自行给出合理评分。"
    dims = dimension_scores.get("dimensions", [])
    total = dimension_scores.get("total_score", "—")
    if not dims:
        return f"总分: {total}，各维度分数暂缺。"
    lines = [f"总分: {total}分", "各维度得分与分析:"]
    for d in dims:
        name = d.get("name", "—")
        score = d.get("score", 0)
        max_score = d.get("max", 0)
        analysis = (d.get("analysis") or "").strip()
        suggest = (d.get("suggestion") or "").strip()
        line = f"  - {name}: {score}/{max_score}"
        if analysis:
            line += f" | 系统分析: {analysis[:120]}"
        if suggest and suggest != analysis:
            line += f" | 建议: {suggest[:100]}"
        lines.append(line)
    return "\n".join(lines)


def generate_composition_narrative(
    *,
    image_path: str,
    original_url: str,
    metrics: Dict[str, Any],
    checks: List[Dict[str, Any]],
    issues: List[Dict[str, Any]],
    references: List[Dict[str, Any]],
    comparisons: List[Dict[str, Any]],
    theory_basis: List[Dict[str, Any]],
    example_images: List[Dict[str, Any]],
    context_knowledge: List[str] | None = None,
    model: Optional[str] = None,
    dimension_scores: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not (settings.QWEN_ENABLED and settings.QWEN_API_KEY and settings.QWEN_BASE_URL):
        return {"ok": False, "error": "qwen_unavailable"}

    model = (model or settings.COMPOSITION_LLM_MODEL or settings.QWEN_MODEL).strip()
    b64 = _encode_image_to_base64(image_path)
    prompt = f"""你是"潘天寿教你构图"的专业讲评助手。你必须基于提供的客观数据（指标、案例相似检索、对比差异、以及 pan.md + panplus.md 规则条目）生成讲评，避免凭空猜测。

重要原则：
- 你面对的可能是经典名作或成熟的习作，评语应先肯定优点，再探讨可精进之处
- 不要上来就批评。先分析作品的构图特点和成功之处，再给出建议
- 建议用"可进一步""不妨尝试""若想更上一层楼"等委婉措辞，避免"应该""必须""错误"等否定性词语
- 如果数据指标显示构图关系成立（留白合理、有主方向、疏密有一定对比），应给予正面评价

【构图类型识别——分析前先判断】
在概述部分，请先识别这幅画属于以下哪种经典构图范式，并在概述中点明：
- 之字形构图（S形/蛇形蜿蜒，多见于兰竹、藤蔓）
- 对角线构图（从一角斜向对角，多见于花卉折枝、鸟禽配石）
- 三段式构图（上中下或远中近三层，多见于荷塘、水岸）
- 边角构图（偏居一角或一边，大面积留白，八大、潘天寿典型）
- 中心辐射构图（主体居中向四周展开，多见于荷、梅）
- 纵横构图（经纬交织，杆石与题款形成十字或井字骨架，吴昌硕典型）
- 全景构图（画材遍布四方，密不透风但有序，金农典型）
如果画面不属于以上任何范式，说明其独特的构图特征即可。识别构图范式后，后续7维度分析应围绕该范式的特点展开。

【审美判断框架——分析每个维度时请遵循】
1. 先判断该维度在当前画面中的"状态"（优/良/可改善），给出具体视觉证据
2. 再分析该维度与整体构图的关系（是加分还是制约）
3. 如有改善空间，引用规则说明方向，但用老师口吻而非术语罗列
4. 避免空泛套话——每句评价都必须对应画面中可见的具体元素或空间关系

评分维度说明（7维度100分制）：
1. 开合之势（20分）— 起结趋势、方向变化、穿插破势
2. 虚实相生（18分）— 留白比例、密处透气、虚实过渡
3. 疏密有致（18分）— 疏密节奏、元素间距、密处留气
4. 辅助元素（14分）— 题款印章位置与大小、三角形布局
5. 均衡节奏（12分）— 杆秤式平衡、大小相间、蓄势借力、对角呼应
6. 穿插结构（10分）— 女字交叉、直起横破、斜势走向、线条交织
7. 边角空间（8分）— 金边银角、四角不等量、大空白与小空白、款印分割空间

【系统计算得分（必须严格使用这些分数输出综合评分表，不得修改）】
{_build_score_table(dimension_scores)}

图像URL：{original_url}

【客观指标 metrics】{_safe_json(metrics)}
【环节打分 checks】{_safe_json(checks)}
【关键问题 issues】{_safe_json(issues)}
【相似案例 references】{_safe_json(references)}
【对比差异 comparisons】{_safe_json(_slim_comparisons(comparisons))}
【原文依据 theory_basis（来自 pan.md + panplus.md 规则表）】{_safe_json(theory_basis)}
【可用示例图片（用于插入正文）example_images】{_safe_json(_slim_example_images(example_images))}

【知识库原文 context_knowledge（来自潘天寿《关于构图问题》+《中国写意花鸟画教程》中与当前作品最相关的原文节选，请在分析中参考引述这些原文观点与案例，让讲评更有权威依据）】
{_safe_knowledge(context_knowledge)}

输出要求：
1) 必须输出 Markdown，结构参考：
   - ## 一、作品概述与优点（先判断构图范式，再从整体上肯定作品的构图特色和亮点）
   - ## 二、分项分析（每个维度单独一行标题，如"1. **开合之势**"，然后换行写分析段落；共7个维度：开合之势、虚实相生、疏密有致、辅助元素、均衡节奏、穿插结构、边角空间。每个维度按"审美判断框架"三步走：状态判断→与整体关系→改善方向）
   - ## 综合评分表（必须严格使用上方"系统计算得分"中的分数，用 Markdown 表格输出7个维度 + 总分行，不得修改任何数值）
   - ## 精进建议（如需提升，可参考潘天寿及历代名家的经验，编号列表，3-5条即可。每条建议需说明与当前构图范式的关联）
   - ## 结语（总结性正面评价，呼应开头构图范式判断）
2) 不要输出任何内部编号与算法术语：不得输出 rule_id、图号编号（如 KH-01-03、JH-01-01）、不得输出 blank_ratio/角度差等原始数值。
3) 每条建议必须说明"依据"：用老师口吻引用原文要点（来自 theory_basis 的 rule_name/condition/quantitative_standard，但不要带编号），并说明该条与当前作品如何对应。
4) 对比分析部分必须引用至少 2 条 comparisons（如果存在），并解释"当前 vs 参考"差异意味着什么。
5) 关键点用标记，避免空泛套话；只根据输入数据与图像内容推断，不得编造引用与案例。
6) 【图片插入规则——严格遵守】
   a) 每张示例图片必须插入到正文中与其内容最相关的段落之后，不得在文末单独设立"示例图讲解"等集中展示章节。
   b) 插入格式：在相关段落末尾空一行，写入 `![图片title](image_url)`，然后在图片下方用一句引用说明该图与当前分析的关联（如"下图展示了…"）。
   c) example_images 中的 title/note/caption 字段说明了该图对应的构图规则，请据此判断图片应放在哪个维度或建议段落。
   d) 只能使用 example_images 中提供的 image_url，不得编造路径。如无合适图片可跳过。
7) 新增维度（均衡节奏/穿插结构/边角空间）的建议可适当引用刘海勇《中国写意花鸟画教程》中的概念，如"杆秤式平衡""女字交叉""金边银角""大实空白"等。
8) 【重要】必须完整输出所有内容直至"结语"部分。不要因为篇幅限制而中途截断。如果空间不够，适当精简每段的论述，但确保7个维度分析和精进建议全部输出。"""

    payload: Dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            }
        ],
        "stream": False,
        "max_tokens": int(getattr(settings, "COMPOSITION_LLM_MAX_TOKENS", 8192)),
        "temperature": 0.5,
    }

    url = _build_chat_url(settings.QWEN_BASE_URL)
    headers = {"Authorization": f"Bearer {settings.QWEN_API_KEY}", "Content-Type": "application/json"}

    try:
        with httpx.Client(timeout=httpx.Timeout(120.0, connect=10.0, read=110.0, write=30.0)) as client:
            r = client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            choice = data["choices"][0]
            content = choice["message"]["content"]
            finish_reason = choice.get("finish_reason", "")
            text = (content or "").strip()
            if text.startswith("```"):
                text = text.lstrip("`").strip()
            text = _postprocess_text(text, example_images, dimension_scores=dimension_scores)
            if finish_reason == "length":
                text += "\n\n> ⚠️ *（内容因长度限制被截断，部分分析未完整输出）*"
            return {"ok": True, "model": model, "text": text, "finish_reason": finish_reason}
    except Exception as e:
        fallback = (settings.QWEN_MODEL or "").strip()
        if fallback and fallback != model:
            payload["model"] = fallback
            try:
                with httpx.Client(timeout=httpx.Timeout(120.0, connect=10.0, read=110.0, write=30.0)) as client:
                    r = client.post(url, headers=headers, json=payload)
                    r.raise_for_status()
                    data = r.json()
                    choice = data["choices"][0]
                    content = choice["message"]["content"]
                    finish_reason = choice.get("finish_reason", "")
                    text = (content or "").strip()
                    if text.startswith("```"):
                        text = text.lstrip("`").strip()
                    text = _postprocess_text(text, example_images, dimension_scores=dimension_scores)
                    if finish_reason == "length":
                        text += "\n\n> ⚠️ *（内容因长度限制被截断，部分分析未完整输出）*"
                    return {"ok": True, "model": fallback, "text": text, "finish_reason": finish_reason}
            except Exception:
                pass
        return {"ok": False, "error": str(e), "model": model}


_FORBIDDEN_RE = re.compile(
    r"(KH-\d{2}-\d{2,3})|(JH-\d{2}-\d{2})|(CC-\d{2}-\d{2})|(BJ-\d{2}-\d{2})|(XS-\d{2}-\d{2})|(SM-\d{2}-\d{2})|(QS-\d{2}-\d{2})|(FZ-\d{2}-\d{2})"
    r"|(rule_id)|(blank_ratio)|(too_void)|(too_dense)|(flat_rhythm)|(parallel)|(严重度\s*[:：]?\s*\d+)",
    re.IGNORECASE,
)


def _postprocess_text(text: str, example_images: List[Dict[str, Any]], dimension_scores: Optional[Dict[str, Any]] = None) -> str:
    t = (text or "").strip()
    t = _FORBIDDEN_RE.sub("", t)

    # --- Build whitelist of valid image URLs from example_images ---
    valid_urls = set()
    for img in (example_images or []):
        url = (img.get("image_url") or img.get("url") or "").strip()
        if url:
            valid_urls.add(url)

    # --- Remove images whose URLs are NOT in the whitelist (LLM hallucination) ---
    def _filter_image(m):
        url = m.group(2)
        if url in valid_urls:
            return m.group(0)
        logger.debug("Filtered hallucinated image URL: %s", url)
        return ""
    t = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', _filter_image, t)

    # --- Normalize HTML tags back to Markdown ---
    # Backend must output pure Markdown; rendering is the frontend/PDF's job.
    # LLM may occasionally output HTML tags (e.g. <strong>, <em>, <bold>);
    # convert them back to Markdown so downstream renderers handle them uniformly.
    t = re.sub(r'<strong>([\s\S]*?)</strong>', r'**\1**', t)
    t = re.sub(r'<em>([\s\S]*?)</em>', r'*\1*', t)
    t = re.sub(r'<bold>([\s\S]*?)</bold>', r'**\1**', t)
    t = re.sub(r'<b>([\s\S]*?)</b>', r'**\1**', t)
    t = re.sub(r'<i>([\s\S]*?)</i>', r'*\1*', t)

    # --- Deduplicate images: keep only first occurrence of each URL ---
    _seen_urls = set()
    def _dedup_image(m):
        url = m.group(2)
        if url in _seen_urls:
            return ""
        _seen_urls.add(url)
        return m.group(0)
    t = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', _dedup_image, t)

    # --- Force-replace total score in 综合评分表 to match system score ---
    if dimension_scores and dimension_scores.get("total_score") is not None:
        target_total = int(dimension_scores["total_score"])
        # Match: | 总分 | XX | 100 |
        t = re.sub(
            r'\|\s*总分\s*\|\s*\d+\s*\|\s*100\s*\|',
            f'| 总分 | {target_total} | 100 |',
            t,
        )
        # Match: | 总分 | XX/100 |
        t = re.sub(
            r'\|\s*总分\s*\|\s*\d+\s*/\s*100\s*\|',
            f'| 总分 | {target_total}/100 |',
            t,
        )
        # Match standalone text like "总评 90/100" or "总评90分"
        t = re.sub(
            r'(总评\s*)\d+\s*/\s*100',
            rf'\g<1>{target_total}/100',
            t,
        )
        t = re.sub(
            r'(总评\s*)\d+\s*分',
            rf'\g<1>{target_total}分',
            t,
        )
        # Match: **总分**: XX or 总分：XX
        t = re.sub(
            r'(\*\*)?总分\s*[：:]\s*\d+(\*\*)?',
            lambda m: f'{m.group(1) or ""}总分：{target_total}{m.group(2) or ""}',
            t,
        )
        # Match: 总分\s*XX分
        t = re.sub(
            r'总分\s*\d+\s*分',
            f'总分 {target_total}分',
            t,
        )
        # Also fix dimension scores in table rows
        dims = dimension_scores.get("dimensions", [])
        if dims:
            correct_scores = {}
            for d in dims:
                name = d.get("name", "").strip()
                score = d.get("score", 0)
                correct_scores[name] = int(score)
            for name, score in correct_scores.items():
                escaped = re.escape(name)
                t = re.sub(
                    rf'\|\s*{escaped}\s*\|\s*\d+\s*\|\s*\d+\s*\|',
                    f'| {name} | {score} | {next((d["max"] for d in dims if d.get("name") == name), 20)} |',
                    t,
                )
    # --- Smart image insertion: distribute images into relevant dimension sections ---
    if example_images:
        t = _distribute_images_into_sections(t, example_images)
    return t.strip()


def _distribute_images_into_sections(text: str, example_images: List[Dict[str, Any]]) -> str:
    """将示例图片智能插入到对应的维度分析段落中。
    
    根据图片的 title/note 中提到的维度关键词，将图片插入到对应维度段落的末尾。
    如果找不到对应维度，则插入到"精进建议"之前。
    """
    t = text
    
    # 维度关键词映射
    DIMENSION_KEYWORDS = {
        "开合之势": ["开合", "起承转合", "起结", "开合之势"],
        "虚实相生": ["虚实", "留白", "虚实相生"],
        "疏密有致": ["疏密", "疏密有致", "节奏"],
        "辅助元素": ["辅助", "题款", "印章", "题跋", "辅助元素"],
        "均衡节奏": ["均衡", "节奏", "均衡节奏", "杆秤", "大小相间"],
        "穿插结构": ["穿插", "结构", "穿插结构", "女字", "交叉"],
        "边角空间": ["边角", "边角空间", "金边银角", "占边", "占角"],
    }
    
    _seen_urls = set()
    
    for it in example_images[:6]:  # 最多处理6张图
        url = (it.get("image_url") or it.get("url") or "").strip()
        if not url or url in _seen_urls:
            continue
        _seen_urls.add(url)
        
        title = (it.get("title") or "示例图").strip()
        note = (it.get("note") or "").strip()
        caption = (it.get("caption") or "").strip()
        
        # 组合所有文本用于匹配维度
        combined_text = f"{title} {note} {caption}".lower()
        
        # 确定这张图片属于哪个维度
        target_dim = None
        for dim_name, keywords in DIMENSION_KEYWORDS.items():
            if any(kw in combined_text for kw in keywords):
                target_dim = dim_name
                break
        
        # 构建图片 markdown
        img_md = f"\n\n![{title}]({url})"
        if note or caption:
            img_md += f"\n> *{note or caption}*"
        img_md += "\n"
        
        # 尝试插入到对应维度段落末尾
        inserted = False
        if target_dim:
            # 查找维度段落：匹配 "1. **开合之势**" 或 "## 开合之势" 或 "**开合之势**"
            patterns = [
                rf'(\d+\.\s*\*\*{re.escape(target_dim)}\*\*.*?)(?=\n\n\d+\.\s*\*\*|\n\n##|\n\n【精进建议】|\n\n## 精进建议|$)',
                rf'(##\s*{re.escape(target_dim)}.*?)(?=\n\n##|\n\n【精进建议】|\n\n## 精进建议|$)',
                rf'(\*\*{re.escape(target_dim)}\*\*.*?)(?=\n\n\d+\.\s*\*\*|\n\n##|\n\n【精进建议】|\n\n## 精进建议|$)',
            ]
            for pattern in patterns:
                match = re.search(pattern, t, re.DOTALL)
                if match:
                    # 在段落末尾插入图片
                    end_pos = match.end()
                    t = t[:end_pos] + img_md + t[end_pos:]
                    inserted = True
                    break
        
        # 如果找不到对应维度，插入到"精进建议"之前
        if not inserted:
            # 查找精进建议部分
            suggest_patterns = [
                r'(\n\n【精进建议】)',
                r'(\n\n## 精进建议)',
                r'(\n\n## 三、精进建议)',
            ]
            for pattern in suggest_patterns:
                match = re.search(pattern, t)
                if match:
                    t = t[:match.start()] + img_md + t[match.start():]
                    inserted = True
                    break
            
            # 如果还是找不到，插入到结尾（但不在"示例图讲解"章节）
            if not inserted:
                # 移除已有的"示例图讲解"章节
                t = re.sub(r'\n\n## 示例图讲解\n\n.*?(?=\n\n##|$)', '', t, flags=re.DOTALL)
                t = t.rstrip() + img_md
    
    return t
