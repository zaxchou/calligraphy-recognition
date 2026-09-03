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
