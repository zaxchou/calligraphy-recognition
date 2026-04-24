"""
Parse bird_flower_tutorial.txt figure annotations and generate structured metadata JSON.

Figure annotations in the tutorial follow these patterns:
  - "图 N\t朝代\t画家\t《作品名》\t材质\t尺寸\t年代\t收藏"
  - "图 N\t朝代\t画家\t《作品名》（局部）\t材质\t尺寸\t年代\t收藏"
  - "图 N\t技法描述" (for technique illustrations, no artist)

The extracted PNG files in mapping.json use "图N" format (图一, 图二, ..., 图一〇〇)
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# Chinese digit to arabic converter
_ZH_DIGITS = {"〇": 0, "零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
               "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
_ZH_UNITS = {"十": 10, "百": 100, "千": 1000}


def zh_num_to_arabic(s: str) -> int:
    """Convert Chinese number like '一〇〇' to 100."""
    s = s.strip().replace("〇", "零")
    if not s:
        return 0
    # Try direct digits-only
    if all(c in "零一二三四五六七八九" for c in s):
        # Simple additive
        total = 0
        for c in s:
            total += _ZH_DIGITS.get(c, 0)
        return total
    # Handle 十, 百 patterns
    result = 0
    i = 0
    while i < len(s):
        c = s[i]
        if c == "十":
            if i == 0:
                result += 10
            else:
                prev = _ZH_DIGITS.get(s[i-1], 0)
                if prev:
                    result -= prev
                    result += prev * 10
                else:
                    result += 10
        elif c in _ZH_DIGITS:
            if i + 1 < len(s) and s[i+1] not in _ZH_UNITS:
                result += _ZH_DIGITS[c]
            elif i + 1 >= len(s):
                result += _ZH_DIGITS[c]
        i += 1
    return result


def arabic_to_zh(n: int) -> str:
    """Convert arabic number to Chinese figure label (图一, 图一〇〇, etc.)"""
    if n <= 0 or n > 999:
        return f"图{n}"
    digits = []
    for d in str(n):
        digits.append("〇一二三四五六七八九"[int(d)])
    return "图" + "".join(digits)


def _parse_figure_annotation(line: str) -> Optional[Dict[str, Any]]:
    """Parse a single figure annotation line.

    Examples:
      "图 1\t  元代\t  \t赵孟\n\t 《窠木竹石图轴》\n绢本水墨\t 99.4cm×48.2cm\t 台北"故宫博物院"藏"
      "图 2\t 明代\t 林良\t 《双鹰图轴》\t 绢本设色\t 166cm×105cm\t \t 广东省博物馆藏"
      "图 19\t \t近代\t 吴昌硕\t 《墨梅》\t 纸本水墨\t 68cm×132cm\t 1918 年\t 西泠印社藏"
      "图 10\t 章法布局规律"
      "图 1\t \t\t用笔"
      "图 3\t 元代\t 吴镇墨竹"分"字出梢式"
    """
    line = line.strip()
    # Match "图 N" at the start (with possible spaces)
    m = re.match(r"^图\s*(\d+)\s*(.*)", line)
    if not m:
        return None

    fig_num = int(m.group(1))
    rest = m.group(2).strip()

    # Remove leading tabs/spaces
    rest = rest.lstrip("\t ").strip()

    result: Dict[str, Any] = {
        "figure_num": fig_num,
        "figure_id": arabic_to_zh(fig_num),
        "source": "bird_flower_tutorial",
    }

    # Check if it's a technique/non-artwork figure
    # These typically don't have era/artist patterns
    if not rest:
        result["figure_type"] = "technique"
        result["description"] = ""
        return result

    # Try to detect if this has structured metadata (era + artist + artwork)
    # Pattern: 朝代 \t 画家 \t 《作品》 ...
    # Era keywords
    era_pattern = r"(元代|明代|清代|北宋|南宋|近现代?|当代|现代|民国|宋|唐|五代|晋)"
    
    # Check for technique/schematic figures (no era/artist)
    # These are like: "用笔", "章法布局规律", "合掌法与顺掌法", "元代 吴镇墨竹"分"字出梢式"
    has_era = bool(re.search(era_pattern, rest))
    
    # Check for book reference figure (has 《》)
    has_book = bool(re.search(r"《[^》]+》", rest))
    
    if not has_era and not has_book:
        # Likely a technique/schematic figure
        result["figure_type"] = "technique"
        result["description"] = rest
        # Try to parse "元代 吴镇墨竹" pattern for mixed type
        m2 = re.match(r"(元代|明代|清代|北宋|南宋)\s+(.+)", rest)
        if m2:
            result["figure_type"] = "artwork_reference"
            result["era"] = m2.group(1)
            result["description"] = m2.group(2).strip()
        return result

    # Parse structured artwork figure
    result["figure_type"] = "artwork"
    
    # Split by tabs and clean
    parts = [p.strip() for p in re.split(r"[\t]+", rest) if p.strip()]
    
    # Join all parts and parse
    full_text = " ".join(parts)
    
    # Extract era
    era_match = re.search(era_pattern, full_text)
    if era_match:
        result["era"] = era_match.group(1)
        full_text = full_text[:era_match.start()] + full_text[era_match.end():]
    
    # Extract artist name (typically after era, before 《)
    # Artist names: 2-4 Chinese characters
    artist_match = re.search(r"([\u4e00-\u9fff]{2,4})(?:\s*《)", full_text)
    if artist_match:
        result["artist"] = artist_match.group(1).strip()
    
    # Extract artwork title
    title_match = re.search(r"《([^》]+)》", full_text)
    if title_match:
        result["artwork_title"] = title_match.group(1).strip()
    
    # Check for 局部
    if "局部" in full_text:
        result["is_section"] = True
    else:
        result["is_section"] = False
    
    # Extract medium (材质): 纸本水墨, 纸本设色, 绢本设色, etc.
    medium_match = re.search(r"(纸本水墨|纸本设色|绢本设色|绢本水墨|纸本|绢本|水墨|设色)", full_text)
    if medium_match:
        result["medium"] = medium_match.group(1)
    
    # Extract size: pattern like 99.4cm×48.2cm or 243.9cm×60.2cm×4
    size_match = re.search(r"([\d.]+cm[×x][\d.]+cm(?:[×x][\d.]+)?)", full_text)
    if size_match:
        result["size"] = size_match.group(1).replace("×", "×").replace("x", "×")
    
    # Extract year: pattern like "1694 年" or "1927 年" or "年代不详"
    year_match = re.search(r"(\d{4})\s*年", full_text)
    if year_match:
        result["year"] = year_match.group(1)
    elif "年代不详" in full_text:
        result["year"] = "年代不详"
    
    # Extract collection/museum
    museum_patterns = [
        r"([\u4e00-\u9fff]+博物馆藏)",
        r"([\u4e00-\u9fff]+美术馆藏)",
        r"([\u4e00-\u9fff]+印社藏)",
        r"([\u4e00-\u9fff]+艺术馆藏)",
        r'(台北["\u201c\u201d]故宫博物院藏)',
        r"(北京故宫博物院藏)",
        r"(南京博物院藏)",
        r"(天津.*?艺术博物馆藏)",
        r"(旅顺博物馆藏)",
        r"(荣宝斋藏)",
        r"(中央美术学院藏)",
        r"(中国美术馆藏)",
        r"(大阪市立美术馆藏)",
        r"(日本泉屋博古馆藏)",
        r"(私人藏)",
        r"(炎黄艺术馆藏)",
        r"(安徽省博物馆藏)",
        r"(浙江省博物馆藏)",
        r"(上海博物馆藏)",
        r"(西泠印社藏)",
        r"(王方宇旧藏)",
        r"(唐云旧藏)",
        r"(邵洛羊藏)",
        r"(山口.*?藏)",
        r"(广州美术馆藏)",
    ]
    for pat in museum_patterns:
        m = re.search(pat, full_text)
        if m:
            result["collection"] = m.group(1).strip()
            break
    
    return result


def extract_all_figures(text: str) -> Dict[str, Dict[str, Any]]:
    """Extract all figure annotations from bird_flower_tutorial.txt."""
    figures: Dict[str, Dict[str, Any]] = {}
    
    for line in text.splitlines():
        line = line.strip()
        # Figure annotation lines start with "图 " or "图\t"
        if not re.match(r"^图\s*\d+", line):
            continue
        
        parsed = _parse_figure_annotation(line)
        if parsed and parsed.get("figure_id"):
            fig_id = parsed["figure_id"]
            # Don't overwrite if already exists
            if fig_id not in figures:
                figures[fig_id] = parsed
    
    return figures


def load_mapping(mapping_path: str) -> Dict[str, str]:
    """Load mapping.json (filename -> figure_id)."""
    with open(mapping_path, "r", encoding="utf-8") as f:
        return json.load(f) or {}


def extract_page_from_filename(filename: str) -> Optional[int]:
    """Extract page number from filename like '899591682ff741588ba7017d69188ef1_p014_001.png'."""
    m = re.search(r"_p(\d+)_", filename)
    if m:
        return int(m.group(1))
    return None


def build_metadata_with_mapping(
    figures: Dict[str, Dict[str, Any]],
    mapping: Dict[str, str],
    image_dir: str,
) -> Dict[str, Dict[str, Any]]:
    """Merge parsed figure metadata with file mapping."""
    # Build reverse mapping: figure_id -> filename
    fig_to_file: Dict[str, str] = {}
    for fname, fig_id in mapping.items():
        fig_id_norm = fig_id.strip().replace("圖", "图").replace("○", "〇")
        if fig_id_norm not in fig_to_file:
            fig_to_file[fig_id_norm] = fname
    
    output: Dict[str, Dict[str, Any]] = {}
    
    for fig_id, meta in figures.items():
        fname = fig_to_file.get(fig_id)
        entry = dict(meta)
        if fname:
            entry["filename"] = fname
            entry["image_path"] = os.path.join(image_dir, fname) if image_dir else fname
            entry["page"] = extract_page_from_filename(fname)
        output[fig_id] = entry
    
    # Also add entries from mapping that weren't parsed (missing annotations)
    for fig_id, fname in fig_to_file.items():
        if fig_id not in output:
            output[fig_id] = {
                "figure_id": fig_id,
                "source": "bird_flower_tutorial",
                "figure_type": "unknown",
                "filename": fname,
                "image_path": os.path.join(image_dir, fname) if image_dir else fname,
                "page": extract_page_from_filename(fname),
            }
    
    return output


# --- Context analysis: what chapter/section is each figure in? ---

_CHAPTER_RE = re.compile(r"^第[一二三四五六七八九十]+章\s+(.+)")
_SECTION_RE = re.compile(r"^(?:第[一二三四五六七八九十]+节\s+)?(.+?)(?:\s*$)")


def extract_chapter_context(text: str, line_num: int) -> Dict[str, str]:
    """Extract chapter and section context for a given line number."""
    lines = text.splitlines()
    chapter = ""
    section = ""
    for i in range(min(line_num, len(lines))):
        line = lines[i].strip()
        m_ch = _CHAPTER_RE.match(line)
        if m_ch:
            chapter = m_ch.group(1).strip()
        m_sec = _SECTION_RE.match(line)
        if m_sec and not line.startswith("第") and not line.startswith("==="):
            section = m_sec.group(1).strip()
            # Clean section name
            if len(section) > 50:
                section = section[:50]
    return {"chapter": chapter, "section": section}


def enrich_with_context(
    text: str,
    metadata: Dict[str, Dict[str, Any]],
):
    """Add chapter/section context to each figure."""
    lines = text.splitlines()
    line_figures: Dict[int, str] = {}
    
    # Find line numbers of figure annotations
    for i, line in enumerate(lines):
        line = line.strip()
        m = re.match(r"^图\s*(\d+)", line)
        if m:
            fig_num = int(m.group(1))
            fig_id = arabic_to_zh(fig_num)
            line_figures[i] = fig_id
    
    # Extract context for each figure
    chapter = ""
    section = ""
    for i, line in enumerate(lines):
        stripped = line.strip()
        m_ch = _CHAPTER_RE.match(stripped)
        if m_ch:
            chapter = m_ch.group(1).strip()
        
        if i in line_figures:
            fig_id = line_figures[i]
            if fig_id in metadata:
                metadata[fig_id]["chapter"] = chapter
                metadata[fig_id]["section"] = section


# --- Artist aggregation ---

def aggregate_artists(metadata: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Aggregate all figures by artist."""
    artists: Dict[str, Dict[str, Any]] = {}
    
    for fig_id, meta in metadata.items():
        artist = meta.get("artist")
        if not artist:
            continue
        
        if artist not in artists:
            artists[artist] = {
                "name": artist,
                "era": meta.get("era", ""),
                "works": [],
                "figure_ids": [],
                "mediums": set(),
                "collections": set(),
            }
        
        artists[artist]["works"].append(meta.get("artwork_title", ""))
        artists[artist]["figure_ids"].append(fig_id)
        if meta.get("medium"):
            artists[artist]["mediums"].add(meta["medium"])
        if meta.get("collection"):
            artists[artist]["collections"].add(meta["collection"])
    
    # Convert sets to lists for JSON serialization
    for a in artists.values():
        a["mediums"] = sorted(list(a["mediums"]))
        a["collections"] = sorted(list(a["collections"]))
    
    return artists


