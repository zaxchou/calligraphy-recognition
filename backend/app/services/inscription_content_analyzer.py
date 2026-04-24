"""
题跋内容分析服务
- LLM主题分类（五大类）
- 情感分析（双通道：规则词表 + Qwen Turbo LLM）
- jieba分词统计
- 特征词提取
"""
import json
import re
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import httpx

from app.services.artist_context_registry import get_artist_birth_year, get_artist_display_name


def _get_artist_sentiment_note(artist: str = None) -> str:
    """根据画家返回情感分析的特殊注意事项，李鱓有含蓄特征，其他画家通用"""
    name = get_artist_display_name(artist) if artist else ""
    if name == "李鱓":
        return "李鱓题跋多含蓄，'借景抒怀'常暗藏压抑愤懑，**表面写景但有愁苦词即判negative**"
    return ""


def _get_artist_theme_note(artist: str = None) -> Tuple[str, str]:
    """
    根据画家返回主题分析的特殊注意事项和别名关键词。
    返回 (易混淆情形说明, 别名关键词，用于替换 {artist_note} 和 {artist_se_names})
    """
    name = get_artist_display_name(artist) if artist else ""
    if name == "李鱓":
        return (
            "含\"懊道人\"署名的题跋，即使有吉祥词（如\"加官\"\"大吉\"等），仍可能是讽喻而非纯粹的世俗祈愿，需结合全文判断。",
            "、懊道人、复堂"
        )
    return ("", "")

# jieba 中文分词
import jieba

# 禁用词表（基础版，可扩展）
STOP_WORDS = set([
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也",
    "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己", "这", "那"
])

# 李鱓特征词库（6维度）
FEATURE_WORDS = {
    "core_arts": ["水", "墨", "笔", "色", "气", "韵", "娱", "戏", "乐", "寄", "自怡", "门户", "法", "师", "我法"],
    "emotion": [
        # 积极-喜悦
        "喜", "笑", "呵", "乐", "欢", "欣",
        # 积极-酣畅
        "狂", "放", "纵", "恣", "酣", "畅", "快",
        # 积极-热爱
        "爱", "慕", "趣", "兴", "怡", "娱",
        # 积极-淡雅
        "清", "静", "幽", "淡", "雅",
        # 积极-傲健
        "傲", "雄", "健", "劲", "凌",
        # 消极-悲愁
        "悲", "哀", "凄", "凉", "愁", "苦", "闷",
        # 消极-愤怒
        "怒", "愤", "憾", "恚", "恼",
        # 消极-叹息
        "叹", "慨", "惘", "惆", "寂",
        # 消极-衰败
        "破", "残", "衰", "败", "倦",
        # 消极-惊恐
        "惊", "恐",
    ],
    "objects": {
        "四君子": ["松", "竹", "梅", "兰", "菊"],
        "蔬果": ["葱", "姜", "蒜", "白菜", "萝卜"],
        "吉祥": ["牡丹", "萱草", "芙蓉", "海棠"],
        "草虫": ["鹅", "鸡", "鸟", "鱼", "蟹", "蝶"],
    },
    "social": ["民", "农", "耕", "田", "粮", "租", "吏", "官", "衙", "权", "贵", "霸", "世", "俗", "尘", "市", "贾", "金"],
    "spacetime": ["春", "夏", "秋", "冬", "晴", "雨", "风", "雪", "晨", "午", "夜", "今", "昔", "年", "岁", "扬州", "兴化", "山东"],
    "philosophy": ["道", "自然", "天趣", "真", "朴", "淡", "空", "静", "虚", "灵", "禅", "雅", "俗", "赏", "鉴", "味"],
}

# 六大主题定义
THEMES = {
    1: {"name": "记录创作信息", "keywords": ["画", "写", "作", "题", "跋", "年", "月", "日", "记", "临", "摹", "制", "自画", "自写"]},
    2: {"name": "即景寄兴与抒怀", "keywords": ["感", "怀", "兴", "寄", "见", "观", "赏", "爱", "喜", "诗", "句", "杜", "前人", "诗意", "题诗", "抄", "吟"]},
    3: {"name": "讽喻社会与民生", "keywords": ["民", "吏", "官", "税", "租", "耕", "农", "苦", "悲", "叹", "世间", "天下", "苍生"]},
    4: {"name": "阐述画理画法", "keywords": ["笔", "墨", "水", "法", "理", "论", "道", "师", "学", "用", "雅俗", "俗", "分之", "笔法", "墨法"]},
    5: {"name": "世俗祈愿与谐趣", "keywords": ["吉", "福", "寿", "顺", "遂", "笑", "戏", "娱", "玩", "大吉", "如意", "富贵"]},
    6: {"name": "应酬送人与雅交", "keywords": ["请指教", "敬请", "雅正", "指正", "惠存", "存念", "补壁", "应酬", "为", "赠", "送", "奉赠", "乞", "教", "正", "年长兄", "仁兄"]},
}

# 李鱓作画心情关键词库（2026-04-14 更新，基于学术研究）
# 积极词汇
POSITIVE_WORDS = set([
    # 喜悦类
    "喜", "笑", "呵", "乐", "欢", "欣",
    # 酣畅类
    "狂", "放", "纵", "酣", "畅", "快",
    # 热爱类
    "爱", "慕", "趣", "兴", "怡", "娱",
    # 淡雅类
    "清", "静", "幽", "淡", "雅",
    # 傲健类
    "傲", "雄", "健", "劲", "凌",
])
# 消极词汇
NEGATIVE_WORDS = set([
    # 悲愁类
    "悲", "哀", "凄", "凉", "愁", "苦", "闷",
    # 愤怒类
    "怒", "愤", "憾", "恚", "恼",
    # 叹息类
    "叹", "慨", "惘", "惆", "寂",
    # 衰败类
    "破", "残", "衰", "败", "倦",
    # 惊恐类
    "惊", "恐", "不安",
])


# ══════════════════════════════════════════════════════════════════════
# v4 多维信号融合规则表
# ══════════════════════════════════════════════════════════════════════

# ── 表1：时间-阶段-基线情感映射表 ─────────────────────────────────────
LIFE_STAGE_TABLE = {
    # (year_start, year_end): {stage, baseline_emotion, weight, description}
    # 三期划分：
    # 早期：1714–1722年（入宫学蒋至首次离京）
    # 中期：1723–约1745年（离京卖画、师从高其佩、见石涛、二次出仕与罢官）
    # 晚期：约1746–1760年（彻底归隐，画风"衰年变法"）
    (1714, 1722): {
        "stage": "早期（入宫学蒋）",
        "baseline_emotion": "积极/中立",
        "emotion_offset": 0.3,     # 早期微偏积极
        "weight": 1.0,            # 阶段权重：晚期作品即使文字平淡也倾向消极
        "description": "师从蒋廷锡，画法工致，抱负满腔",
    },
    (1723, 1745): {
        "stage": "中期（出京卖画）",
        "baseline_emotion": "偏消极",
        "emotion_offset": -0.3,
        "weight": 1.5,
        "description": "仕途受挫，卖画为生，师从高其佩、见石涛，二次出仕后被贬",
    },
    (1746, 1760): {
        "stage": "晚期（彻底归隐）",
        "baseline_emotion": "消极/自嘲",
        "emotion_offset": -0.5,
        "weight": 2.0,
        "description": "题跋谨慎，生活困顿，'老夫卖画'，衰年变法",
    },
}

# ── 表2：题材-主题/情感关联表 ─────────────────────────────────────────
# 画材关键词 → 视觉情感 → 默认主题倾向 + 证据权重
PAINTING_MATERIAL_RULES = [
    {
        "keywords": ["松", "梅", "兰", "竹", "菊", "岁寒三友"],
        "visual_emotion": "傲骨/坚韧",
        "theme_tendency": 2,   # 即景寄兴与抒怀
        "emotion_offset": 0.0, # 中性偏积极（傲骨非消极）
        "weight": 1.2,
        "description": "四君子/岁寒三友 → 即景寄兴/抒怀",
    },
    {
        "keywords": ["牡丹", "藤蔓", "松藤", "松石", "百子", "富贵", "长年"],
        "visual_emotion": "富贵/长寿",
        "theme_tendency": 5,   # 世俗祈愿与谐趣
        "emotion_offset": 0.5,
        "weight": 1.3,
        "description": "牡丹/藤蔓/松石 → 世俗祈愿/应酬",
    },
    {
        "keywords": ["墨荷", "风雨", "枯木", "残荷", "芭蕉", "萧瑟"],
        "visual_emotion": "萧瑟/压抑",
        "theme_tendency": 2,   # 即景寄兴与抒怀（也可能讽喻，由文本信号决定）
        "emotion_offset": -0.5,
        "weight": 1.5,
        "description": "墨荷/风雨/枯木 → 即景抒怀/讽喻",
    },
    {
        "keywords": ["蔬果", "葱", "蒜", "姜", "白菜", "萝卜", "杂画"],
        "visual_emotion": "生活化/趣味",
        "theme_tendency": 5,   # 世俗祈愿与谐趣
        "emotion_offset": 0.3,
        "weight": 1.0,
        "description": "蔬果 → 世俗祈愿/谐趣",
    },
    {
        "keywords": ["鸡", "柏", "鱼", "柿", "加官", "大吉", "喜上眉梢"],
        "visual_emotion": "谐音吉祥",
        "theme_tendency": 5,   # 世俗祈愿与谐趣
        "emotion_offset": 0.5,
        "weight": 1.4,
        "description": "鸡柏鱼柿 → 世俗祈愿（谐音）",
    },
]

