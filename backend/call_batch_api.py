import requests
import json
import time

# Call the batch analysis API
url = "http://localhost:8001/api/v1/content-analysis/batch"
params = {
    "artist": "李鱓",
    "force_reanalyze": "true",
    "use_llm": "true"
}

print(f"Calling API: {url}")
print(f"Params: {params}")
start = time.time()

try:
    resp = requests.post(url, params=params, timeout=600)
    elapsed = time.time() - start
    print(f"\nResponse status: {resp.status_code}")
    print(f"Time elapsed: {elapsed:.1f}s")
    print(f"Response: {resp.text[:2000]}")
except Exception as e:
    print(f"Error: {e}")