"""
自动标签计算服务
从 AI 分析结果和画作尺寸中实时计算 computed_tags
"""

import json
from typing import List, Dict, Any, Optional


# ────────────────────────────────────────────────────────────────
# 1. 情感标签（5档，基于 174 条数据分布: -3.55 ~ 7.35）
# ────────────────────────────────────────────────────────────────
def get_emotion_tag(emotion_score: Optional[float]) -> Optional[str]:
    if emotion_score is None:
        return None
    if emotion_score <= -2.0:
        return "愤慨/压抑"
    elif emotion_score <= -0.5:
        return "恬淡悠然"
    elif emotion_score <= 0.5:
        return "平静"
    elif emotion_score <= 2.0:
        return "旷达"
    else:
        return "昂扬向上"


# ────────────────────────────────────────────────────────────────
# 2. 尺幅标签（基于北兰亭国画尺寸标准）
#    换算公式: 平方尺 = 长(cm) × 宽(cm) / 1089
# ────────────────────────────────────────────────────────────────
# 标准尺寸定义（单位: cm）
SIZE_STANDARDS = [
    # (长, 宽, 名称, 面积平方尺)
    (33, 33, "小品", 1.0),
    (45, 33, "小品", 1.4),
    (69, 46, "四尺三开", 2.8),
    (69, 34, "四尺四开", 2.0),
    (68, 68, "四尺对开斗方", 4.0),
    (34, 136, "四尺对开长条", 4.0),
    (69, 136, "四尺整纸", 8.0),
    (138, 69, "四尺整纸", 8.0),
    (81, 155, "五尺整纸", 11.5),
    (153, 84, "五尺整纸", 11.5),
    (97, 178, "六尺整纸", 15.6),
    (180, 97, "六尺整纸", 15.6),
    (122, 244, "八尺整纸", 27.0),
    (248, 129, "八尺整纸", 27.0),
    (144, 366, "丈二整纸", 48.0),
    (367, 144, "丈二整纸", 48.0),
    (200, 498, "丈六整纸", 92.0),
    (503, 193, "丈六整纸", 92.0),
    (600, 248, "丈八尺", 136.0),
]

# 按面积从小到大排列
SIZE_STANDARDS.sort(key=lambda x: x[3])

# 面积阈值映射（面积平方尺 → 标签名）
SIZE_AREA_THRESHOLDS = [
    (2, "小幅"),
    (4, "四开/斗方"),
    (8, "四尺整纸"),
    (15, "五尺整纸"),
    (27, "六尺整纸"),
    (48, "八尺整纸"),
]


def get_size_tag(height_cm: Optional[float], width_cm: Optional[float]) -> Optional[str]:
    """根据画作尺寸计算尺幅标签"""
    if height_cm is None or width_cm is None:
        return None

    # 换算平方尺（长×宽/1089）
    area_sqchi = (height_cm * width_cm) / 1089

    # 精确匹配标准尺寸
    for h, w, name, area in SIZE_STANDARDS:
        if abs(height_cm - h) <= 2 and abs(width_cm - w) <= 2:
            return name

    # 按阈值区间匹配
    for threshold, label in SIZE_AREA_THRESHOLDS:
        if area_sqchi <= threshold:
            return label

    return "丈二及以上"


# ────────────────────────────────────────────────────────────────
# 3. 题材标签（从 material_tags 和 title 推断）
# ────────────────────────────────────────────────────────────────
MATERIAL_CATEGORIES = {
    "花鸟": ["梅", "兰", "竹", "菊", "松", "牡丹", "荷", "莲", "兰", "菊", "桃", "海棠", "芍药",
              "牡丹", "紫藤", "木棉", "水仙", "山茶", "绣球", "芙蓉", "葵", "榴", "荔枝", "枇杷",
              "鸟", "雀", "燕", "鹦鹉", "鹭", "鹤", "鸽", "鸡", "鸭", "鹅", "鱼", "虾", "蟹",
              "蝶", "蜻蜓", "蝉", "虫", "蛙", "龟", "蛙鸣", "草虫", "蜂", "蟋蟀"],
    "人物": ["人", "仕女", "渔翁", "农夫", "书生", "佛像", "罗汉", "观音", "仙人", "高士", "孩童",
              "女", "子", "翁", "叟", "客", "友", "徒", "主", "仆"],
    "山水": ["山", "水", "石", "云", "泉", "瀑", "江", "湖", "溪", "松石", "山水", "岩", "崖",
              "峰", "岭", "洲", "岛", "岸", "帆", "舟", "桥", "亭", "寺", "塔", "楼", "阁"],
}

