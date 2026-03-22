import httpx
import base64
import json

SILICONFLOW_API_KEY = "sk-slysntfniiwizugtkyxcyokpkrnhwzuttfzosyxmwfannsdb"
SILICONFLOW_API_URL = "https://api.siliconflow.cn/v1/chat/completions"
MODEL_NAME = "Pro/moonshotai/Kimi-K2.5"

def log(msg):
    with open("test_log2.txt", "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def test_api():
    image_path = "data/uploads/lishan.jpg"

    try:
        with open(image_path, "rb") as f:
            pass
        log(f"Image found: {image_path}")
    except FileNotFoundError:
        log(f"Image not found: {image_path}")
        return

    with open(image_path, "rb") as f:
        base64_image = base64.b64encode(f.read()).decode("utf-8")

    log(f"Image base64 size: {len(base64_image)}")

    prompt = """你是一个专业的中国画艺术分析师。请分析这幅绘画作品，识别并标注以下三类区域：

1. 题跋区域（红色）：书法文字、款识、印章等文字内容区域
2. 绘画区域（绿色）：山水、花鸟、竹石等绘画主体内容
3. 留白区域（蓝色）：画面中无画无字的空白区域

请以JSON格式返回分析结果：
{
    "inscription_regions": [{"x1": 0.0, "y1": 0.0, "x2": 0.5, "y2": 0.2}],
    "painting_regions": [{"x1": 0.0, "y1": 0.2, "x2": 1.0, "y2": 1.0}],
    "blank_regions": [{"x1": 0.5, "y1": 0.0, "x2": 1.0, "y2": 0.2}],
    "analysis_note": "简要说明"
}

只返回JSON，不要有其他内容。"""

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        "stream": False,
        "max_tokens": 2048
    }

    headers = {
        "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
        "Content-Type": "application/json"
    }

    log(f"Testing with model: {MODEL_NAME}")
    log("Sending request with 600s timeout...")

    try:
        with httpx.Client(timeout=600.0) as client:
            response = client.post(SILICONFLOW_API_URL, headers=headers, json=payload)
            log(f"Status: {response.status_code}")

            result = response.json()

            if "choices" in result:
                content = result["choices"][0]["message"]["content"]
                log(f"\nAI Response:\n{content}")
            else:
                log(f"Full response: {json.dumps(result, ensure_ascii=False, indent=2)}")
    except Exception as e:
        log(f"Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc(file=open("test_log2.txt", "a", encoding="utf-8"))

if __name__ == "__main__":
    test_api()