def main():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    txt_path = os.path.join(repo_root, "bird_flower_tutorial.txt")
    mapping_path = os.path.join(
        repo_root, "backend", "data", "knowledge", "extracted",
        "899591682ff741588ba7017d69188ef1", "mapping.json"
    )
    image_dir = os.path.dirname(mapping_path)
    output_dir = os.path.join(repo_root, "backend", "data", "knowledge")
    os.makedirs(output_dir, exist_ok=True)
    
    text = _read_text(txt_path)
    mapping = load_mapping(mapping_path)
    
    # Step 1: Extract figure annotations
    figures = extract_all_figures(text)
    print(f"Extracted {len(figures)} figure annotations")
    
    # Step 2: Merge with file mapping
    metadata = build_metadata_with_mapping(figures, mapping, image_dir)
    print(f"Built metadata for {len(metadata)} figures")
    
    # Step 3: Enrich with chapter context
    enrich_with_context(text, metadata)
    
    # Step 4: Aggregate by artist
    artists = aggregate_artists(metadata)
    print(f"Found {len(artists)} artists")
    
    # Count figure types
    artwork_count = sum(1 for m in metadata.values() if m.get("figure_type") == "artwork")
    technique_count = sum(1 for m in metadata.values() if m.get("figure_type") == "technique")
    ref_count = sum(1 for m in metadata.values() if m.get("figure_type") == "artwork_reference")
    unknown_count = sum(1 for m in metadata.values() if m.get("figure_type") == "unknown")
    print(f"  Artwork: {artwork_count}, Technique: {technique_count}, Reference: {ref_count}, Unknown: {unknown_count}")
    
    # Save outputs
    fig_meta_path = os.path.join(output_dir, "figure_metadata.json")
    with open(fig_meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"Saved figure metadata to {fig_meta_path}")
    
    artist_path = os.path.join(output_dir, "artist_index.json")
    with open(artist_path, "w", encoding="utf-8") as f:
        json.dump(artists, f, ensure_ascii=False, indent=2)
    print(f"Saved artist index to {artist_path}")
    
    # Print summary
    print("\n=== Artists Summary ===")
    for name, info in sorted(artists.items(), key=lambda x: -len(x[1]["works"])):
        print(f"  {info['era']} {name}: {len(info['works'])} works ({', '.join(info['figure_ids'][:5])}...)")


if __name__ == "__main__":
    main()