# 画材关键词 → 直接作为标签
MATERIAL_KEYWORDS = [
    "墨荷", "枯木", "芭蕉", "竹", "兰", "梅", "松", "菊", "牡丹", "芍药",
    "藤蔓", "紫藤", "凌霄", "葡萄", "葫芦", "瓜", "蔬果", "白菜", "萝卜", "葱", "蒜", "姜",
    "鱼", "虾", "蟹", "蛙", "龟", "蝶", "蜻蜓", "虫", "鸟", "雀", "燕", "鹦鹉",
    "鸡", "鸭", "鹅", "鸽", "鹤", "鹭", "喜鹊", "鹰",
    "石", "岩", "峰", "云", "水", "泉", "瀑", "舟", "帆", "桥", "亭",
    "松石", "松藤", "松菊", "松柏",
]


def get_material_tags(material_tags_str: Optional[str], title: Optional[str]) -> List[str]:
    """从 material_tags 和 title 推断题材标签"""
    tags = []

    # 解析 material_tags（逗号分隔字符串）
    if material_tags_str:
        if isinstance(material_tags_str, str):
            parts = [p.strip() for p in material_tags_str.split(",") if p.strip()]
            tags.extend(parts)
        elif isinstance(material_tags_str, list):
            tags.extend([p for p in material_tags_str if p])

    # 从 title 补充关键词（排除"鸟"字，避免"花鸟册"标题误匹配）
    if title:
        for kw in MATERIAL_KEYWORDS:
            # "鸟"字不从 title 里匹配，避免"花鸟册"标题误标
            if kw == "鸟":
                continue
            if kw in title and kw not in tags:
                tags.append(kw)

    return list(dict.fromkeys(tags))  # 去重保留顺序


# ────────────────────────────────────────────────────────────────
# 4. 主题标签（从 content_analysis.themes 提取）
# ────────────────────────────────────────────────────────────────
THEME_CODE_MAP = {
    1: "身世自况",
    2: "咏物寄兴",
    3: "画理自叙",
    4: "时事讽喻",
    5: "吉语祥瑞",
    6: "交游赠答",
}

# 旧主题名称 → 新主题名称 兼容映射（处理历史数据）
THEME_NAME_COMPAT = {
    "记录创作信息": "身世自况",
    "记录创作": "身世自况",
    "即景寄兴与抒怀": "咏物寄兴",
    "即景寄兴": "咏物寄兴",
    "讽喻社会与民生": "时事讽喻",
    "讽喻社会": "时事讽喻",
    "阐述画理画法": "画理自叙",
    "世俗祈愿与谐趣": "吉语祥瑞",
    "世俗祈愿": "吉语祥瑞",
    "应酬送人与雅交": "交游赠答",
    "交游应酬": "交游赠答",
    "自怜自况": "身世自况",
}


def get_theme_tags(content_analysis: Optional[Any]) -> List[str]:
    """从 content_analysis JSON 提取主题标签（v5: 支持新旧主题名称兼容）"""
    if not content_analysis:
        return []

    tags = []

    if isinstance(content_analysis, str):
        try:
            content_analysis = json.loads(content_analysis)
        except Exception:
            return []

    themes = content_analysis.get("themes", [])
    for theme in themes:
        code = theme.get("code")
        name = theme.get("name")
        if code in THEME_CODE_MAP:
            tags.append(THEME_CODE_MAP[code])
        elif name:
            # 兼容旧主题名称
            compat_name = THEME_NAME_COMPAT.get(name, name)
            tags.append(compat_name)
            tags.append(name)

    return tags


# ────────────────────────────────────────────────────────────────
# 5. 时期标签
# ────────────────────────────────────────────────────────────────
def get_period_tag(period_phase: Optional[str]) -> Optional[str]:
    if period_phase in ("早期", "中期", "晚期", "年代不详"):
        return period_phase
    return None


# ────────────────────────────────────────────────────────────────
# 主函数：为单条记录计算 computed_tags
# ────────────────────────────────────────────────────────────────
def compute_tags(record: Dict[str, Any]) -> List[str]:
    """
    接收一条 tubi_analyses 记录字典，返回 computed_tags 列表
    所有标签按固定顺序排列，便于去重和展示
    """
    tags = []

    # 1. 时期
    period = get_period_tag(record.get("period_phase"))
    if period:
        tags.append(period)

    # 2. 尺幅
    size_tag = get_size_tag(
        record.get("artwork_height_cm"),
        record.get("artwork_width_cm"),
    )
    if size_tag:
        tags.append(size_tag)

    # 3. 情感
    content_analysis = record.get("content_analysis")
    emotion_score = None
    if content_analysis:
        if isinstance(content_analysis, str):
            try:
                content_analysis = json.loads(content_analysis)
            except Exception:
                pass
        if isinstance(content_analysis, dict):
            emotion_score = content_analysis.get("sentiment", {}).get("emotion_score")

    emotion_tag = get_emotion_tag(emotion_score)
    if emotion_tag:
        tags.append(emotion_tag)

    # 4. 题材/画材
    material_tags = get_material_tags(
        record.get("material_tags"),
        record.get("title"),
    )
    tags.extend(material_tags)

    # 5. 主题（去重）
    theme_tags = get_theme_tags(record.get("content_analysis"))
    for t in theme_tags:
        if t not in tags:
            tags.append(t)

    return tags
