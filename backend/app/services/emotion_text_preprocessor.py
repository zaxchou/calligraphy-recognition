"""
文本情感预处理引擎
────────────────────────────────────────
在词库匹配前对文本进行规则层预处理：

1. MultiWordPriority  — 多字词组优先标记（匹配到的多字词占用的字符不再匹配单字）
2. NegationHandler    — 否定词检测 + 极性反转
3. AdverbHandler      — 程度副词检测 + 强度加权
4. PrefixSuffixHandler — 前缀/后缀修饰处理

处理管道:
  preprocess(text) → AnnotatedText
     → word_boundaries  (多字词组占位)
     → negation_regions (否定词作用范围)
     → adverb_markers   (程度副词修饰标记)
     → prefix_markers   (前后缀修饰标记)
"""
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field


# ============================================================
# 数据结构
# ============================================================

@dataclass
class WordBoundary:
    """多字词组的匹配边界（用于跳过已占用的字符位置）"""
    start: int
    end: int
    word: str
    length: int

    def overlaps(self, other_start: int, other_end: int) -> bool:
        return not (self.end <= other_start or self.start >= other_end)


@dataclass
class NegationMarker:
    """否定词标记"""
    position: int        # 否定词在原文中的位置
    word: str            # 否定词本身
    scope_end: int       # 否定作用范围的结束位置


@dataclass
class AdverbMarker:
    """程度副词标记"""
    position: int
    word: str
    multiplier: float    # 强度放大/缩小系数


@dataclass
class PrefixMarker:
    """前缀修饰标记"""
    position: int
    prefix: str          # 前缀词
    affected_word: str   # 被修饰的词
    override_score: Optional[int] = None  # 如果有特例规则，覆盖分数


@dataclass
class AnnotatedText:
    """预处理后的标注文本"""
    raw: str                             # 原始文本
    word_boundaries: List[WordBoundary] = field(default_factory=list)
    exception_boundaries: List[WordBoundary] = field(default_factory=list)  # 否定特例边界
    negation_markers: List[NegationMarker] = field(default_factory=list)
    adverb_markers: List[AdverbMarker] = field(default_factory=list)
    prefix_markers: List[PrefixMarker] = field(default_factory=list)

    def is_position_blocked(self, pos: int, length: int = 1) -> bool:
        """判断某个位置是否已被多字词组占用（含特例边界）"""
        all_boundaries = list(self.word_boundaries) + list(self.exception_boundaries)
        for b in all_boundaries:
            if b.start <= pos < b.end:
                return True
            if b.overlaps(pos, pos + length):
                return True
        return False

    def is_in_negation_scope(self, pos: int) -> Tuple[bool, str]:
        """判断某个位置是否在否定词作用范围内"""
        for m in self.negation_markers:
            if m.position < pos < m.scope_end:
                return True, m.word
        return False, ""

    def get_adverb_multiplier(self, pos: int) -> float:
        """获取某个位置前面的程度副词系数"""
        best = 1.0
        for m in self.adverb_markers:
            # 副词在目标词之前且距离较近（10 字以内）
            if 0 < pos - m.position <= 10:
                if abs(m.multiplier) > abs(best):
                    best = m.multiplier
        return best


# ============================================================
# 各处理器
# ============================================================

