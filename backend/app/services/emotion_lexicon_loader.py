"""
情感词典加载器
────────────────────────────────────────
加载 emotion_lexicon_v3.json（优先）或 emotion_lexicon.json 并提供查询接口
"""

import json
import os
from typing import Dict, Optional, Set


class EmotionLexicon:
    """情感词典"""

    def __init__(self, lexicon_path: str = None):
        if lexicon_path is None:
            # 优先加载 v3
            v3_path = os.path.join(os.path.dirname(__file__), "emotion_lexicon_v3.json")
            v2_path = os.path.join(os.path.dirname(__file__), "emotion_lexicon.json")
            lexicon_path = v3_path if os.path.exists(v3_path) else v2_path

        self.entries: Dict[str, Dict] = {}
        self.version: str = ""
        self.generated_at: str = ""

        if os.path.exists(lexicon_path):
            with open(lexicon_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.entries = data.get("entries", {})
                self.version = data.get("version", "")
                self.generated_at = data.get("generated_at", "")

    def get_score(self, word: str) -> Optional[int]:
        """获取词语的情感分数"""
        entry = self.entries.get(word)
        if entry:
            return entry.get("score")
        return None

    def get_category(self, word: str) -> Optional[str]:
        """获取词语的情感分类"""
        entry = self.entries.get(word)
        if entry:
            return entry.get("category")
        return None

    def has_word(self, word: str) -> bool:
        """检查词语是否在词典中"""
        return word in self.entries

    def get_all_words(self) -> list:
        """获取所有词语"""
        return list(self.entries.keys())

    def get_multi_char_words(self) -> Set[str]:
        """获取所有多字词组（长度 >= 2），用于多字优先匹配"""
        return {w for w in self.entries if len(w) >= 2}

    def get_stats(self) -> Dict:
        """获取词典统计信息"""
        categories = {}
        for entry in self.entries.values():
            cat = entry.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1

        return {
            "total_words": len(self.entries),
            "version": self.version,
            "generated_at": self.generated_at,
            "categories": categories,
        }


# 全局单例
_lexicon: Optional[EmotionLexicon] = None


def get_lexicon() -> EmotionLexicon:
    """获取全局词典实例"""
    global _lexicon
    if _lexicon is None:
        _lexicon = EmotionLexicon()
    return _lexicon
