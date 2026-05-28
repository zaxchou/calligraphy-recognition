"""
画家规则管理 API
- CRUD（规则增删改查）
- AI 规则发现（为新画家生成规则包）
"""
import json
import re
from datetime import datetime
from typing import Optional, Dict, List

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.core.database import get_db_connection
from app.core.auth import require_admin_role


def _clear_artist_rules_cache(artist_name: str):
    """清除画家规则内存缓存，使新规则立即生效"""
    try:
        from app.services.inscription_content_analyzer import _cache_artist_rules
        _cache_artist_rules.pop(artist_name, None)
    except ImportError:
        pass


router = APIRouter(prefix="/artist-rules", tags=["artist-rules"])


# ============ 数据模型 ============

class ArtistRuleCreate(BaseModel):
    artist_name: str
    emotion_baseline: float = 0.0
    life_stages: Optional[List[Dict]] = None
    sentiment_note: Optional[str] = ""
    theme_note: Optional[str] = ""
    theme_exceptions: Optional[Dict] = None
    expected_theme_distribution: Optional[Dict] = None
    expected_sentiment_distribution: Optional[Dict] = None
    rules_version: str = "5.4"


class ArtistRuleUpdate(BaseModel):
    artist_name: Optional[str] = None
    emotion_baseline: Optional[float] = None
    life_stages: Optional[List[Dict]] = None
    sentiment_note: Optional[str] = None
    theme_note: Optional[str] = None
    theme_exceptions: Optional[Dict] = None
    expected_theme_distribution: Optional[Dict] = None
    expected_sentiment_distribution: Optional[Dict] = None
    rules_version: Optional[str] = None


def _row_to_dict(row) -> Dict:
    """将数据库行转为字典，解析 JSON 字段"""
    d = dict(row)
    for field in ["life_stages", "theme_exceptions", "expected_theme_distribution",
                   "expected_sentiment_distribution"]:
        if d.get(field) and isinstance(d[field], str):
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return d


# ============ API 端点 ============

@router.get("")
async def list_artist_rules():
    """列出所有画家规则"""
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM artist_rules ORDER BY id").fetchall()
        rules = [_row_to_dict(row) for row in rows]
        return {"success": True, "rules": rules}
    finally:
        conn.close()


@router.get("/{rule_id}")
async def get_artist_rule(rule_id: int):
    """获取单条画家规则"""
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM artist_rules WHERE id = ?", (rule_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="规则不存在")
        return {"success": True, "rule": _row_to_dict(row)}
    finally:
        conn.close()


@router.get("/by-name/{artist_name}")
async def get_artist_rule_by_name(artist_name: str):
    """按画家名称获取规则"""
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT * FROM artist_rules WHERE artist_name = ?", (artist_name,)
        ).fetchone()
        if not row:
            return {"success": True, "rule": None}
        return {"success": True, "rule": _row_to_dict(row)}
    finally:
        conn.close()