class NegationHandler:
    """
    否定词处理器

    规则：
    - 否定词后 1-3 个词的极性反转
    - 特例表：某些 "否定词+词根" 组合不是否定（如"不俗"=脱俗≠否定俗）
    """

    # 否定词列表（按长度降序，长词优先匹配）
    NEGATION_WORDS = sorted([
        "不可", "不必", "未曾", "未尝", "并非",
        "不", "无", "未", "莫", "勿", "休", "非", "弗", "毋", "别",
    ], key=len, reverse=True)

    # 特例：这些 "否定词+词根" 组合不是真正的否定
    # fmt: off
    NEGATION_EXCEPTIONS = {
        "不俗",     # 脱俗，积极
        "不凡",     # 不平凡，积极
        "不已",     # 不止，中性
        "不己",     # 不止，中性
        "不禁",     # 忍不住，中性/积极
        "不穷",     # 不穷尽，中性
        "不羁",     # 不受约束（书画中偏积极）
        "不群",     # 卓尔不群，积极
        "不讳",     # 不避讳，中性
        "不休",     # 不止，中性
        "不倦",     # 不厌倦，积极
        "不厌",     # 不厌倦，积极/中性
        "不暇",     # 来不及，中性
        "不忿",     # 不服气，偏消极但非否定
        "不才",     # 自谦，中性
        "不如",     # 比较，中性
        "不知",     # 认知动词，中性
        "不见",     # 看不见/不被看见，中性
        "无为",     # 道家概念，中性
        "无聊",     # 中性/偏消极
        "无言",     # 无语，中性
        "无穷",     # 无穷尽，中性/积极
        "无边",     # 无边际，中性
        "无畏",     # 无畏，积极
        "无愧",     # 无愧，积极
        "无限",     # 无限，中性/积极
        "无双",     # 无双，积极
        "无敌",     # 无敌，积极
        "无比",     # 无比，程度副词
        "无异",     # 无异于，中性
        "无形",     # 无形，中性
        "无心",     # 无心，中性
        "无意",     # 无意，中性
        "无论",     # 无论，中性
        "无比",     # 无比，程度
        "无恙",     # 无恙，积极
        "无妨",     # 无妨，中性
        "无奈",     # 无奈，偏消极
        "无赖",     # 无奈/撒泼，偏消极
        "无聊",     # 无聊，偏消极
        "勿忘",     # 勿忘，中性/积极
        "莫如",     # 不如，中性
        "莫非",     # 莫非，中性
        "莫不",     # 双重否定=肯定
        "莫逆",     # 莫逆之交，积极
        "莫愁",     # 劝慰，中性
        "莫笑",     # 莫笑，自嘲/劝诫，中性
        "莫问",     # 莫问，中性
        "莫言",     # 莫言，中性
        "莫怪",     # 莫怪，轻微消极
        "非但",     # 不但，中性
        "非常",     # 程度副词
        "非命",     # 非命，消极
        "未曾有",   # 未曾有，中性
        "未始",     # 未尝，中性
        "未几",     # 不久，中性
        "未必",     # 未必，中性
        "未知",     # 未知，中性
        "未定",     # 未定，中性
        "未了",     # 未了，中性/偏消极
        "未可知",   # 未可知，中性
        "未尝",     # 未尝，中性
        "未敢",     # 未敢，中性
        "未能",     # 未能，中性
        "未竟",     # 未竟，偏消极
    }
    # fmt: on

    def process(self, text: str, word_boundaries: List[WordBoundary]) -> List[NegationMarker]:
        markers = []
        i = 0
        while i < len(text):
            # 如果当前位置已被多字词组占用，跳过
            if any(b.start <= i < b.end for b in word_boundaries):
                i += 1
                continue

            matched = False
            for neg_word in self.NEGATION_WORDS:
                if text[i:].startswith(neg_word):
                    # 检查是否是特例
                    exception_found = False
                    for exc in self.NEGATION_EXCEPTIONS:
                        if text[i:].startswith(exc) and len(exc) >= len(neg_word):
                            exception_found = True
                            break

                    if not exception_found:
                        # 否定作用范围：往后 5 个字符（覆盖后续 1-2 个词）
                        scope_end = min(i + len(neg_word) + 5, len(text))
                        markers.append(NegationMarker(
                            position=i,
                            word=neg_word,
                            scope_end=scope_end,
                        ))
                        i += len(neg_word)
                        matched = True
                        break

            if not matched:
                i += 1

        return markers

    def get_exception_boundaries(self, text: str) -> List[WordBoundary]:
        """获取否定特例的字符边界（这些位置不应被单字匹配）"""
        boundaries = []
        for exc in sorted(self.NEGATION_EXCEPTIONS, key=len, reverse=True):
            pos = text.find(exc)
            if pos >= 0:
                # 检查是否与已有边界重叠
                if not any(b.overlaps(pos, pos + len(exc)) for b in boundaries):
                    boundaries.append(WordBoundary(
                        start=pos,
                        end=pos + len(exc),
                        word=exc,
                        length=len(exc),
                    ))
        return boundaries


