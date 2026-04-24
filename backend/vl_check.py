import base64, os, httpx, json, sys
from dotenv import load_dotenv
load_dotenv()
api_key = os.environ["QWEN_API_KEY"]

def call_qwen_vl(image_path, prompt):
    with open(image_path, 'rb') as f:
        img_b64 = base64.b64encode(f.read()).decode()
    payload = {
        'model': 'qwen-vl-plus',
        'messages': [{'role': 'user', 'content': [
            {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{img_b64}'}},
            {'type': 'text', 'text': prompt}
        ]}]
    }
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    resp = httpx.post(
        'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
        headers=headers, json=payload, timeout=90.0
    )
    resp.raise_for_status()
    return resp.json()['choices'][0]['message']['content']

if __name__ == '__main__':
    page = sys.argv[1]  # e.g. r'E:\...\第214页-214.JPG'
    prompt = (
        '这是一页关于清代李鱓（lǐshàn）书画的古书扫描页。请详细描述：'
        '1. 这一页上有几幅作品？每幅作品的名称/主题是什么？'
        '2. 每幅作品上的题款（落款）内容是什么？'
        '3. 是否有年份/干支纪年（如"乾隆十年"）？'
        '请尽量列出所有文字。'
    )
    result = call_qwen_vl(page, prompt)
    print(result)