"""
百度百科抓取服务
- 优先通过百度百科开放 API 获取结构化数据
- API 失败时回退到页面爬虫（需要 beautifulsoup4）
"""
import json
import re
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# 尝试导入 BeautifulSoup（可选依赖）
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    logger.info("beautifulsoup4 未安装，页面爬虫 fallback 不可用")

# 百度百科开放 API
BAIDU_BAIKE_API = "https://baike.baidu.com/api/openapi/BaikeLemmaCardApi"
DEFAULT_APPID = "379020"  # 公开测试 appid，限流较低


def _get_appid() -> str:
    """从设置中获取百度 API Key 作为 appid，否则用默认值"""
    try:
        from app.core.config import get_settings
        key = get_settings().BAIDU_API_KEY
        if key:
            return key
    except Exception:
        pass
    return DEFAULT_APPID


def fetch_artist_from_baike(name: str) -> dict:
    """从百度百科获取画家信息，返回结构化字典"""
    result = {"success": False, "data": {}, "source": None, "baidu_url": ""}

    # 1. 优先尝试开放 API
    try:
        data = _fetch_via_api(name)
        if data:
            result["data"] = data
            result["success"] = True
            result["source"] = "api"
            return result
    except Exception as e:
        logger.warning("百度百科API获取失败(%s): %s", name, e)

    # 2. API 失败，回退到页面爬虫
    try:
        data = _fetch_via_scrape(name)
        if data:
            result["data"] = data
            result["success"] = True
            result["source"] = "scrape"
            return result
    except Exception as e:
        logger.warning("百度百科爬虫获取失败(%s): %s", name, e)

    return result


def _fetch_via_api(name: str, appid: Optional[str] = None) -> Optional[dict]:
    """通过百度百科开放 API 获取"""
    appid = appid or _get_appid()
    resp = requests.get(BAIDU_BAIKE_API, params={
        "appid": appid,
        "bk_key": name,
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    if not data or "title" not in data:
        return None

    extracted = {
        "name": data.get("title", name),
        "baidu_url": data.get("url", ""),
        "abstract": data.get("abstract", ""),
        "image": data.get("image", ""),
        "avatar_url": data.get("image", ""),
    }

    # 从 card 中提取结构化字段
    card = data.get("card", [])
    for item in card:
        key = item.get("key", "")
        values = item.get("value", [])
        plain_values = [re.sub(r'<[^>]+>', '', v) for v in values]
        joined = " ".join(plain_values)

        if key.endswith("_nameC") or key.endswith("_origName"):
            extracted["name"] = plain_values[0] if plain_values else name
        elif key.endswith("_alias") or key.endswith("_otherName"):
            alias_text = joined
            if alias_text:
                extracted.setdefault("alias_parts", []).append(alias_text)
        elif key.endswith("_bornDay") or key.endswith("_birth"):
            m = re.search(r'(\d{4})', joined)
            if m:
                extracted["birth_year"] = int(m.group(1))
        elif key.endswith("_dieDay") or key.endswith("_death"):
            m = re.search(r'(\d{4})', joined)
            if m:
                extracted["death_year"] = int(m.group(1))
        elif key.endswith("_bornPlace"):
            extracted["hometown"] = re.sub(r'<[^>]+>', '', plain_values[0]) if plain_values else ""
        elif key.endswith("_dynasty") or key.endswith("_era"):
            extracted["dynasty"] = joined
        elif key.endswith("_masterpiece") or key.endswith("_representative"):
            mps = [re.sub(r'[《》「」]', '', p.strip()) for v in plain_values for p in re.split(r'[、,，]', v) if p.strip()]
            if mps:
                extracted["masterpieces_list"] = mps
        elif key.endswith("_career") or key.endswith("_job"):
            extracted.setdefault("specialties_parts", []).extend(plain_values)
        elif key.endswith("_customDefault"):
            # 可能包含籍贯等信息
            if not extracted.get("hometown") and "宿州" in joined or "湖南" in joined or "浙江" in joined or "江苏" in joined:
                extracted["hometown"] = re.sub(r'<[^>]+>', '', plain_values[0]) if plain_values else ""

    # 解析别名（字号）
    alias_parts = extracted.pop("alias_parts", [])
    if alias_parts:
        alias_text = " ".join(alias_parts)
        # 提取字号：字XXX，号XXX
        alias_parts_clean = []
        for part in alias_text.replace("，", ",").split(","):
            part = part.strip()
            if part and not re.match(r'^\d', part):
                alias_parts_clean.append(part)
        extracted["alias"] = "，".join(alias_parts_clean)

    # 解析代表作（取前6个）
    mps = extracted.pop("masterpieces_list", [])
    if mps:
        extracted["masterpieces"] = json.dumps(mps[:6], ensure_ascii=False)

    # 解析专长
    spec_parts = extracted.pop("specialties_parts", [])
    if spec_parts:
        extracted["specialties"] = "、".join(spec_parts[:5])

    return extracted


def _fetch_via_scrape(name: str) -> Optional[dict]:
    """回退方案：通过百度百科页面抓取"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # 构造百度百科URL
    encoded_name = requests.utils.quote(name)
    urls_to_try = [
        f"https://baike.baidu.com/item/{encoded_name}",
        f"https://baike.baidu.com/item/{encoded_name}/",
    ]

    page_content = None
    final_url = ""
    for url in urls_to_try:
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            page_content = resp.text
            final_url = resp.url
            break
        except Exception:
            continue

    if not page_content:
        return None

    soup = BeautifulSoup(page_content, "html.parser")
    extracted = {
        "name": name,
        "baidu_url": final_url,
    }

    # 提取摘要
    abstract_el = soup.select_one(".lemmaWgt-subLemmaDetailTitle,.basicInfo-item,.para")
    if not abstract_el:
        abstract_el = soup.select_one("meta[name=description]")
    if abstract_el:
        if abstract_el.name == "meta":
            extracted["abstract"] = abstract_el.get("content", "")
        else:
            extracted["abstract"] = abstract_el.get_text(strip=True)[:500]

    # 提取基本信息表中的字段
    basic_info = soup.select(".basicInfo-item")
    for item in basic_info:
        text = item.get_text(strip=True)
        # 尝试匹配键值对
        if "：" in text:
            key, val = text.split("：", 1)
            key = key.strip()
            val = val.strip()
            if "字" == key or "号" == key:
                old = extracted.get("alias", "")
                extracted["alias"] = f"{old} {key}{val}".strip()
            elif "出生" in key:
                m = re.search(r'(\d{4})', val)
                if m:
                    extracted["birth_year"] = int(m.group(1))
            elif "逝世" in key or "去世" in key:
                m = re.search(r'(\d{4})', val)
                if m:
                    extracted["death_year"] = int(m.group(1))
            elif "籍贯" in key or "出生地" in key:
                extracted["hometown"] = val
            elif "朝代" in key or "时代" in key:
                extracted["dynasty"] = val
            elif "代表" in key:
                # 取逗号分隔的前6个
                parts = [p.strip() for p in re.split(r'[,，、]', val) if p.strip()]
                if parts:
                    extracted["masterpieces"] = json.dumps(parts[:6], ensure_ascii=False)
            elif "主要成就" in key:
                extracted["specialties"] = val[:100]

    return extracted


if __name__ == "__main__":
    # 测试
    result = fetch_artist_from_baike("齐白石")
    print(f"Source: {result.get('source')}")
    print(f"Success: {result.get('success')}")
    print(json.dumps(result.get("data", {}), ensure_ascii=False, indent=2))
