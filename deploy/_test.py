import urllib.request, ssl, json, socket

ip = socket.gethostbyname("124.223.17.29")
ctx = ssl.create_default_context()
ctx.check_hostname = False

try:
    # Direct IP test (bypasses DNS)
    sock = socket.create_connection(("124.223.17.29", 443), timeout=10)
    ssock = ctx.wrap_socket(sock)
    ssock.sendall(b"GET /api/v1/composition/history?limit=2 HTTP/1.1\r\nHost: xcx.zhouhouhan.com\r\nConnection: close\r\n\r\n")
    resp = b""
    while True:
        chunk = ssock.recv(4096)
        if not chunk:
            break
        resp += chunk
    ssock.close()
    body = resp.split(b"\r\n\r\n", 1)[-1]
    data = json.loads(body)
    items = data.get("items", [])
    print(f"✅ API OK - {len(items)} history items")
    for item in items[:2]:
        print(f"   {item['task_id'][:12]}... status={item['status']} created={item['created_at'][:16]}")
except Exception as e:
    print(f"❌ FAIL: {e}")