# ── 表3：文本特征词库（权重打分表） ────────────────────────────────────
# 主题代码: 1=记录创作信息, 2=即景寄兴与抒怀, 3=讽喻社会与民生,
#           4=阐述画理画法, 5=世俗祈愿与谐趣, 6=应酬送人与雅交
TEXT_SCORING_RULES = {
    3: {  # 讽喻社会与民生 — 高优先级
        "keywords": {
            # +3分词（强信号，一旦触发覆盖即景抒怀）
            "催租": 3, "舆隶": 3, "官粮": 3, "纨绔": 3, "夺朱": 3,
            "世味辣": 3, "卖画难": 3, "官吏": 3, "赋税": 3,
            "纨绔子弟": 3, "恶态": 3,
            # +2分词（中等信号：社会批判/个人困顿/讽刺表达）
            "苍生": 2, "民生": 2, "民": 2, "吏": 2,
            "租": 2, "官": 2, "世间": 2, "天下": 2,
            "世味": 2, "豪家": 2, "冷落": 2, "簪缨": 2,
            "挥毫卖": 2, "寻纸": 2, "索画": 2, "催诗": 2, "催画": 2,
            "艰难": 2, "恼客魂": 2, "俗尘": 2,
            "衣食": 2, "画贱": 2, "何苦": 2, "味犹苦": 2, "百结衣": 2,
            # +1分词（弱信号：需组合才触发）
            "苦": 1, "寒": 1, "难": 1, "恼": 1, "愁": 1,
            "辣": 1, "悔": 1, "怨": 1, "愤": 1,
            "权": 1, "霸": 1,
            "富贵": 1, "名利": 1, "荣华": 1,
            "利市": 1, "卖": 1,
            "不得": 1, "何意": 1, "没处": 1,
        },
        "priority_override": True,  # 得分>=2时直接锁定主题（降低阈值）
        "override_threshold": 2,
        "overrides_theme": 2,       # 覆盖即景寄兴与抒怀
    },
    6: {  # 应酬送人与雅交
        "keywords": {
            "祝": 2, "贺": 2, "赠": 2, "送": 2, "奉赠": 2,
            "敬请": 2, "雅正": 2, "指正": 2, "惠存": 2,
            "补壁": 2, "雅属": 2, "鉴": 2, "乞教": 2,
            "年长兄": 2, "仁兄": 2, "亲翁": 2, "先生": 1,
            "写似": 2, "奉": 1,
        },
        "priority_override": False,
        "requires_recipient": True,  # 需要明确受赠人才触发
    },
    5: {  # 世俗祈愿与谐趣
        "keywords": {
            "多寿": 2, "子孙贤": 2, "大吉": 2, "平安": 2,
            "荣华": 2, "如意": 2, "富贵": 2, "福": 2,
            "寿": 2, "吉": 2, "顺遂": 2, "同到白头": 2,
            "喜": 1, "笑": 1, "戏": 1, "娱": 1,
            "加官": 2, "长命": 2, "吉祥": 2, "祝福": 2,
            "百子": 2, "长年": 2,
        },
        "priority_override": False,
    },
    4: {  # 阐述画理画法
        "keywords": {
            # 复合词（高分）
            "笔法": 2, "墨法": 2, "画理": 2, "师承": 2,
            "仿": 2, "拟": 2, "笔意": 2, "宗派": 2,
            "用笔": 2, "用墨": 2, "画法": 2, "技法": 2,
            "写意": 2, "泼墨": 2, "水墨": 1,
            # 单字词（低分，避免误判）
            "临": 1, "摹": 1,
            # 画理相关短语
            "笔墨": 2, "自娱": 1, "雅俗": 2,
            "长于": 2, "师": 1, "法": 1,
            "门户": 1, "我法": 2,
        },
        "priority_override": False,
    },
    2: {  # 即景寄兴与抒怀
        "keywords": {
            # 强信号 — 抒怀类（核心判据）
            "孤": 2, "愁": 2, "遥": 2, "故山": 2,
            "凄": 2, "凉": 2, "寂": 2, "惘": 2,
            "抒怀": 2, "寄兴": 2, "触景": 2, "即景": 2,
            "空山": 2, "空庭": 2,
            "何用": 1, "何意": 1, "何曾": 1,
            "无复": 1, "不堪": 1,
            # 中信号 — 情感/态度词
            "苍松": 1, "劲竹": 1, "傲霜": 1, "凌云": 1,
            "闲": 1, "静": 1, "爱": 1, "观": 1, "赏": 1,
            "感": 1, "怀": 1, "兴": 1, "寄": 1,
            "叹": 1, "慨": 1, "惆": 1,
            "萧疏": 1, "萧瑟": 1,
            # 弱信号 — 景物词（仅复合词，不用单字）
            "秋风": 0.5, "晚晴": 0.5, "清风": 0.5,
            "寒": 0.5, "暮": 0.5,
        },
        "priority_override": False,
    },
    1: {  # 记录创作信息 — 仅纯记录时触发
        "keywords": {},
        "priority_override": False,
        "base_score": 1,  # 恢复基础分1
    },
}

# 情感词打分（独立于主题，用于 emotion_score 连续值计算）
EMOTION_SCORING = {
    "negative_strong": {  # 强消极 -2分
        "words": ["催租", "舆隶", "官粮", "纨绔", "夺朱", "卖画难",
                   "悲", "愤", "怒", "恚", "恶态", "簪缨", "袴子弟",
                   "纨绔子弟", "世味辣", "画贱", "衣食"],
        "score": -2,
    },
    "negative_moderate": {  # 中消极 -1分
        "words": ["老夫", "白发", "艰难", "寒", "凄", "恼", "悔",
                   "故山遥", "愁", "凉", "闷", "叹", "慨", "惆",
                   "寂", "残", "衰", "败", "倦", "苦", "俗尘",
                   "习气", "脂粉", "俗", "冷落", "索画", "催诗",
                   "何苦", "味犹苦", "百结衣"],
        "score": -1,
    },
    "positive_strong": {  # 强积极 +2分
        "words": ["大吉", "多寿", "子孙贤", "如意", "百事大吉"],
        "score": 2,
    },
    "positive_moderate": {  # 中积极 +1分
        "words": ["喜", "笑", "乐", "欢", "欣", "畅", "快",
                   "傲", "健", "劲", "凌", "怡", "趣"],
        "score": 1,
    },
}

# 主题-情感关联修正表：特定主题强制情感方向
THEME_SENTIMENT_OVERRIDE = {
    3: {  # 讽喻社会与民生
        "polarity": "negative",  # 强制倾向
        "min_score": -1.0,      # 最低情感分
        "override_bonus": -2.0,   # 额外修正分
        "note": "讽喻社会主题强制消极倾向"
    }
}


# ══════════════════════════════════════════════════════════════════════
# v4 尺寸信号规则表
# ══════════════════════════════════════════════════════════════════════

# 尺寸分组阈值（基于李鱓作品研究）
SIZE_CATEGORIES = {
    "小幅": {"max_height": 70, "description": "册页/扇面/小品，便于携带把玩"},
    "中幅": {"min_height": 70, "max_height": 150, "description": "标准立轴，兼顾展示与效率"},
    "大幅": {"min_height": 150, "description": "大轴/通景屏，用于厅堂悬挂或重礼"},
}

# 尺寸×题材→主题权重（基于用户研究的4个核心发现）
SIZE_THEME_RULES = [
    {
        "condition": {"size": "大幅", "materials": ["吉祥", "牡丹", "松柏", "祝寿", "富贵", "长寿"]},
        "theme_boost": {6: 1.5},  # 应酬送人与雅交 +1.5
        "description": "大幅+吉祥题材→应酬/祝寿/厅堂装饰",
    },
    {
        "condition": {"size": "小幅", "materials": ["四君子", "墨荷", "山水"]},
        "theme_boost": {2: 1.0},  # 即景寄兴与抒怀 +1.0
        "description": "小幅+四君子/墨荷→案头清玩/自我遣怀",
    },
    {
        "condition": {"size": "中幅", "materials": ["鱼虾", "蔬果"]},
        "theme_boost": {5: 0.5},  # 世俗祈愿与谐趣 +0.5
        "description": "中幅+鱼虾/蔬果→世俗谐趣",
    },
]

