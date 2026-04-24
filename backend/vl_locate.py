"""在参考书某一页上定位特定画作"""
import sys, base64, os, json, httpx
from dotenv import load_dotenv
load_dotenv()

def qwen_vl_v2(img_path, prompt):
    with open(img_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()
    payload = {
        "model": "qwen-vl-plus",
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
            {"type": "text", "text": prompt}
        ]}],
        "max_tokens": 300
    }
    with httpx.Client(timeout=60) as client:
        r = client.post(
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            headers={"Authorization": f"Bearer {os.environ['QWEN_API_KEY']}", "Content-Type": "application/json"},
            json=payload
        )
    print("Status:", r.status_code, file=sys.stderr)
    print("Response:", r.text[:500], file=sys.stderr)
    return r.json()["choices"][0]["message"]["content"]

page = sys.argv[1]
artwork = sys.argv[2] if len(sys.argv) > 2 else ""

prompt = f"""这是一本中国画册的一页扫描图（完整页面，含多幅作品及其说明文字）。

请仔细看这幅页面：
1. 这一页包含几幅画？每幅画的名称是什么？（看页面上的文字标签，不是看文件名校猜）
2. 找一福名称为"{artwork}"的画，如果找到了，描述它在页面中的位置（左/右/上/下），并描述该画的画面内容
3. 如果没找到名称完全一致的，列出这一页所有画作的名称供对比

请用中文回答，尽量列出页面上的所有文字信息。"""

result = qwen_vl_v2(page, prompt)
print(result)