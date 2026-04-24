"""
实时学习器

每次用户进行手动标注后，自动对比自动分析结果和手动标注结果，
提取差异规律，更新规律库。
"""

import json
import os
from typing import Dict, List, Optional
from datetime import datetime

from app.tubi.llm_classifier.rule_library import load_rule_library, save_rule_library


LEARN_LOG_PATH = r"z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\backend\data\rule_library\learn_log.jsonl"


def learn_from_manual_annotation(
    image_id: str,
    auto_regions: Dict,
    manual_regions: Dict,
    group_name: str,
    image_stats: Dict,
) -> Optional[str]:
    """
    从手动标注中学习
    
    参数：
        image_id: 图片ID
        auto_regions: 自动分析结果
        manual_regions: 手动标注结果
        group_name: 画群名称
        image_stats: 图像统计特征
    
    返回：
        学习到的规律字符串，或None
    """
    try:
        # 对比自动结果和手动结果
        auto_insc = auto_regions.get("inscription_regions", [])
        manual_insc = manual_regions.get("inscription_regions", [])
        
        auto_paint = auto_regions.get("painting_regions", [])
        manual_paint = manual_regions.get("painting_regions", [])
        
        # 计算差异
        insc_diff = abs(len(auto_insc) - len(manual_insc))
        paint_diff = abs(len(auto_paint) - len(manual_paint))
        
        if insc_diff == 0 and paint_diff == 0:
            return None  # 没有差异，无需学习
        
        # 生成学习到的规律
        rule = None
        
        if insc_diff > 0:
            # 题跋数量差异
            if len(auto_insc) < len(manual_insc):
                rule = f"{group_name}画作中，题跋区域可能被遗漏，需要更仔细地检测边缘小字"
            else:
                rule = f"{group_name}画作中，容易将绘画纹理误判为题跋，需要区分笔画的\"书写性\"和\"绘画性\""
        
        if paint_diff > 0:
            # 绘画区域差异
            if len(auto_paint) < len(manual_paint):
                if rule:
                    rule += "；绘画区域检测可能不完整，特别是对于淡墨区域"
                else:
                    rule = f"{group_name}画作中，绘画区域检测可能不完整，特别是对于淡墨区域"
        
        if rule:
            # 加载规律库并添加新规律
            library = load_rule_library()
            library.add_rule(group_name, rule)
            save_rule_library(library)
            
            # 记录学习日志
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "image_id": image_id,
                "group": group_name,
                "rule": rule,
                "auto_insc_count": len(auto_insc),
                "manual_insc_count": len(manual_insc),
                "auto_paint_count": len(auto_paint),
                "manual_paint_count": len(manual_paint),
                "image_stats": image_stats,
            }
            
            os.makedirs(os.path.dirname(LEARN_LOG_PATH), exist_ok=True)
            with open(LEARN_LOG_PATH, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
            
            return rule
        
        return None
    except Exception as e:
        print(f"ERROR: Realtime learning failed: {e}")
        return None