# 尺寸×分期→心境权重
SIZE_PERIOD_MOOD_RULES = [
    {
        "condition": {"size": "大幅", "period": "早期"},
        "theme_boost": {1: 1.0},  # 记录创作信息 +1.0（进呈/正式创作）
        "sentiment_modifier": 0.2,
        "description": "早期大幅→进呈之作，风格工致",
    },
    {
        "condition": {"size": "大幅", "period": "中期"},
        "theme_boost": {3: 0.5},  # 讽喻社会 +0.5（职业画家需要关注）
        "sentiment_modifier": -0.2,
        "description": "中期大幅→职业画家生存策略，润格所需",
    },
    {
        "condition": {"size": "大幅", "period": "晚期"},
        "sentiment_modifier": 0.3,  # 矛盾心理：积极入世期待
        "description": "晚期大幅→入世期待（矛盾心理），或被迫应酬",
        "mood_tag": "入世期待",
    },
    {
        "condition": {"size": "小幅", "period": "晚期"},
        "theme_boost": {2: 0.5},  # 即景寄兴 +0.5
        "sentiment_modifier": -0.3,  # 归隐身心态
        "description": "晚期小幅→归隐后墨戏，抒发性灵",
        "mood_tag": "归隐自遣",
    },
]

# 尺寸解读语料库（用于生成一句话解读）
SIZE_INTERPRETATION = {
    "大幅": {
        "早期": "此画尺幅宏大，或为进呈之作，体现宫廷画家对正式场合的创作态度。",
        "中期": "大幅立轴常见于中期卖画生涯，既展示笔墨功力，也对应更高润格。",
        "晚期": "晚年仍作大幅，或出于对世事的未甘，借大笔挥洒寄寓复杂心绪。",
    },
    "中幅": {
        "通用": "标准立轴尺寸，是李鱓最常用的形制，兼顾展示效果与创作效率。",
    },
    "小幅": {
        "早期": "册页形制便于呈览，符合宫廷画家\"应制\"或进呈的功能需求。",
        "中期": "小景多为案头清玩，或作友人间的笔墨唱和。",
        "晚期": "晚年小品多为墨戏，题材日常，笔墨恣肆，是归隐后抒发性灵的载体。",
    },
}


def get_size_category(width_cm: float = None, height_cm: float = None) -> str:
    """根据高度判断尺寸分组"""
    if not height_cm:
        return "未知"
    if height_cm < 70:
        return "小幅"
    elif height_cm <= 150:
        return "中幅"
    else:
        return "大幅"


def get_size_interpretation(size_category: str, period: str = None) -> str:
    """获取尺寸解读语料"""
    if size_category == "未知":
        return ""
    interp = SIZE_INTERPRETATION.get(size_category, {})
    if period and period in interp:
        return interp[period]
    return interp.get("通用", "")


def _extract_material_category_from_title(title: str, analysis_note: str = None) -> List[str]:
    """从标题和AI画材分析中提取画材类别（匹配 SIZE_THEME_RULES 中的 materials）"""
    material_categories = []
    category_keywords = {
        "吉祥": ["牡丹", "松柏", "松藤", "松石", "长寿", "百子", "富贵", "荣华", "多寿", "长年"],
        "四君子": ["梅", "兰", "竹", "菊", "松", "岁寒三友"],
        "墨荷": ["荷", "莲", "残荷"],
        "山水": ["山水", "泉", "溪"],
        "鱼虾": ["鱼", "虾", "蟹"],
        "蔬果": ["蔬", "果", "葱", "蒜", "姜", "白菜", "萝卜"],
        "祝寿": ["寿", "松鹤", "仙鹤", "鹤"],
    }
    combined = f"{title or ''} {analysis_note or ''}"
    for category, keywords in category_keywords.items():
        if any(kw in combined for kw in keywords):
            material_categories.append(category)
    return list(set(material_categories))


# ══════════════════════════════════════════════════════════════════════
# v4 核心函数
# ══════════════════════════════════════════════════════════════════════

def get_life_stage(year: int) -> Dict:
    """
    查表1：年份 → 人生阶段 + 基线情感 + 权重
    返回 {"stage": ..., "baseline_emotion": ..., "emotion_offset": ..., "weight": ..., "description": ...}
    """
    if year is None:
        return {
            "stage": "未知",
            "baseline_emotion": "中立",
            "emotion_offset": 0.0,
            "weight": 1.0,
            "description": "无年份信息",
        }
    for (start, end), info in LIFE_STAGE_TABLE.items():
        if start <= year <= end:
            return info
    # 超出已知范围
    if year < 1714:
        return LIFE_STAGE_TABLE[(1714, 1722)]  # 按早期处理
    return LIFE_STAGE_TABLE[(1746, 1760)]  # 按晚期处理


def match_painting_materials(title: str, analysis_note: str) -> List[Dict]:
    """
    查表2：画作标题 + AI画材分析 → 匹配题材规则
    返回匹配到的规则列表 [{"rule": ..., "matched_keywords": [...]}]
    """
    combined_text = f"{title or ''} {analysis_note or ''}"
    matches = []
    for rule in PAINTING_MATERIAL_RULES:
        matched_kw = [kw for kw in rule["keywords"] if kw in combined_text]
        if matched_kw:
            matches.append({
                "rule": rule,
                "matched_keywords": matched_kw,
            })
    return matches


def score_text_keywords(text: str) -> Tuple[Dict[int, float], float]:
    """
    查表3：文本关键词扫描 → 主题得分 + 情感分值
    返回 (theme_scores, emotion_score)
    - theme_scores: {theme_code: score, ...}
    - emotion_score: 连续值（正=积极，负=消极）
    """
    theme_scores = {}
    # 各主题基础分
    for code, rule in TEXT_SCORING_RULES.items():
        base = rule.get("base_score", 0)
        if base > 0:
            theme_scores[code] = base

    # 关键词匹配累加
    for code, rule in TEXT_SCORING_RULES.items():
        kw_dict = rule.get("keywords", {})
        for kw, score in kw_dict.items():
            if kw in text:
                theme_scores[code] = theme_scores.get(code, 0) + score

    # 情感分值计算
    emotion_score = 0.0
    for category, config in EMOTION_SCORING.items():
        for word in config["words"]:
            if word in text:
                emotion_score += config["score"]

    return theme_scores, emotion_score


