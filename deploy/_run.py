import subprocess, os

PEM = r"z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\cali_cloud_20260503.pem"
HOST = "ubuntu@124.223.17.29"
with open(PEM) as f: key = f.read()
tk = os.path.join(os.environ["TEMP"], "cali.pem")
with open(tk, "w") as f: f.write(key.strip() + "\n")

# Check cert exists
p = subprocess.Popen(["ssh", "-o", "StrictHostKeyChecking=no", "-i", tk, HOST,
    "sudo ls /etc/letsencrypt/live/xcx.zhouhouhan.com/"])
out, _ = p.communicate(timeout=10)
print("Cert:", out.decode().strip() if out else "missing")

# Check current nginx config
p = subprocess.Popen(["ssh", "-o", "StrictHostKeyChecking=no", "-i", tk, HOST,
    "cat /opt/calligraphy-recognition/deploy/nginx.conf"])
out, _ = p.communicate(timeout=10)
print("Nginx:", out.decode()[:300] if out else "missing")

# Write correct HTTPS config
nginx = """server {
    listen 80;
    server_name xcx.zhouhouhan.com;
    return 301 https://$host$request_uri;
}
server {
    listen 443 ssl;
    server_name xcx.zhouhouhan.com;
    ssl_certificate /etc/letsencrypt/live/xcx.zhouhouhan.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/xcx.zhouhouhan.com/privkey.pem;
    client_max_body_size 30M;
    location / {
        proxy_pass http://backend:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 180s;
    }
}
"""
# Write nginx.conf locally
with open(r"z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\deploy\nginx.conf", "w") as f:
    f.write(nginx)
# SCP
p = subprocess.Popen(["scp", "-o", "StrictHostKeyChecking=no", "-i", tk,
    r"z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\deploy\nginx.conf",
    f"{HOST}:/opt/calligraphy-recognition/deploy/nginx.conf"])
p.communicate(timeout=15)
print("nginx.conf uploaded")

# Restart nginx
p = subprocess.Popen(["ssh", "-o", "StrictHostKeyChecking=no", "-i", tk, HOST,
    "sudo docker compose -f /opt/calligraphy-recognition/deploy/docker-compose.yml restart nginx && sleep 3 && curl -sk -o /dev/null -w '%{http_code}' https://localhost/ && echo HTTPS_OK"])
out, _ = p.communicate(timeout=20)
print(out.decode() if out else "no output")

os.unlink(tk)
