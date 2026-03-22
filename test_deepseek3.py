"""测试 DeepSeek API - 使用特征描述"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

import json
import requests

# 测试 DeepSeek API
def test_deepseek_api():
    print("测试 DeepSeek API...")
    
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    
    features_description = """图像尺寸: 128x128
笔画密度: 15.23%
轮廓数量: 3
九宫格区域笔画密度:
  上左: 5.00%
  上中: 80.00%
  上右: 5.00%
  中左: 10.00%
  中中: 20.00%
  中右: 10.00%
  下左: 60.00%
  下中: 70.00%
  下右: 60.00%
主要笔画方向: 水平, 左上-右下, 右上-左下
重心位置: (0.50, 0.55)
重心偏移: 居中, 偏下"""
    
    candidates = ["大", "唐", "三", "文"]
    candidate_str = ", ".join(candidates)
    
    prompt = f"""你是一位书法字体识别专家。请根据以下特征描述判断这是哪个汉字。

候选汉字：{candidate_str}

特征描述：
{features_description}

请仔细分析这些特征，然后：
1. 判断这是哪个汉字（必须从候选字中选择）
2. 给出置信度（0-100%）
3. 简要说明判断理由

请以 JSON 格式返回结果：
{{"character": "识别的汉字", "confidence": 95.5, "reason": "判断理由"}}"""
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.1,
        "max_tokens": 500
    }
    
    print("发送请求...")
    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            ai_response = result['choices'][0]['message']['content']
            print(f"AI 响应:\n{ai_response}")
            
            # 解析 JSON
            ai_response = ai_response.strip()
            if ai_response.startswith('```json'):
                ai_response = ai_response[7:]
            if ai_response.startswith('```'):
                ai_response = ai_response[3:]
            if ai_response.endswith('```'):
                ai_response = ai_response[:-3]
            ai_response = ai_response.strip()
            
            recognition_result = json.loads(ai_response)
            print(f"\n解析结果:")
            print(f"  字符: {recognition_result.get('character')}")
            print(f"  置信度: {recognition_result.get('confidence')}")
            print(f"  理由: {recognition_result.get('reason')}")
        else:
            print(f"错误: {response.text}")
    except Exception as e:
        print(f"异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_deepseek_api()