def classify_inscription_v4(
    text: str,
    year: int = None,
    title: str = None,
    analysis_note: str = None,
    width_cm: float = None,
    height_cm: float = None,
    artist: str = None,
) -> Dict:
    """
    v4 多维信号融合分类器
    ─────────────────────────────────
    四个信号维度：
    1. 时间信号：year → 人生阶段 → 基线情感修正
    2. 画作内容信号：title + analysis_note → 题材匹配 → 主题/情感倾向
    3. 文本信号：关键词扫描 → 主题得分累加 + 情感分值
    4. 尺寸信号：width_cm + height_cm → 尺寸分组 → 主题/心境权重

    返回：
    {
        "themes": [{"code": 1, "name": "...", "confidence": 0.9, "score": 3.0}, ...],
        "sentiment": {
            "polarity": "positive"|"negative"|"neutral",
            "emotion_score": 1.5,  # 连续值，用于时间序列分析
            "reasoning": "..."
        },
        "signals": {
            "time": {...},        # 时间信号明细
            "painting": [...],    # 画作内容信号明细
            "text": {...},        # 文本信号明细
            "size": {...},        # 尺寸信号明细
        },
        "special_rules": [...],   # 触发的特殊规则
    }
    """
    signals = {"time": {}, "painting": [], "text": {}, "size": {}}
    special_rules = []

    # ── 维度1：时间信号 ──────────────────────────────────────────
    life_stage = get_life_stage(year)
    signals["time"] = {
        "year": year,
        "stage": life_stage["stage"],
        "baseline_emotion": life_stage["baseline_emotion"],
        "emotion_offset": life_stage["emotion_offset"],
        "weight": life_stage["weight"],
    }

    # ── 维度2：画作内容信号 ──────────────────────────────────────
    painting_matches = match_painting_materials(title, analysis_note)
    painting_theme_scores = {}
    painting_emotion_offset = 0.0
    for match in painting_matches:
        rule = match["rule"]
        code = rule["theme_tendency"]
        # 画作内容信号：0.7*weight（画作是辅助信号，文本为主）
        painting_theme_scores[code] = painting_theme_scores.get(code, 0) + rule["weight"] * 0.7
        painting_emotion_offset += rule["emotion_offset"]
        signals["painting"].append({
            "matched_keywords": match["matched_keywords"],
            "visual_emotion": rule["visual_emotion"],
            "theme_tendency": THEMES[code]["name"],
            "weight": rule["weight"],
        })

    # ── 维度3：文本信号 ──────────────────────────────────────────
    text_theme_scores, text_emotion_score = score_text_keywords(text or "")
    signals["text"] = {
        "theme_scores": {str(k): v for k, v in text_theme_scores.items()},
        "emotion_score": text_emotion_score,
    }

    # ── 维度4：尺寸信号 ──────────────────────────────────────────
    size_theme_boost = {}  # 主题权重加成
    size_sentiment_modifier = 1.0  # 情感极性修正
    size_mood_tag = None
    size_category = "未知"
    period_phase = get_period_phase(year, artist)
    material_categories = []
    
    if width_cm or height_cm:
        size_category = get_size_category(width_cm, height_cm)
        material_categories = _extract_material_category_from_title(title or "", analysis_note)
        size_signals = []
        
        # 尺寸×题材→主题权重
        for rule in SIZE_THEME_RULES:
            cond = rule["condition"]
            if cond["size"] == size_category:
                # 检查题材关键词匹配（material_categories 与 rule 中 materials 的交集）
                matched_materials = [m for m in material_categories if m in cond.get("materials", [])]
                if matched_materials:
                    for theme_code, boost in rule["theme_boost"].items():
                        size_theme_boost[theme_code] = size_theme_boost.get(theme_code, 0) + boost
                    size_signals.append(f"{rule['description']}")
        
        # 尺寸×分期→心境权重
        for rule in SIZE_PERIOD_MOOD_RULES:
            cond = rule["condition"]
            if cond["size"] == size_category and cond["period"] == period_phase:
                if "theme_boost" in rule:
                    for theme_code, boost in rule["theme_boost"].items():
                        size_theme_boost[theme_code] = size_theme_boost.get(theme_code, 0) + boost
                if "sentiment_modifier" in rule:
                    size_sentiment_modifier = rule["sentiment_modifier"]
                if "mood_tag" in rule:
                    size_mood_tag = rule["mood_tag"]
                size_signals.append(f"{rule['description']}")
        
        signals["size"] = {
            "size_category": size_category,
            "width_cm": width_cm,
            "height_cm": height_cm,
            "material_categories": material_categories,
            "period": period_phase,
            "theme_boost": size_theme_boost,
            "sentiment_modifier": size_sentiment_modifier,
            "mood_tag": size_mood_tag,
            "signals": size_signals,
            "interpretation": get_size_interpretation(size_category, period_phase),
        }

    # ── 信号融合 ─────────────────────────────────────────────────
    # 合并主题得分：文本分 + 画作内容分 + 尺寸分
    merged_scores = {}
    for code, score in text_theme_scores.items():
        merged_scores[code] = merged_scores.get(code, 0) + score
    for code, score in painting_theme_scores.items():
        merged_scores[code] = merged_scores.get(code, 0) + score
    # 新增：尺寸信号主题权重加成
    for code, boost in size_theme_boost.items():
        merged_scores[code] = merged_scores.get(code, 0) + boost

    # 合并情感分值：文本情感为基底，时间/画作/尺寸作为修正
    # 时间修正：当文本本身有消极信号时放大，无消极信号时微调
    emotion_score = text_emotion_score
    if text_emotion_score < 0:
        # 文本已有消极信号 → 时间偏移放大（乘法）
        emotion_score += life_stage["emotion_offset"] * 1.5
    else:
        # 文本无消极信号 → 时间偏移微调（不强制覆盖文本信号）
        emotion_score += life_stage["emotion_offset"] * 0.3
    emotion_score += painting_emotion_offset
    # 新增：尺寸情感修正（加法修正，小幅偏移方向）
    emotion_score += size_sentiment_modifier

    # ── 特殊规则 ─────────────────────────────────────────────────

    # 规则A：讽喻锁定 — 需要足够强的信号
    # 情况1：有强讽喻词（>=2分的单个词）→ 直接锁定
    # 情况2：只有弱讽喻词（1分词）→ 需要>=3分（至少3个弱词组合）才锁定
    satire_score = merged_scores.get(3, 0)
    # 检查是否有强讽喻词（2分及以上）
    strong_satire_keywords = ["催租", "舆隶", "官粮", "纨绔", "夺朱", "世味辣", "卖画难",
                              "官吏", "赋税", "纨绔子弟", "恶态", "苍生", "民生",
                              "世味", "豪家", "冷落", "簪缨", "挥毫卖", "寻纸",
                              "索画", "催诗", "催画", "艰难", "恼客魂", "俗尘",
                              "衣食", "画贱", "世间", "天下"]
    has_strong_satire = any(kw in (text or "") for kw in strong_satire_keywords)
    # 锁定条件：有强词且>=2，或无强词但>=3
    should_lock_satire = (has_strong_satire and satire_score >= 2) or (not has_strong_satire and satire_score >= 3)
    if should_lock_satire:
        special_rules.append(f"讽喻得分={satire_score}，直接锁定讽喻社会与民生主题")
        # 移除即景抒怀的分数（被覆盖）
        if 2 in merged_scores:
            del merged_scores[2]
        emotion_score -= 1.5  # 讽喻消极修正

    # 规则A2：老夫+困顿词组合 → 讽喻加分（李鱓经典讽喻模式）
    # 注意：只用"老夫"不用"懊道人"（后者太常见，几乎每幅都有）
    text_lower = text or ""
    has_laofu = "老夫" in text_lower
    hardship_words = ["寒", "难", "苦", "醉", "卖", "贫", "困", "泣", "湿"]
    has_hardship = any(w in text_lower for w in hardship_words)
    if has_laofu and has_hardship:
        merged_scores[3] = merged_scores.get(3, 0) + 2
        special_rules.append("老夫+困顿词组合 → 讽喻加分")

    # 规则A3：世味/豪家+冷落 → 讽喻加分（社会批判模式）
    social_critique_pairs = [
        (["世味"], ["辣", "苦", "寒", "知"]),
        (["豪家", "富贵"], ["冷落", "笑", "争"]),
        (["簪缨", "纨绔"], ["恶态", "问", "子弟"]),
    ]
    for triggers, modifiers in social_critique_pairs:
        has_trigger = any(t in text_lower for t in triggers)
        has_modifier = any(m in text_lower for m in modifiers)
        if has_trigger and has_modifier:
            merged_scores[3] = merged_scores.get(3, 0) + 2
            special_rules.append(f"社会批判模式({triggers[0]}+{modifiers[0]}) → 讽喻加分")
            break

    # 规则B：文本<10字且无强特征词 → 强制记录创作信息
    char_count_val = count_chars(text or "")
    has_strong_signal = any(merged_scores.get(c, 0) >= 1.5 for c in [2, 3, 4, 5, 6])
    if char_count_val < 10 and not has_strong_signal:
        special_rules.append("文本<10字且无强特征词，强制记录创作信息")
        merged_scores = {1: 10}  # 强制置顶
        emotion_score = 0  # 强制中立

    # 规则C：蔬果+辣/蒜 → 世俗谐趣加分
    painting_text = f"{title or ''} {analysis_note or ''}"
    if any(kw in painting_text for kw in ["蔬果", "葱", "蒜", "姜", "白菜", "萝卜"]):
        if any(kw in (text or "") for kw in ["辣", "蒜", "葱"]):
            merged_scores[5] = merged_scores.get(5, 0) + 2
            emotion_score += 0.5  # 幽默感
            special_rules.append("蔬果+辣/蒜 → 世俗谐趣加分")

    # 规则D：应酬需明确受赠人（"写/摹/作"不等于应酬）
    if merged_scores.get(6, 0) > 0:
        # 检查是否有明确受赠人标记
        recipient_markers = ["赠", "送", "奉", "雅正", "指正", "惠存", "补壁",
                           "雅属", "乞教", "年长兄", "仁兄", "亲翁", "写似",
                           "为.", "祝", "贺"]
        has_recipient = any(m in (text or "") for m in recipient_markers)
        if not has_recipient:
            # 降权：应酬分数减半
            merged_scores[6] = merged_scores[6] * 0.3
            special_rules.append("无明确受赠人，应酬得分降权")

    # ── 生成主题结果 ─────────────────────────────────────────────
    # 按得分排序，取前3个非零主题
    sorted_themes = sorted(merged_scores.items(), key=lambda x: x[1], reverse=True)

    themes_result = []
    for code, score in sorted_themes:
        if score <= 0:
            continue
        # 置信度：基于得分归一化，score>=3 → 高置信, score 1-2 → 中置信
        if score >= 5:
            confidence = 0.9
        elif score >= 3:
            confidence = 0.8
        elif score >= 2:
            confidence = 0.7
        elif score >= 1:
            confidence = 0.6
        else:
            confidence = 0.5
        # 第一主题至少0.5
        if len(themes_result) == 0:
            confidence = max(confidence, 0.5)
        # 后续主题按与第一主题的得分比降权
        if themes_result:
            ratio = score / max(themes_result[0]["score"], 0.01)
            confidence = min(confidence * ratio, 0.9)
        # 尺寸boost置信度折扣：纯boost贡献的主题比有文本/画作信号的置信度低
        if code in size_theme_boost and size_theme_boost[code] > 0:
            boost_score = size_theme_boost[code]
            boost_ratio = min(boost_score / max(score, 0.01), 1.0)
            # 纯boost最高0.75折扣，纯文本/画作信号不打折
            confidence *= (0.5 + 0.5 * (1 - boost_ratio))
        themes_result.append({
            "code": code,
            "name": THEMES[code]["name"],
            "confidence": round(confidence, 2),
            "score": round(score, 2),
        })
        if len(themes_result) >= 3:
            break

    # 如果没有主题，默认记录创作信息
    if not themes_result:
        themes_result = [{"code": 1, "name": "记录创作信息", "confidence": 0.9, "score": 1.0}]

    # ── 主题-情感关联修正（最后一步，优先级最高） ─────────────────
    # 检查是否有主题需要强制情感修正
    main_theme_code = None
    if themes_result:
        main_theme_code = themes_result[0]["code"]
    
    theme_sentiment_applied = False
    if main_theme_code and main_theme_code in THEME_SENTIMENT_OVERRIDE:
        override_rule = THEME_SENTIMENT_OVERRIDE[main_theme_code]
        special_rules.append(override_rule["note"])
        # 应用修正分
        emotion_score += override_rule["override_bonus"]
        # 强制极性
        if override_rule["polarity"] == "negative" and emotion_score > override_rule["min_score"]:
            emotion_score = min(emotion_score, override_rule["min_score"])
        theme_sentiment_applied = True

    # ── 生成情感结果 ─────────────────────────────────────────────
    if emotion_score > 0.5:
        polarity = "positive"
    elif emotion_score < -0.5:
        polarity = "negative"
    else:
        polarity = "neutral"
    
    # 主题强制极性（兜底）
    if theme_sentiment_applied and main_theme_code in THEME_SENTIMENT_OVERRIDE:
        override_rule = THEME_SENTIMENT_OVERRIDE[main_theme_code]
        polarity = override_rule["polarity"]

    sentiment_result = {
        "polarity": polarity,
        "emotion_score": round(emotion_score, 2),
        "reasoning": _build_sentiment_reasoning(polarity, emotion_score, life_stage, painting_matches, special_rules),
    }

    return {
        "themes": themes_result,
        "sentiment": sentiment_result,
        "signals": signals,
        "special_rules": special_rules,
    }