class AdverbHandler:
    """
    程度副词处理器

    规则：
    - 程度副词修饰后面的形容词/动词
    - 放大或缩小情感强度
    """

    # (副词, 系数)
    ADVERBS = [
        # 极度（高强度放大）
        ("最", 2.0),
        ("至", 2.0),
        ("极", 2.0),
        ("极其", 2.5),
        ("极为", 2.5),
        ("绝", 2.0),
        ("绝顶", 2.5),
        ("非常", 2.0),
        ("十分", 2.0),
        ("万分", 2.0),
        ("何等", 2.0),
        ("异常", 1.8),
        ("格外", 1.8),
        ("过于", 1.5),
        ("过分", 1.5),
        ("太", 1.8),
        ("尤", 1.5),
        ("尤其", 1.5),
        ("颇", 1.3),
        ("甚", 1.5),
        ("深", 1.5),
        ("深深", 1.8),
        ("不胜", 1.5),
        ("何其", 1.5),
        # 中等
        ("更", 1.2),
        ("更加", 1.3),
        ("愈发", 1.3),
        ("越", 1.2),
        ("越发", 1.3),
        ("还", 1.1),
        ("较", 1.1),
        ("较为", 1.1),
        # 轻微（强度缩小）
        ("略", 0.5),
        ("略微", 0.5),
        ("稍", 0.5),
        ("稍微", 0.5),
        ("稍稍", 0.5),
        ("微", 0.3),
        ("微微", 0.3),
        ("有些", 0.6),
        ("有点", 0.6),
        ("一点儿", 0.4),
        ("几分", 0.5),
        ("些许", 0.4),
        ("聊", 0.5),
        ("姑", 0.5),
        ("尚", 0.7),
    ]

    def process(self, text: str, word_boundaries: List[WordBoundary]) -> List[AdverbMarker]:
        markers = []
        i = 0
        while i < len(text):
            if any(b.start <= i < b.end for b in word_boundaries):
                i += 1
                continue

            matched = False
            for adv_word, mult in self.ADVERBS:
                if text[i:].startswith(adv_word):
                    # 避免过长匹配干扰（如"微微"不应匹配"微笑"的"微"）
                    # 检查后面是否是情感词（空格或汉字）
                    next_char = text[i + len(adv_word)] if i + len(adv_word) < len(text) else ''
                    if next_char and '一' <= next_char <= '鿿':
                        markers.append(AdverbMarker(
                            position=i,
                            word=adv_word,
                            multiplier=mult,
                        ))
                        i += len(adv_word)
                        matched = True
                        break

            if not matched:
                i += 1

        return markers


class PrefixSuffixHandler:
    """
    前缀/后缀修饰处理器

    规则：
    - 某些前缀 + 词根的组合需要特殊处理
    - 通过特例表覆盖
    """

    # 常见前缀
    COMMON_PREFIXES = ["可", "堪", "宜", "足", "莫", "相", "见", "被", "所"]

    # 特例覆盖表：前缀+词根 → 覆盖分数（None 表示由通用规则处理）
    # fmt: off
    PREFIX_OVERRIDES = {
        # 可X — "可"通常是"值得"之意，放大情感
        "可悲": -3,      # 比"悲"(-3) 更强烈 → 还是 -3
        "可怜": -2,      # 可怜 → 偏消极
        "可笑": -2,      # 可笑 → 偏消极
        "可喜": 2,       # 可喜 → 积极
        "可叹": -2,      # 可叹 → 偏消极
        "可憎": -3,      # 可憎 → 消极
        "可爱": 2,       # 可爱 → 积极
        "可敬": 2,       # 可敬 → 积极
        "可贺": 2,       # 可贺 → 积极
        "可耻": -3,      # 可耻 → 消极
        "可恶": -3,      # 可恶 → 消极
        "可怜见": -2,    # 可怜见 → 偏消极
        "可怪": -1,      # 可怪 → 轻微消极
        "可畏": -1,      # 可畏 → 轻微消极
        "可惊": 1,       # 可惊 → 轻微积极（惊叹）
        "可疑": -1,      # 可疑 → 轻微消极
        "可忧": -2,      # 可忧 → 偏消极

        # 堪X — "堪" = 足以、能够，放大
        "堪叹": -2,
        "堪笑": -1,
        "堪怜": -2,
        "堪悲": -3,

        # 莫X — "莫"通常是否定前缀
        "莫笑": -2,      # 莫笑 → 自嘲，偏消极
        "莫愁": 0,       # 莫愁 → 劝慰，中性
        "莫怪": -1,      # 莫怪 → 轻微消极
        "莫问": 0,       # 莫问 → 中性
        "莫说": 0,       # 莫说 → 中性
        "莫言": 0,       # 莫言 → 中性

        # 相X — "相"是互相，情感取决于词根
        "相思": -1,      # 相思 → 轻微消极
        "相忆": -1,      # 相忆 → 轻微消极
        "相见": 1,       # 相见 → 轻微积极
        "相知": 2,       # 相知 → 积极
        "相惜": 1,       # 相惜 → 轻微积极
        "相爱": 2,       # 相爱 → 积极
        "相助": 1,       # 相助 → 轻微积极
        "相伴": 1,       # 相伴 → 轻微积极
        "相忘": -1,      # 相忘 → 轻微消极
    }
    # fmt: on

    def process(self, text: str, word_boundaries: List[WordBoundary]) -> List[PrefixMarker]:
        markers = []
        i = 0
        while i < len(text):
            if any(b.start <= i < b.end for b in word_boundaries):
                i += 1
                continue

            for prefix in self.COMMON_PREFIXES:
                if not text[i:].startswith(prefix):
                    continue

                # 看前缀后跟的 2 个字是否是已知情感词
                matched_override = False
                for lookahead in range(2, 5):
                    if i + len(prefix) + lookahead > len(text):
                        break
                    candidate = text[i:i + len(prefix) + lookahead]

                    if candidate in self.PREFIX_OVERRIDES:
                        markers.append(PrefixMarker(
                            position=i,
                            prefix=prefix,
                            affected_word=candidate[len(prefix):],
                            override_score=self.PREFIX_OVERRIDES[candidate],
                        ))
                        i += len(candidate)
                        matched_override = True
                        break

                if not matched_override:
                    # 未匹配到特例（含文本过短导致 lookahead 越界的情况）
                    i += 1
                break
            else:
                i += 1

        return markers


