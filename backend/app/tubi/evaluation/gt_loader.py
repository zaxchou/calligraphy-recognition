"""
Ground Truth 加载器

从SQLite数据库只读加载手动标注的regions数据
"""

import json
import sqlite3
import os
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class GroundTruthRecord:
    """单张图的Ground Truth记录"""
    id: int                    # DB自增id
    image_id: str              # UUID
    filepath: str              # 原始图路径
    title: str                 # 作品名
    width: int                 # 图像宽度
    height: int                # 图像高度
    regions: Dict              # {"inscription_regions": [...], "painting_regions": [...], "blank_regions": [...]}
    group: Optional[str]       # CV画群分类（如果有）


DB_PATH = os.path.join(
    os.path.dirname(__file__),  # app/tubi/evaluation/
    "..", "..", "..",           # app/
    "data", "calligraphy.db"
)


def _parse_regions(raw: str) -> Optional[Dict]:
    """
    解析数据库中的regions字段
    
    数据库中存储的可能是：
    1. 纯JSON字符串: '{"inscription_regions": [...]}'
    2. 双重编码的JSON字符串: '"{\\"inscription_regions\\": [...]}"'
    """
    if not raw:
        return None
    
    raw = raw.strip()
    
    # 尝试直接解析（情况1：纯JSON）
    try:
        result = json.loads(raw)
        if isinstance(result, dict):
            return result
        # 如果解析出来是str（情况2：双重编码），继续解析
        if isinstance(result, str):
            return json.loads(result)
    except json.JSONDecodeError:
        pass
    
    # 尝试去掉外层引号后解析
    if raw.startswith('"') and raw.endswith('"'):
        try:
            unquoted = json.loads(raw)
            if isinstance(unquoted, str):
                return json.loads(unquoted)
            return unquoted
        except (json.JSONDecodeError, TypeError):
            pass
    
    # 尝试修复转义问题
    try:
        fixed = raw.replace('\\"', '"').replace('\\\\', '\\')
        if fixed.startswith('"') and fixed.endswith('"'):
            fixed = fixed[1:-1]
        result = json.loads(fixed)
        if isinstance(result, str):
            return json.loads(result)
        return result
    except json.JSONDecodeError:
        pass
    
    print(f"WARNING: Failed to parse regions JSON. First 200 chars: {raw[:200]}")
    return None


def load_ground_truth(
    db_path: Optional[str] = None,
    artist: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[GroundTruthRecord]:
    """
    加载所有手动标注的Ground Truth记录
    
    参数:
        db_path: 数据库路径，默认自动推导
        artist: 过滤指定作者（如"李鱓"），None=全部
        limit: 限制返回数量，None=全部
    
    返回:
        List[GroundTruthRecord]: Ground Truth记录列表
    """
    if db_path is None:
        db_path = DB_PATH
    
    # 使用绝对路径并标准化
    db_path = os.path.abspath(os.path.normpath(db_path))
    
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")
    
    records = []
    
    # 只读模式打开数据库
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    cur = conn.cursor()
    
    query = """
        SELECT id, image_id, filepath, title, image_width, image_height, regions
        FROM tubi_analyses
        WHERE is_manual_annotated = 1
    """
    params = []
    
    if artist:
        query += " AND artist = ?"
        params.append(artist)
    
    query += " ORDER BY id"
    
    if limit:
        query += " LIMIT ?"
        params.append(limit)
    
    cur.execute(query, params)
    
    for row in cur.fetchall():
        db_id, image_id, filepath, title, width, height, regions_raw = row
        group = None  # cv_first_group列可能不存在
        
        regions = _parse_regions(regions_raw) if regions_raw else None
        if regions is None:
            print(f"WARNING: Skipping {image_id} - cannot parse regions")
            continue
        
        # 确保filepath是绝对路径
        if not os.path.isabs(filepath):
            # filepath是相对backend目录的（如 data/uploads/xxx.jpg）
            # db_path在 backend/data/calligraphy.db，所以base是db_path的父目录的父目录
            base_dir = os.path.dirname(os.path.dirname(db_path))
            filepath = os.path.join(base_dir, filepath)
        
        records.append(GroundTruthRecord(
            id=db_id,
            image_id=image_id,
            filepath=filepath,
            title=title or "",
            width=width or 0,
            height=height or 0,
            regions=regions,
            group=group,
        ))
    
    conn.close()
    return records


def get_image_dimensions(image_path: str) -> Optional[tuple]:
    """获取图像实际尺寸（如果数据库中的尺寸不可靠）"""
    try:
        import cv2
        img = cv2.imread(image_path)
        if img is not None:
            h, w = img.shape[:2]
            return (w, h)
    except Exception as e:
        print(f"WARNING: Cannot read image {image_path}: {e}")
    return None


def validate_ground_truth(records: List[GroundTruthRecord]) -> Dict:
    """
    验证Ground Truth数据质量
    
    返回统计信息
    """
    stats = {
        "total": len(records),
        "has_inscription": 0,
        "has_painting": 0,
        "has_blank": 0,
        "missing_file": 0,
        "zero_dimensions": 0,
        "insc_regions_count": [],
        "paint_regions_count": [],
        "blank_regions_count": [],
    }
    
    for r in records:
        regions = r.regions
        
        insc = regions.get("inscription_regions", [])
        paint = regions.get("painting_regions", [])
        blank = regions.get("blank_regions", [])
        
        if insc:
            stats["has_inscription"] += 1
            stats["insc_regions_count"].append(len(insc))
        if paint:
            stats["has_painting"] += 1
            stats["paint_regions_count"].append(len(paint))
        if blank:
            stats["has_blank"] += 1
            stats["blank_regions_count"].append(len(blank))
        
        if not os.path.exists(r.filepath):
            stats["missing_file"] += 1
        
        if r.width == 0 or r.height == 0:
            stats["zero_dimensions"] += 1
    
    # 计算平均区域数量
    for key in ["insc_regions_count", "paint_regions_count", "blank_regions_count"]:
        counts = stats[key]
        stats[f"avg_{key}"] = sum(counts) / len(counts) if counts else 0
        stats[f"max_{key}"] = max(counts) if counts else 0
    
    return stats