def _build_sentiment_reasoning(polarity, emotion_score, life_stage, painting_matches, special_rules) -> str:
    """构建情感判断理由"""
    parts = []
    if life_stage.get("stage") and life_stage["stage"] != "未知":
        parts.append(f"{life_stage['stage']}({life_stage['baseline_emotion']})")
    if painting_matches:
        emotions = list(set(m["rule"]["visual_emotion"] for m in painting_matches))
        parts.append(f"画材:{'/'.join(emotions)}")
    parts.append(f"情感分={emotion_score:.1f}")
    if special_rules:
        parts.append(special_rules[0][:30])
    return "；".join(parts)


@dataclass
class AnalysisResult:
    """题跋内容分析结果"""
    char_count: int
    word_count: int
    ttr: float  # Type-Token Ratio
    themes: List[Dict]  # [{"code": 1, "name": "...", "confidence": 0.9}, ...]
    sentiment: Dict  # {"polarity": "positive", "intensity": 0.8}
    feature_words: Dict  # 各维度特征词统计
    objects_mentioned: List[str]  # 具体物象词
    top_words: List[Tuple[str, int]]  # 高频词Top20


def get_period_phase(year: int, artist: str = None) -> str:
    """
    画家艺术生涯分期（基于出生年份计算年龄阶段）
    
    默认按李鱓分期（早期≤36岁/中期37-59岁/晚期≥60岁），
    如果传入 artist 参数则使用该画家的出生年份计算。
    year=None 时返回"年代不详"。
    """
    if year is None:
        return "年代不详"
    
    birth_year = get_artist_birth_year(artist) if artist else None
    
    if birth_year:
        age = year - birth_year
        if age <= 36:
            return "早期"
        elif age <= 59:
            return "中期"
        else:
            return "晚期"
    else:
        # 无出生年份时，使用通用分期（按世纪中叶划分）
        if year <= 1722:
            return "早期"
        elif year <= 1745:
            return "中期"
        else:
            return "晚期"


def count_chars(text: str) -> int:
    """统计字符数（不含标点）"""
    # 移除标点符号
    text_no_punct = re.sub(r'[，。！？、；：""''（）【】《》\\n\\s]', '', text)
    return len(text_no_punct)


def jieba_tokenize(text: str) -> List[str]:
    """jieba分词，去除停用词"""
    words = jieba.lcut(text)
    return [w for w in words if w not in STOP_WORDS and len(w) > 1]


# 画材/题材关键词表（关键词, 标准化标签）
MATERIAL_KEYWORDS = [
    # 花卉类
    ("紫藤", "紫藤"), ("牡丹", "牡丹"), ("荷花", "荷花"), ("水仙", "水仙"),
    ("玉兰", "玉兰"), ("海棠", "海棠"), ("芙蓉", "芙蓉"), ("石竹", "石竹"),
    ("蝴蝶花", "蝴蝶花"), ("罂粟", "罂粟"), ("萱草", "萱草"),
    ("兰", "兰"), ("梅", "梅"), ("菊", "菊"), ("桃", "桃"), ("柳", "柳"),
    ("莲", "莲"), ("芍药", "芍药"), ("桂", "桂"), ("杏", "杏"),
    # 树木类
    ("芭蕉", "芭蕉"), ("古柏", "柏"), ("松柏", "松"), ("松树", "松"),
    ("松藤", "松"), ("松石", "松"), ("松竹", "松"),
    ("松", "松"), ("柏", "柏"), ("梧桐", "梧桐"),
    # 竹石类
    ("竹石", "竹"), ("竹", "竹"), ("笋", "竹"), ("湖石", "石"), ("怪石", "石"),
    # 蔬果类
    ("白菜", "白菜"), ("萝卜", "萝卜"), ("枇杷", "枇杷"), ("杨梅", "杨梅"),
    ("葡萄", "葡萄"), ("葫芦", "葫芦"), ("石榴", "石榴"), ("荔枝", "荔枝"),
    ("柿子", "柿子"), ("佛手", "佛手"),
    ("葱", "葱"), ("蒜", "蒜"), ("姜", "姜"), ("芋", "芋"),
    # 禽鸟类
    ("鸳鸯", "鸳鸯"), ("仙鹤", "鹤"), ("白鹤", "鹤"), ("孔雀", "孔雀"),
    ("黄鹂", "黄鹂"), ("喜鹊", "喜鹊"), ("燕子", "燕"), ("画眉", "画眉"),
    ("鹰", "鹰"), ("鹤", "鹤"), ("鸡", "鸡"), ("鸭", "鸭"), ("鹅", "鹅"),
    ("鸟", "鸟"), ("雀", "鸟"),
    # 昆虫类
    ("蝴蝶", "蝴蝶"), ("蜜蜂", "蜂"), ("蝉", "蝉"), ("蟋蟀", "蟋蟀"),
    # 水族类
    ("蟹", "蟹"), ("虾", "虾"), ("鱼", "鱼"), ("蛙", "蛙"),
    # 走兽类
    ("马", "马"), ("牛", "牛"), ("猫", "猫"), ("狗", "狗"), ("兔", "兔"),
    # 其他题材
    ("山水", "山水"), ("百子", "百子"), ("富贵", "富贵"), ("长寿", "长寿"),
    ("岁寒三友", "岁寒三友"),
]

# 需要特殊处理的单字（容易误匹配）
GENERIC_SINGLE_CHARS = {"石", "月", "云", "雪", "鸟"}


def extract_material_tags(title: str, analysis_note: str) -> List[str]:
    """从作品标题和AI分析内容中提取画材标签，返回去重列表。"""
    combined = (title or "") + " " + (analysis_note or "")
    if not combined.strip():
        return []
    
    tags = []
    seen = set()
    
    for keyword, tag in MATERIAL_KEYWORDS:
        if tag in seen:
            continue
        
        # 单字特殊处理
        if keyword in GENERIC_SINGLE_CHARS and len(keyword) == 1:
            if keyword == "石":
                # "石"字：需要检查是否是"湖石/怪石/奇石"等（仅在标题中）
                if keyword in (title or ""):
                    idx = (title or "").find(keyword)
                    if idx > 0 and title[idx - 1] in "湖怪奇":
                        tags.append(tag)
                        seen.add(tag)
            elif keyword == "鸟":
                # "鸟"字：需要 analysis_note 中确实提到鸟相关内容，不只是标题
                bird_keywords = ["鸟", "雀", "燕", "鹦鹉", "鹭", "鹤", "鸽", "鸡", "鸭", "鹅", "鹌鹑", "喜鹊", "鹰", "黄鹂"]
                has_bird = any(k in (analysis_note or "") for k in bird_keywords)
                if has_bird:
                    tags.append(tag)
                    seen.add(tag)
            else:
                # 其他单字（月、云、雪）：在标题中匹配
                if keyword in (title or ""):
                    tags.append(tag)
                    seen.add(tag)
            continue
        
        # 多字关键词：在标题+分析内容中匹配
        if keyword in combined:
            tags.append(tag)
            seen.add(tag)
    
    return tags


def calculate_ttr(words: List[str]) -> float:
    """计算词汇多样性指数（Type-Token Ratio）"""
    if not words:
        return 0.0
    unique_words = set(words)
    return len(unique_words) / len(words)


def extract_feature_words(words: List[str]) -> Dict:
    """提取特征词统计"""
    word_set = set(words)
    result = {}

    # 核心艺术理念
    result["core_arts"] = [w for w in FEATURE_WORDS["core_arts"] if w in word_set]
    # 情感词
    result["emotion"] = [w for w in FEATURE_WORDS["emotion"] if w in word_set]
    # 社会民生
    result["social"] = [w for w in FEATURE_WORDS["social"] if w in word_set]
    # 时空
    result["spacetime"] = [w for w in FEATURE_WORDS["spacetime"] if w in word_set]
    # 哲学审美
    result["philosophy"] = [w for w in FEATURE_WORDS["philosophy"] if w in word_set]

    return result


