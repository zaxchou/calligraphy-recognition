"""
分群规律库

存储和管理按画群分类的题跋/绘画规律。

规律格式：
每条规律是一个自然语言描述，LLM在分类时作为上下文注入。
规律按画群分类存储，互不干扰。

画群：
- dark_base:    暗底画
- light_base:   亮底画
- colorful:     彩色画
- monochrome:   单色画
- printed:      印刷品
- scanned:      扫描件
"""

import json
import os
from typing import Dict, List
from dataclasses import dataclass, asdict


RULE_LIBRARY_PATH = r"z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\backend\data\rule_library\group_rules.json"


# 初始规律库（基于李鱓作品特征的通用规律）
DEFAULT_RULES = {
    "dark_base": [
        "暗底画的题跋区域通常位于画面边缘，特别是右侧和顶部",
        "暗底画的墨迹对比度较高，文字笔画清晰",
        "暗底画的题跋面积占比通常较小（5%-20%），因为暗色背景会压缩文字区域",
        "暗底画的印章通常为红色或朱砂色，在暗底上对比明显",
        "暗底画的绘画区域通常占据画面中心，面积较大",
    ],
    "light_base": [
        "亮底画（宣纸色）的题跋区域分布较广，可能在任何位置",
        "亮底画的墨迹密度中等，笔画与底色对比适中",
        "亮底画的题跋面积占比通常为8%-25%",
        "亮底画的印章颜色多样，红色最常见",
        "亮底画的留白区域明显，绘画与题跋边界清晰",
    ],
    "colorful": [
        "彩色画的题跋通常避开设色浓重的区域，位于色彩较淡的边缘",
        "彩色画的题跋面积占比通常较小（5%-15%），因为绘画主体占面积大",
        "彩色画的印章可能与画面色彩形成对比",
        "彩色画的绘画区域有明显的色彩特征，饱和度较高",
        "彩色画的留白区域可能较少，画面较满",
    ],
    "monochrome": [
        "单色画（纯水墨）的题跋与绘画都依赖墨色深浅区分",
        "单色画的题跋通常有明显的行列结构",
        "单色画的题跋面积占比可能较大（10%-30%），因为没有设色挤占空间",
        "单色画的印章是画面中唯一的非黑色元素，非常显眼",
        "单色画的留白区域通常较大，有\"计白当黑\"的特点",
    ],
    "printed": [
        "印刷品的纹理均匀，边缘锐利规则",
        "印刷品的题跋如果是印刷体，笔画粗细均匀；如果是手写题跋，可能有不同的纹理特征",
        "印刷品的颜色分布较均匀，没有手绘的随机笔触",
    ],
    "scanned": [
        "扫描件可能有扫描条纹或噪点，纹理复杂度较高",
        "扫描件的颜色可能不够准确，有偏色现象",
        "扫描件的题跋和绘画边界可能因扫描质量而模糊",
    ],
    "global": [
        "题跋区域通常有行列结构（水平或垂直排列的文字）",
        "题跋区域的高宽比通常较大（细长条）或接近方形（短款）",
        "题跋区域的纹理密度高（笔画边缘多）",
        "绘画区域通常面积较大，占据画面主体",
        "绘画区域的形状不规则，边缘柔和",
        "留白区域通常面积最大，分布均匀",
        "印章区域通常面积小（<1%），形状近方形，颜色饱和度高",
    ],
}


@dataclass
class RuleLibrary:
    """规律库"""
    rules: Dict[str, List[str]]  # group -> list of rules
    version: str = "1.0"
    
    def get_rules_for_group(self, group: str) -> List[str]:
        """获取指定画群的规律"""
        group_rules = self.rules.get(group, [])
        global_rules = self.rules.get("global", [])
        return global_rules + group_rules
    
    def add_rule(self, group: str, rule: str):
        """添加新规律"""
        if group not in self.rules:
            self.rules[group] = []
        self.rules[group].append(rule)
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "RuleLibrary":
        return cls(rules=data.get("rules", {}), version=data.get("version", "1.0"))


def load_rule_library(path: str = RULE_LIBRARY_PATH) -> RuleLibrary:
    """加载规律库"""
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return RuleLibrary.from_dict(data)
    return RuleLibrary(rules=DEFAULT_RULES.copy())


def save_rule_library(library: RuleLibrary, path: str = RULE_LIBRARY_PATH):
    """保存规律库"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(library.to_dict(), f, ensure_ascii=False, indent=2)
