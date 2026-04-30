import requests
import json

try:
    resp = requests.get('http://localhost:8001/api/v1/knowledge/tasks', timeout=5)
    print(f'后端状态: {resp.status_code}')
    tasks = resp.json()
    print(f'任务数量: {len(tasks)}')
    for t in tasks[:3]:
        tid = t['id'][:8]
        status = t['status']
        progress = t['progress']
        stage = t.get('stage', '无')
        print(f'  - ID: {tid}..., 状态: {status}, 进度: {progress}%, 阶段: {stage}')
except Exception as e:
    print(f'后端连接失败: {e}')