def extract_objects(text: str) -> List[str]:
    """提取具体物象词"""
    objects = []
    for category, words in FEATURE_WORDS["objects"].items():
        for word in words:
            if word in text:
                objects.append(word)
    return list(set(objects))


def rule_based_theme_classification(text: str) -> List[Dict]:
    """
    基于规则的主题分类（快速初筛）
    返回可能的多标签分类结果
    """
    themes = []
    text_lower = text.lower()

    for code, theme_info in THEMES.items():
        score = 0
        for keyword in theme_info["keywords"]:
            if keyword in text_lower:
                score += 1
        if score > 0:
            confidence = min(score / 3, 0.9)  # 最高0.9
            themes.append({
                "code": code,
                "name": theme_info["name"],
                "confidence": round(confidence, 2)
            })

    # 按置信度排序
    themes.sort(key=lambda x: x["confidence"], reverse=True)
    return themes if themes else [{"code": 0, "name": "未分类", "confidence": 0.0}]


def rule_based_sentiment_analysis(text: str, feature_words: Dict) -> Dict:
    """
    基于情感词的情感分析（通道1）
    """
    # 从特征词中提取情感词
    emotion_words = feature_words.get("emotion", [])

    positive_count = sum(1 for w in emotion_words if w in POSITIVE_WORDS)
    negative_count = sum(1 for w in emotion_words if w in NEGATIVE_WORDS)

    # 判定极性
    if positive_count > negative_count:
        polarity = "positive"
    elif negative_count > positive_count:
        polarity = "negative"
    else:
        polarity = "neutral"

    # 情感强度（0-1）
    total_emotion = positive_count + negative_count
    intensity = min(total_emotion / 3, 1.0) if total_emotion > 0 else 0.0

    return {
        "polarity": polarity,
        "intensity": round(intensity, 2),
        "positive_words": [w for w in emotion_words if w in POSITIVE_WORDS],
        "negative_words": [w for w in emotion_words if w in NEGATIVE_WORDS],
    }


LLM_SENTIMENT_PROMPT = """你是一位精通中国古代书画题跋情感分析的专家。请分析以下题跋文本的情感极性和强度。

题跋内容：
{text}

请以JSON格式返回分析结果：
{{
  "polarity": "positive" | "negative" | "neutral",
  "intensity": 0.0到1.0之间的数值，表示情感强度，
  "reasoning": "一句话说明判断理由，15字以内"
}}

要求：
- 只返回JSON，不要有其他内容
- intensity：积极或消极情感越强烈越接近1.0，完全中性为0.0"""

# v3版本prompt：详细情感分析
LLM_SENTIMENT_PROMPT_V3 = """你是一位中国古代书画题跋情感分析专家。请严格判断以下题跋的情感倾向。

【情感分类——必须严格遵守】

**positive（积极）必须满足以下之一**：
- 歌颂品格/理想：赞松竹梅菊高洁，寄托凌云志向
- 世俗祈愿：多子多福、长命富贵、平安吉祥
- 创作愉悦/自信：享受笔墨，表达艺术自信
- 友情雅交：真诚祝贺友人升迁、寿辰
- 关键词：凌云、傲霜、多寿子孙贤、平安、大吉、自怡悦、笑口、好音、春色

**negative（消极）满足以下之一**：
- 仕途失意：感慨年老无成、白发、被贬、无心情
- 社会批判：揭露官吏凶横、赋税沉重、民生疾苦
- 生活困顿：卖画艰难、催租恼人、衣食无着
- 世态炎凉：讽刺豪门奢靡、人心势利（世味辣、防辣）
- 压抑愁苦：风雨凄凄、荒园冷淡、故山遥不可及
- 关键词：老夫、白发、艰难、困、寒、凄、恼、恨、俗尘、催租、画贱、世味、辣、悔、孤、愁、遥

**neutral（中性）**：仅客观记录创作信息、纯技法讨论、无明显情感表达

【特别注意】
{artist_note}
- 祝寿/吉祥语明确出现 → positive
- 纯年款/仅署名/纯技法说明 → neutral

【输出格式】只返回JSON，不要其他文字：
{{"polarity": "negative", "reasoning": "简要说明"}}

【题跋内容】
{text}

【输出】"""


LLM_THEME_PROMPT = """分析以下中国古代书画题跋的内容，判断它属于哪个主题类别。

题跋内容：
{text}

六大主题分类：
1. 记录创作信息：纪年、落款、说明创作时间地点
2. 即景寄兴与抒怀：感怀、寄兴、观赏、即兴创作、触景生情
3. 讽喻社会与民生：议论民瘼、讽刺官吏、同情百姓
4. 阐述画理画法：讨论笔法、墨法、画法、师承、艺术理念
5. 世俗祈愿与谐趣：吉祥祝福、幽默戏谑、娱乐消遣
6. 应酬送人与雅交：请指教、敬请雅正、惠存、指正、应酬之作、赠予友人

请以JSON格式返回：
{{"theme_code": 1-6, "theme_name": "主题名", "confidence": 0.0到1.0}}

要求：只返回JSON，不要有其他内容。"""

# 组合分析 Prompt：一次调用同时返回主题和情感
LLM_COMBINED_PROMPT_V1 = """你是一位中国古代书画题跋研究专家。请分析以下题跋，判断其主题分类和情感倾向。

【六大主题定义】

**主题1（记录创作信息）**：仅记录创作时间、地点、别号，无其他明确主题
**主题2（即景寄兴与抒怀）**：借景抒情、托物言志，表达个人心境、人生感悟
**主题3（讽喻社会与民生）**：关注现实、批判时弊、揭露民生疾苦、讽刺权贵
**主题4（阐述画理画法）**：探讨笔墨技法、宗派师承、创作理念
**主题5（世俗祈愿与谐趣）**：世俗吉祥寓意，或带生活化、趣味化描写
**主题6（应酬送人与雅交）**：为亲友、官员所作，含祝贺、送别、应酬性质

【情感分类】

**positive（积极）**：歌颂品格/理想、世俗祈愿、创作愉悦/自信、友情雅交
**negative（消极）**：仕途失意、社会批判、生活困顿、世态炎凉、压抑愁苦
**neutral（中性）**：仅客观记录创作信息、纯技法讨论、无明显情感表达

【特别注意】
{artist_note}
- "富贵"在讽喻语境下是批判对象（如"富贵花无脂粉恶态"）
- 祝寿/吉祥祝福类题跋即使有牢骚话，整体倾向仍是positive
- 必须返回至少2个主题（题跋少于5字除外）

【输出格式】只返回JSON，不要其他文字：
{{"themes": [{{"code": 3, "name": "讽喻社会与民生", "confidence": 0.8}}], "themes_reasoning": "主题判断理由", "sentiment": {{"polarity": "negative", "intensity": 0.7, "reasoning": "情感判断理由"}}, "overall_reasoning": "综合分析"}}

【题跋内容】
{text}

【输出】"""


# 矛盾检测重试 Prompt
LLM_CONFLICT_RETRY_PROMPT = """请重新审视以下题跋的分析结果，检查是否存在明显矛盾：

【之前的分析结果】
主题：{themes}
情感：{sentiment}

【题跋原文】
{text}

【需要检查的潜在矛盾】
{conflicts}

请重新判断这段题跋的主题和情感。如果发现之前的分析有误，请给出正确的判断。如果确认之前的分析正确，请说明理由。

【输出格式】只返回JSON：
{{"themes": [{{"code": 3, "name": "讽喻社会与民生", "confidence": 0.8}}], "sentiment": {{"polarity": "negative", "intensity": 0.7, "reasoning": "判断理由"}}, "resolved": true/false, "explanation": "矛盾是否解决及原因"}}

【输出】"""


