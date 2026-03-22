import httpx
import json
import sys
import os

SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
SILICONFLOW_API_URL = "https://api.siliconflow.cn/v1/chat/completions"
MODEL_NAME = "Pro/moonshotai/Kimi-K2.5"

def log(msg):
    with open("test_log.txt", "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def test_api():
    log("Starting test...")
    log(f"Model: {MODEL_NAME}")

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": "Say hello in JSON format: {\"greeting\": \"hello\"}"
            }
        ],
        "stream": False,
        "max_tokens": 100
    }

    headers = {
        "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
        "Content-Type": "application/json"
    }

    log("Sending request...")

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(SILICONFLOW_API_URL, headers=headers, json=payload)
            log(f"Status: {response.status_code}")

            result = response.json()
            log(f"Response: {json.dumps(result, ensure_ascii=False, indent=2)}")

            if "choices" in result:
                content = result["choices"][0]["message"]["content"]
                log(f"Content: {content}")
    except Exception as e:
        log(f"Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc(file=open("test_log.txt", "a", encoding="utf-8"))

if __name__ == "__main__":
    test_api()
