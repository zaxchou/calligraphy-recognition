"""测试v3 prompt是否正常工作"""
import asyncio
import sys
sys.path.insert(0, '.')
from app.services.inscription_content_analyzer import llm_theme_classification_v3, llm_sentiment_analysis_v3

async def test():
    # 测试用例 - 包含真正的讽喻类内容
    test_cases = [
        ("增其寿也。增其福也。", "世俗祈愿"),
        ("问年得似松枝老，富贵还如藤蔓缠。更写兰花芝草秀，卜君多寿子孙贤。", "世俗祈愿"),
        ("世味年来辣更长，舆隶面前强项。", "讽喻类"),
        ("官吏声声催租急，租吏捉人太凶横。", "讽喻类"),
        ("夺朱非正色，异样也芬芳。", "讽喻类"),
        ("乾三卦不上书，人民政府有何妨。", "讽喻类"),
        ("写意花鸟画，记录创作信息", "记录创作信息"),
        ("日日临池画水仙，欲向高人学笔意。", "记录创作信息+画理"),
    ]

    for text, expected in test_cases:
        print(f"\n输入: {text[:50]}...")
        print(f"期望: {expected}")
        themes = await llm_theme_classification_v3(text)
        sentiment = await llm_sentiment_analysis_v3(text)
        print(f"  主题: {themes}")
        print(f"  情感: {sentiment['polarity']}")

if __name__ == "__main__":
    asyncio.run(test())