# v3版本prompt：多标签主题分类（修正版）
LLM_THEME_PROMPT_V3 = """你是一位中国古代书画题跋研究专家。请根据以下题跋内容，严格按照六类定义判断其主题归属。

【六大主题定义】

**主题1（记录创作信息）**
- 定义：仅记录创作时间、地点、别号，无其他明确主题
- 关键词：制、写、画、题、于某斋、落款{artist_se_names}
- 仅当题跋无其他明确主题时归此

**主题2（即景寄兴与抒怀）**
- 定义：借景抒情、托物言志，表达个人心境、人生感悟
- 关键词：孤、愁、遥、故山、苍松、劲竹、傲霜、凌云、闲、静、爱、观、赏
- 无社会批判、无吉祥寓意时归此

**主题3（讽喻社会与民生）**
- 定义：关注现实、批判时弊、揭露民生疾苦、讽刺权贵
- 关键词：官吏、催租、官粮、村愚、纨绔、舆隶、夺朱(非正统)、世味辣(人情冷暖)、利市、卖画艰难、俗尘、衣食、民生
- **必须是批判/讽刺性质的内容，没有批判意味就不是此类别**

**主题4（阐述画理画法）**
- 定义：探讨笔墨技法、宗派师承、创作理念
- 关键词：仿、拟、摹、临、笔意、墨法、自娱、画理、师承、宗派
- 以理论探讨为主时归此

**主题5（世俗祈愿与谐趣）**
- 定义：世俗吉祥寓意，或带生活化、趣味化描写
- 关键词：多寿、子孙贤、百事大吉、平安、顺遂、同到白头、雅蒜、谐音（鸡=吉、鱼=余、蝠=福）、富贵、长命、吉祥、祝福
- **吉祥祝福类内容优先归此**

**主题6（应酬送人与雅交）**
- 定义：为亲友、官员所作，含祝贺、送别、应酬性质
- 关键词：请指教、敬请、雅正、祝、贺、送、赠、年兄、先生、亲翁、为XX作
- 明确受赠对象时归此

【判断规则】
- **必须返回至少2个主题**（题跋字数少于5字除外）
- 按主题覆盖度排序：主要主题排在最前
- 典型组合示例：
  - "日日临池画水仙..." → 记录创作信息(0.9), 阐述画理画法(0.7)
  - "闲爱孤云静爱僧..." → 即景寄兴与抒怀(0.9), 记录创作信息(0.7)
  - "增其寿也、增其福也" → 世俗祈愿与谐趣(0.9), 应酬送人与雅交(0.6)
  - "多寿子孙贤" → 世俗祈愿与谐趣(0.9), 即景寄兴与抒怀(0.5)
  - 含"世味辣"/"催租"/"夺朱" → 讽喻社会与民生(0.8), 即景寄兴与抒怀(0.6)
  - 祝寿题跋 → 应酬送人与雅交(0.9), 世俗祈愿与谐趣(0.7)
  - "一路荣华" → 世俗祈愿与谐趣(0.8), 即景寄兴与抒怀(0.5)
  - "加官图"/"百事大吉图"/"喜上眉梢" → 世俗祈愿与谐趣(0.9), 应酬送人与雅交(0.7)
  - "和合生孩"/"鸳鸯莲子" → 世俗祈愿与谐趣(0.9), 应酬送人与雅交(0.8)
  - "喜遇圣明时" → 世俗祈愿与谐趣(0.8), 应酬送人与雅交(0.7)（吉祥语非讽喻）
- **易混淆情形**：
  - 含"加官""大吉""喜""福""寿""贺"等吉祥词的题跋，即使有特殊署名（如"懊道人"），也归世俗祈愿而非讽喻
  - **"写""摹""作"不等于应酬**：落款中的"写/摹/作"仅表示创作，不是赠送。只有出现"赠""请...教""祝""贺""奉送""写似...教"等明确指向收件人的用语，才归应酬送人
  - 纯写景抒怀诗即使署名含特殊别号，也归即景寄兴与抒怀，不是应酬也不是世俗祈愿
  {artist_note}

【输出格式】只返回JSON，不要其他文字：
{{"themes": [{{"code": 3, "name": "讽喻社会与民生", "confidence": 0.9}}, ...], "reasoning": "简要说明"}}

【题跋内容】
{text}

【输出】"""


async def llm_sentiment_analysis(text: str) -> Dict:
    """
    调用 Qwen Turbo 分析情感（通道2）
    """
    from app.core.config import get_settings
    settings = get_settings()
    api_key = settings.QWEN_API_KEY
    base_url = settings.QWEN_BASE_URL

    if not api_key:
        return {"polarity": "neutral", "intensity": 0.0, "reasoning": "未配置API Key"}

    prompt = LLM_SENTIMENT_PROMPT.format(text=text[:500])

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "qwen3.5-plus",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                    "temperature": 0.1,
                    "enable_thinking": False
                }
            )
            response.raise_for_status()
            result = response.json()
            raw = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            import json as _json
            parsed = _json.loads(raw)
            return {
                "polarity": parsed.get("polarity", "neutral"),
                "intensity": float(parsed.get("intensity", 0.0)),
                "reasoning": parsed.get("reasoning", "")
            }
    except Exception as e:
        return {"polarity": "neutral", "intensity": 0.0, "reasoning": f"LLM调用失败: {str(e)[:20]}"}


async def llm_theme_classification(text: str) -> Dict:
    """
    调用 Qwen Turbo 分析主题分类（LLM通道）
    """
    from app.core.config import get_settings
    settings = get_settings()
    api_key = settings.QWEN_API_KEY
    base_url = settings.QWEN_BASE_URL

    if not api_key:
        return {"code": 0, "name": "未分类", "confidence": 0.0}

    prompt = LLM_THEME_PROMPT.format(text=text[:500])

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "qwen3.5-plus",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 100,
                    "temperature": 0.1,
                    "enable_thinking": False
                }
            )
            response.raise_for_status()
            result = response.json()
            raw = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            import json as _json
            parsed = _json.loads(raw)
            return {
                "code": parsed.get("theme_code", 0),
                "name": parsed.get("theme_name", "未分类"),
                "confidence": float(parsed.get("confidence", 0.0))
            }
    except Exception as e:
        return {"code": 0, "name": "未分类", "confidence": 0.0}


async def llm_analyze_combined(text: str, artist: str = None, retry_count: int = 0) -> Dict:
    """
    调用 Qwen Turbo 同时分析主题和情感（组合版本）
    返回格式：{
        "themes": [{"code": 3, "name": "讽喻社会与民生", "confidence": 0.8}],
        "sentiment": {"polarity": "negative", "intensity": 0.7, "reasoning": "..."},
        "themes_reasoning": "...",
        "overall_reasoning": "...",
        "success": True,
        "retry_used": False
    }
    """
    from app.core.config import get_settings
    settings = get_settings()
    api_key = settings.QWEN_API_KEY
    base_url = settings.QWEN_BASE_URL

    if not api_key:
        return {"success": False, "error": "未配置API Key"}

    sentiment_note = _get_artist_sentiment_note(artist)
    prompt = LLM_COMBINED_PROMPT_V1.format(text=text[:500], artist_note=sentiment_note)

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "qwen3.5-plus",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 300,
                    "temperature": 0.1,
                    "enable_thinking": False
                }
            )
            response.raise_for_status()
            result = response.json()
            raw = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            import json as _json
            parsed = _json.loads(raw)

            return {
                "themes": parsed.get("themes", []),
                "sentiment": parsed.get("sentiment", {}),
                "themes_reasoning": parsed.get("themes_reasoning", ""),
                "overall_reasoning": parsed.get("overall_reasoning", ""),
                "success": True,
                "retry_used": retry_count > 0
            }
    except Exception as e:
        return {"success": False, "error": f"LLM调用失败: {str(e)[:50]}"}


def detect_sentiment_theme_conflict(text: str, llm_themes: List[Dict], llm_sentiment: Dict) -> Tuple[bool, str]:
    """
    检测主题和情感的矛盾
    返回 (has_conflict, conflict_description)
    """
    if not llm_themes or not llm_sentiment:
        return False, ""

    main_theme = llm_themes[0].get("name", "") if llm_themes else ""
    polarity = llm_sentiment.get("polarity", "neutral")

    text_lower = text or ""

    # 矛盾1：讽喻主题 + 积极情感 + 有强批判词
    strong_satire_words = ["恶态", "簪缨", "纨绔", "夺朱", "世味辣", "催租", "舆隶",
                           "官粮", "画贱", "衣食", "俗尘", "冷落"]
    has_strong_satire = any(w in text_lower for w in strong_satire_words)

    if main_theme == "讽喻社会与民生" and polarity == "positive" and has_strong_satire:
        return True, f"讽喻主题但情感为positive，且有强批判词（{'/'.join([w for w in strong_satire_words if w in text_lower])}）"

    # 茅盾2：应酬送人主题 + 消极情感 + 有牢骚词
    if main_theme == "应酬送人与雅交" and polarity == "negative":
        complaint_words = ["苦", "难", "卖画", "寒", "老", "穷"]
        if any(w in text_lower for w in complaint_words):
            return True, f"应酬送人主题但情感为negative，有牢骚词"

    # 茅盾3：世俗祈愿主题 + 消极情感（一般不应该）
    if main_theme == "世俗祈愿与谐趣" and polarity == "negative":
        # 如果同时有强烈的批判词，可能是矛盾
        if has_strong_satire:
            return True, f"世俗祈愿主题但情感为negative，且有强批判词"

    # 茅盾4：记录创作信息 + 消极情感（一般不应该，除非有很强的人生感慨）
    if main_theme == "记录创作信息" and polarity == "negative":
        strong_life_sorrow = ["老夫", "白发", "艰难", "困", "衰"]
        if any(w in text_lower for w in strong_life_sorrow):
            return True, f"记录创作信息但情感为negative，有人生感慨词"

    return False, ""


async def llm_retry_with_conflict(text: str, llm_themes: List[Dict], llm_sentiment: Dict, conflicts: str) -> Dict:
    """
    当检测到矛盾时，用更详细的 prompt 让 LLM 重新判断
    """
    from app.core.config import get_settings
    settings = get_settings()
    api_key = settings.QWEN_API_KEY
    base_url = settings.QWEN_BASE_URL

    if not api_key:
        return {"success": False, "error": "未配置API Key"}

    # 构建当前主题和情感的文字描述
    themes_str = ", ".join([f"{t['name']}({t['confidence']})" for t in llm_themes[:3]])
    sentiment_str = f"{llm_sentiment.get('polarity', 'unknown')}(强度{llm_sentiment.get('intensity', 0)})"

    prompt = LLM_CONFLICT_RETRY_PROMPT.format(
        themes=themes_str,
        sentiment=sentiment_str,
        text=text[:500],
        conflicts=conflicts
    )

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "qwen3.5-plus",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 300,
                    "temperature": 0.1,
                    "enable_thinking": False
                }
            )
            response.raise_for_status()
            result = response.json()
            raw = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            import json as _json
            parsed = _json.loads(raw)

            return {
                "themes": parsed.get("themes", []),
                "sentiment": parsed.get("sentiment", {}),
                "resolved": parsed.get("resolved", False),
                "explanation": parsed.get("explanation", ""),
                "success": True
            }
    except Exception as e:
        return {"success": False, "error": f"LLM重试失败: {str(e)[:50]}"}