@router.post("")
async def create_artist_rule(rule: ArtistRuleCreate):
    """创建画家规则"""
    conn = get_db_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM artist_rules WHERE artist_name = ?", (rule.artist_name,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail=f"画家 {rule.artist_name} 的规则已存在")

        now = datetime.now().isoformat()
        conn.execute(
            """INSERT INTO artist_rules (
                artist_name, emotion_baseline, life_stages, sentiment_note,
                theme_note, theme_exceptions, expected_theme_distribution,
                expected_sentiment_distribution, rules_version, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rule.artist_name,
                rule.emotion_baseline,
                json.dumps(rule.life_stages or [], ensure_ascii=False),
                rule.sentiment_note or "",
                rule.theme_note or "",
                json.dumps(rule.theme_exceptions or {}, ensure_ascii=False),
                json.dumps(rule.expected_theme_distribution or {}, ensure_ascii=False),
                json.dumps(rule.expected_sentiment_distribution or {}, ensure_ascii=False),
                rule.rules_version,
                now, now
            )
        )
        conn.commit()
        _clear_artist_rules_cache(rule.artist_name)
        return {"success": True, "message": f"画家 {rule.artist_name} 规则创建成功"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.put("/{rule_id}")
async def update_artist_rule(rule_id: int, rule: ArtistRuleUpdate):
    """更新画家规则"""
    conn = get_db_connection()
    try:
        existing = conn.execute(
            "SELECT * FROM artist_rules WHERE id = ?", (rule_id,)
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="规则不存在")

        updates = {}
        for field in ["artist_name", "emotion_baseline", "sentiment_note", "theme_note",
                       "rules_version"]:
            val = getattr(rule, field, None)
            if val is not None:
                updates[field] = val

        for field in ["life_stages", "theme_exceptions", "expected_theme_distribution",
                       "expected_sentiment_distribution"]:
            val = getattr(rule, field, None)
            if val is not None:
                updates[field] = json.dumps(val, ensure_ascii=False)

        if updates:
            updates["updated_at"] = datetime.now().isoformat()
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE artist_rules SET {set_clause} WHERE id = ?",
                (*updates.values(), rule_id)
            )
            conn.commit()

        _clear_artist_rules_cache(existing.get("artist_name", ""))
        return {"success": True, "message": "规则更新成功"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.delete("/{rule_id}")
async def delete_artist_rule(rule_id: int, admin=Depends(require_admin_role)):
    """删除画家规则"""
    conn = get_db_connection()
    try:
        existing = conn.execute(
            "SELECT id, artist_name FROM artist_rules WHERE id = ?", (rule_id,)
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="规则不存在")

        _clear_artist_rules_cache(existing["artist_name"])
        conn.execute("DELETE FROM artist_rules WHERE id = ?", (rule_id,))
        conn.commit()
        return {"success": True, "message": "规则已删除"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/ai-discover/{artist_name}")
async def ai_discover_rules(artist_name: str):
    """
    AI 规则发现：为新画家分析样本书法，生成初始规则包。
    从 tubi_analyses 中取该画家的已校对题跋作为样本，调用 LLM 生成规则。
    """
    conn = get_db_connection()
    try:
        # 获取画家的元数据（出生年份等）
        artist_meta = conn.execute(
            "SELECT birth_year, background FROM artists WHERE name = ?",
            (artist_name,)
        ).fetchone()
        birth_year_hint = ""
        if artist_meta and artist_meta["birth_year"]:
            birth_year_hint = f"\n该画家的已知出生年份：{artist_meta['birth_year']}年。请以此为基础推算其生命周期。"

        samples = conn.execute("""
            SELECT inscription_content FROM tubi_analyses
            WHERE artist LIKE ? AND inscription_verified = 1
            AND inscription_content IS NOT NULL AND LENGTH(inscription_content) > 5
            LIMIT 30
        """, (f"%{artist_name}%",)).fetchall()

        if not samples:
            return {
                "success": False,
                "message": f"画家 {artist_name} 没有已校对的题跋样本，请先校对后再试"
            }

        sample_texts = [row["inscription_content"][:300] for row in samples]
        combined_samples = "\n---\n".join(sample_texts[:15])

        from app.services.qwen_llm_client import call_qwen_chat
        from app.services.tibi_analysis_rules import THEMES

        theme_names = "\n".join(
            f"  {k}: {v['name']} - {v['description']}" for k, v in THEMES.items()
        )

        prompt = f"""你是中国古代书画题跋研究专家。请分析以下画家 {artist_name} 的 {len(sample_texts)} 条题跋样本，为其生成分析规则包。

【六大主题定义】
{theme_names}

【题跋样本】
{combined_samples}

【要求】返回严格JSON格式（不要markdown包裹）：
{{
  "emotion_baseline": 该画家情感基线（-1.0~1.0之间的浮点数，负值偏消极），
  "sentiment_note": "该画家题跋情感特点（50字以内，用于LLM prompt注入）",
  "theme_note": "该画家主题倾向说明（50字以内，用于LLM prompt注入）",
  "theme_exceptions": {{}},
  "life_stages": [
    {{"name": "早期", "year_start": 1980, "year_end": 2000, "weight": 1.0, "mood_offset": 0.0}},
    {{"name": "中期", "year_start": 2000, "year_end": 2010, "weight": 1.5, "mood_offset": -0.2}},
    {{"name": "晚期", "year_start": 2010, "year_end": 2025, "weight": 2.0, "mood_offset": -0.4}}
  ],
  "expected_theme_distribution": {{"身世自况": [5,15], "咏物寄兴": [50,70], "画理自叙": [5,12], "时事讽喻": [5,15], "吉语祥瑞": [3,10], "交游赠答": [8,18]}},
  "expected_sentiment_distribution": {{"negative_min": 20, "positive_max": 35, "emotion_mean_max": -0.3}}
}}

只返回JSON，不要其他文字。life_stages 请根据该画家的实际生平填写年份。{birth_year_hint}"""

        response = call_qwen_chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1500,
        )

        if "error" in response:
            return {"success": False, "message": f"AI调用失败: {response['error']}"}

        result = response.get("choices", [{}])[0].get("message", {}).get("content", "")

        json_match = re.search(r'\{[\s\S]*\}', result)
        if not json_match:
            return {"success": False, "message": "LLM 返回无法解析", "raw": result[:500]}

        info = json.loads(json_match.group())

        now = datetime.now().isoformat()
        conn.execute(
            """INSERT INTO artist_rules (
                artist_name, emotion_baseline, life_stages, sentiment_note,
                theme_note, theme_exceptions, expected_theme_distribution,
                expected_sentiment_distribution, rules_version, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                artist_name,
                float(info.get("emotion_baseline", 0.0)),
                json.dumps(info.get("life_stages", []), ensure_ascii=False),
                info.get("sentiment_note", ""),
                info.get("theme_note", ""),
                json.dumps(info.get("theme_exceptions", {}), ensure_ascii=False),
                json.dumps(info.get("expected_theme_distribution", {}), ensure_ascii=False),
                json.dumps(info.get("expected_sentiment_distribution", {}), ensure_ascii=False),
                "5.4-ai",
                now, now
            )
        )
        conn.commit()

        return {
            "success": True,
            "message": f"AI 规则发现完成，已为 {artist_name} 创建规则包",
            "rule": {
                "artist_name": artist_name,
                "emotion_baseline": info.get("emotion_baseline"),
                "sentiment_note": info.get("sentiment_note"),
                "theme_note": info.get("theme_note"),
            }
        }

    except HTTPException:
        raise
    except ImportError:
        return {"success": False, "message": "AI服务不可用，请检查 QWEN_API_KEY 配置"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/generate-life-stages/{artist_name}")
async def generate_life_stages(artist_name: str):
    """
    从百科数据自动生成生命阶段规则。
    读取 artists 表的 birth_year + death_year + bio_events，
    均分为早/中/晚三期。
    """
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT birth_year, death_year, bio_events FROM artists WHERE name = ?",
            (artist_name,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"画家「{artist_name}」不在百科中")

        birth = row["birth_year"]
        death = row["death_year"]
        bio_events = []
        if row["bio_events"]:
            try:
                bio_events = json.loads(row["bio_events"])
            except (json.JSONDecodeError, TypeError):
                pass

        if not birth:
            raise HTTPException(status_code=400, detail=f"画家「{artist_name}」缺少出生年份，无法生成时期")

        lifespan = (death - birth) if death else (2026 - birth)

        # 三段均分
        p1_end = birth + lifespan // 3
        p2_end = birth + lifespan * 2 // 3
        p3_end = death or 2026

        # 尝试从 bio_events 找关键节点来切分
        if bio_events:
            years = sorted([e.get("year") for e in bio_events if isinstance(e.get("year"), int)])
            if len(years) >= 3:
                mid1, mid2 = years[len(years) // 3], years[len(years) * 2 // 3]
                if mid1 > birth and mid2 > mid1:
                    p1_end, p2_end = mid1, mid2

        stages = [
            {"name": "早期", "year_start": birth, "year_end": p1_end,
             "weight": 1.0, "mood_offset": 0.0, "description": f"{birth}-{p1_end}"},
            {"name": "中期", "year_start": p1_end + 1, "year_end": p2_end,
             "weight": 1.5, "mood_offset": -0.2, "description": f"{p1_end+1}-{p2_end}"},
            {"name": "晚期", "year_start": p2_end + 1, "year_end": p3_end,
             "weight": 2.0, "mood_offset": -0.4, "description": f"{p2_end+1}-{p3_end}"},
        ]

        # 用 bio_events 填充描述
        if bio_events:
            for evt in bio_events:
                yr, desc = evt.get("year"), evt.get("event", "")
                if yr and desc:
                    for s in stages:
                        if s["year_start"] <= yr <= s["year_end"]:
                            s["description"] = desc[:30]

        return {"success": True, "stages": stages}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
