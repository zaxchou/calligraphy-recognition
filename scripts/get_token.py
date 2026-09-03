# 仅限本地开发使用：依赖 WECHAT_MOCK_MODE=true 的本地后端（localhost:3000）。
# 生产环境 mock 已关闭（2026-09-03 安全整改），此脚本对生产无效。
import json, urllib.request
body = json.dumps({"code": "mock_zax"}).encode()
req = urllib.request.Request(
    "http://localhost:3000/api/v1/auth/wechat-login",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
)
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())
with open("scripts/.token.txt", "w") as f:
    f.write(data["token"])
print(f"Token saved. role={data['role']}, id={data['user_id']}")