async def llm_theme_classification_v3(text: str, artist: str = None) -> List[Dict]:
    """
    调用 Qwen Turbo 分析主题分类（v3多标签版本）
    返回格式： [{"code": 3, "name": "讽喻社会与民生", "confidence": 0.9}, ...]
    """
    from app.core.config import get_settings
    settings = get_settings()
    api_key = settings.QWEN_API_KEY
    base_url = settings.QWEN_BASE_URL

    if not api_key:
        return [{"code": 0, "name": "未分类", "confidence": 0.0}]

    note, se_names = _get_artist_theme_note(artist)
    prompt = LLM_THEME_PROMPT_V3.format(text=text[:500], artist_note=note, artist_se_names=se_names)

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "qwen3.5-plus",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                    "temperature": 0.1,
                    "enable_thinking": False
                }
            )
            response.raise_for_status()
            result = response.json()
            raw = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            import json as _json
            parsed = _json.loads(raw)
            themes = parsed.get("themes", [])
            return [{"code": t.get("code", 0), "name": t.get("name", "未分类"), "confidence": float(t.get("confidence", 0.0))} for t in themes]
    except Exception as e:
        return [{"code": 0, "name": "未分类", "confidence": 0.0}]


async def llm_sentiment_analysis_v3(text: str, artist: str = None) -> Dict:
    """
    调用 Qwen Turbo 分析情感（v3详细版本）
    """
    from app.core.config import get_settings
    settings = get_settings()
    api_key = settings.QWEN_API_KEY
    base_url = settings.QWEN_BASE_URL

    if not api_key:
        return {"polarity": "neutral", "reasoning": "未配置API Key"}

    artist_note = _get_artist_sentiment_note(artist)
    prompt = LLM_SENTIMENT_PROMPT_V3.format(text=text[:500], artist_note=artist_note)

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "qwen3.5-plus",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 100,
                    "temperature": 0.1,
                    "enable_thinking": False
                }
            )
            response.raise_for_status()
            result = response.json()
            raw = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            import json as _json
            parsed = _json.loads(raw)
            return {
                "polarity": parsed.get("polarity", "neutral"),
                "reasoning": parsed.get("reasoning", "")
            }
    except Exception as e:
        return {"polarity": "neutral", "reasoning": f"LLM调用失败: {str(e)[:20]}"}


def analyze_tiba_content(text: str, year: int = None, title: str = None, analysis_note: str = None, width_cm: float = None, height_cm: float = None, artist: str = None) -> AnalysisResult:
    """
    分析单条题跋内容
    本地规则版本（无需调用LLM，用于快速统计）
    支持v4多维信号融合（year/title/analysis_note）
    """
    if not text or len(text.strip()) < 2:
        return AnalysisResult(
            char_count=0,
            word_count=0,
            ttr=0.0,
            themes=[{"code": 0, "name": "无内容", "confidence": 0.0}],
            sentiment={"polarity": "neutral", "intensity": 0.0},
            feature_words={},
            objects_mentioned=[],
            top_words=[]
        )

    # 1. 字符统计
    char_count = count_chars(text)

    # 2. 分词
    words = jieba_tokenize(text)
    word_count = len(words)

    # 3. 词汇多样性
    ttr = calculate_ttr(words)

    # 4. v4多维信号融合分类（纯规则，不调LLM）
    v4_result = classify_inscription_v4(text, year, title, analysis_note, width_cm, height_cm, artist=artist)

    # 5. 特征词提取
    feature_words = extract_feature_words(words)
    feature_words["v4_signals"] = v4_result["signals"]
    feature_words["v4_special_rules"] = v4_result["special_rules"]

    # 6. 物象提取
    objects = extract_objects(text)

    # 7. 高频词统计
    from collections import Counter
    word_freq = Counter(words)
    top_words = word_freq.most_common(20)

    return AnalysisResult(
        char_count=char_count,
        word_count=word_count,
        ttr=round(ttr, 3),
        themes=v4_result["themes"],
        sentiment=v4_result["sentiment"],
        feature_words=feature_words,
        objects_mentioned=objects,
        top_words=top_words
    )


async def analyze_tiba_content_dual(
    text: str,
    year: int = None,
    title: str = None,
    analysis_note: str = None,
    width_cm: float = None,
    height_cm: float = None,
    artist: str = None,
) -> AnalysisResult:
    """
    双通道分析（v4多维信号融合 + LLM v3）
    ─────────────────────────────────────────
    v4规则引擎为主，LLM为辅（验证/边界case）
    新增参数：year, title, analysis_note 用于多维信号融合
    """
    # 1. 字符统计
    char_count = count_chars(text)
    # 2. 分词
    words = jieba_tokenize(text)
    word_count = len(words)
    # 3. 词汇多样性
    ttr = calculate_ttr(words)
    # 4. 特征词提取
    feature_words = extract_feature_words(words)
    # 5. 物象提取
    objects = extract_objects(text)
    # 6. 高频词
    from collections import Counter
    word_freq = Counter(words)
    top_words = word_freq.most_common(20)

    # ── v4 多维信号融合分类（主通道） ──────────────────────────────
    v4_result = classify_inscription_v4(text, year, title, analysis_note, width_cm, height_cm, artist=artist)
    v4_themes = v4_result["themes"]
    v4_sentiment = v4_result["sentiment"]
    v4_signals = v4_result["signals"]
    v4_special_rules = v4_result["special_rules"]

    # ── LLM v3 分类（辅助通道，用于交叉验证） ──────────────────────
    llm_themes = await llm_theme_classification_v3(text, artist=artist)
    llm_sentiment = await llm_sentiment_analysis_v3(text, artist=artist)

    # ── 融合策略：v4规则为主，LLM为辅 ─────────────────────────────
    # 主题：以v4规则结果为主
    # 如果v4只有一个低置信度主题且LLM有不同意见，参考LLM补充
    final_themes = v4_themes
    if len(v4_themes) == 1 and v4_themes[0]["confidence"] < 0.6:
        # v4不确定时，参考LLM补充第二主题
        v4_codes = {t["code"] for t in v4_themes}
        for lt in llm_themes:
            if lt["code"] not in v4_codes and lt.get("confidence", 0) >= 0.5:
                final_themes.append(lt)
                break

    # 情感：v4规则为主，LLM为交叉验证
    final_polarity = v4_sentiment["polarity"]
    llm_polarity = llm_sentiment.get("polarity", "neutral")
    agreement = final_polarity == llm_polarity

    sentiment = {
        "polarity": final_polarity,
        "intensity": min(abs(v4_sentiment["emotion_score"]) / 3, 1.0),
        "emotion_score": v4_sentiment["emotion_score"],  # 连续值，用于时间序列
        "reasoning": v4_sentiment["reasoning"],
        "llm_polarity": llm_polarity,
        "agreement": agreement,
        "channel_v4": v4_sentiment,
        "channel_llm": llm_sentiment,
    }

    # 保存完整信号明细到 feature_words（用于前端展示和调试）
    feature_words["v4_signals"] = v4_signals
    feature_words["v4_special_rules"] = v4_special_rules

    return AnalysisResult(
        char_count=char_count,
        word_count=word_count,
        ttr=round(ttr, 3),
        themes=final_themes,
        sentiment=sentiment,
        feature_words=feature_words,
        objects_mentioned=objects,
        top_words=top_words
    )


def analyze_with_llm(image_path: str, text: str, api_key: str = None) -> Dict:
    """
    调用LLM进行高精度主题分类和情感分析
    返回结构化JSON结果
    """
    # TODO: 集成 Qwen VL Plus API
    # 当前返回本地规则结果作为占位
    result = analyze_tiba_content(text)
    return {
        "char_count": result.char_count,
        "word_count": result.word_count,
        "ttr": result.ttr,
        "themes": result.themes,
        "sentiment": result.sentiment,
        "objects_mentioned": result.objects_mentioned,
        "feature_words": result.feature_words,
        "reasoning": "基于规则分析（LLM集成待实现）",
    }


if __name__ == "__main__":
    # 测试
    test_text = "八大山人长于笔，清湘大涤子长于墨，至予则长于水。水为笔墨之介绍，而今人不知也。"
    result = analyze_tiba_content(test_text)
    print(f"字符数: {result.char_count}")
    print(f"词数: {result.word_count}")
    print(f"TTR: {result.ttr}")
    print(f"主题: {result.themes}")
    print(f"情感: {result.sentiment}")
    print(f"物象: {result.objects_mentioned}")