class MultiWordPriority:
    """
    多字词组优先处理器

    规则：
    - 用词库中最长的词组优先匹配
    - 匹配到的位置标记为占用，后续单字匹配跳过这些位置
    """

    def __init__(self, lexicon_words: set = None):
        self.lexicon_words = lexicon_words or set()

    def set_lexicon(self, words: set):
        self.lexicon_words = words

    def process(self, text: str) -> List[WordBoundary]:
        boundaries = []

        if not self.lexicon_words:
            return boundaries

        # 按长度降序排列
        sorted_words = sorted(self.lexicon_words, key=len, reverse=True)

        for word in sorted_words:
            if len(word) < 2:
                continue  # 只处理多字词

            search_from = 0
            while True:
                pos = text.find(word, search_from)
                if pos < 0:
                    break

                # 检查是否与已有边界重叠
                if not any(b.overlaps(pos, pos + len(word)) for b in boundaries):
                    boundaries.append(WordBoundary(
                        start=pos,
                        end=pos + len(word),
                        word=word,
                        length=len(word),
                    ))
                    search_from = pos + len(word)
                else:
                    search_from = pos + 1

        return boundaries


# ============================================================
# 主入口
# ============================================================

class EmotionTextPreprocessor:
    """
    情感文本预处理器

    链式调用各处理器，输出标注文本供词库匹配引擎使用。
    """

    def __init__(self, lexicon_words: set = None):
        self.negation = NegationHandler()
        self.adverb = AdverbHandler()
        self.prefix = PrefixSuffixHandler()
        self.multi_word = MultiWordPriority(lexicon_words)

    def set_lexicon(self, words: set):
        self.multi_word.set_lexicon(words)

    def preprocess(self, text: str) -> AnnotatedText:
        """主入口：对文本进行全链路预处理"""
        result = AnnotatedText(raw=text)

        if not text:
            return result

        # 1. 多字词组优先匹配
        result.word_boundaries = self.multi_word.process(text)

        # 2. 否定词检测（先获取特例边界，再做否定标记）
        result.exception_boundaries = self.negation.get_exception_boundaries(text)
        result.negation_markers = self.negation.process(text, result.word_boundaries)

        # 3. 程度副词检测
        result.adverb_markers = self.adverb.process(text, result.word_boundaries)

        # 4. 前缀/后缀修饰检测
        result.prefix_markers = self.prefix.process(text, result.word_boundaries)

        return result

    def get_blocked_positions(self, annotated: AnnotatedText) -> set:
        """获取所有被多字词组或特例占用的字符位置"""
        blocked = set()
        for b in list(annotated.word_boundaries) + list(annotated.exception_boundaries):
            for p in range(b.start, b.end):
                blocked.add(p)
        return blocked


# 全局单例
_preprocessor: Optional[EmotionTextPreprocessor] = None


def get_preprocessor(lexicon_words: set = None) -> EmotionTextPreprocessor:
    """获取全局预处理器实例"""
    global _preprocessor
    if _preprocessor is None:
        _preprocessor = EmotionTextPreprocessor(lexicon_words)
    return _preprocessor
