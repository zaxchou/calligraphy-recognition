import subprocess, os, zipfile

PEM = r"z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\cali_cloud_20260503.pem"
HOST = "ubuntu@124.223.17.29"
DATA_DIR = r"z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\backend\data"

with open(PEM) as f: key = f.read()
tk = os.path.join(os.environ["TEMP"], "cali.pem")
with open(tk, "w") as f: f.write(key.strip() + "\n")

# Step 1: Create data zip (excluding large cached/temp dirs)
print("=== Compressing data ===")
zpath = os.path.join(os.environ["TEMP"], "data_upload.zip")
with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(DATA_DIR):
        # Skip caches & temp dirs
        dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git', '.image_index', 'thumbnails', 'tubi_debug')]
        for f in files:
            fp = os.path.join(root, f)
            arc = os.path.relpath(fp, r"z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\backend")
            try:
                zf.write(fp, arc)
            except:
                pass
size = os.path.getsize(zpath)
print(f"Zip: {size/1024/1024:.1f} MB")

# Step 2: Upload
print("=== Uploading ===")
p = subprocess.Popen(["scp", "-o", "StrictHostKeyChecking=no", "-i", tk, zpath, f"{HOST}:/tmp/data_upload.zip"])
p.communicate(timeout=300)
print("Upload done")

# Step 3: Stop backend, unzip into /opt/calligraphy-recognition/backend, restart
cmds = [
    "echo '=== Backing up container data ==='",
    "sudo docker exec deploy-backend-1 tar czf /tmp/data_backup.tar.gz -C / app/data 2>/dev/null || true",
    "echo '=== Unzipping data ==='",
    "sudo rm -rf /opt/calligraphy-recognition/backend/data_old 2>/dev/null; sudo mv /opt/calligraphy-recognition/backend/data /opt/calligraphy-recognition/backend/data_old 2>/dev/null; true",
    "sudo mkdir -p /opt/calligraphy-recognition/backend/data",
    "sudo unzip -o /tmp/data_upload.zip -d /opt/calligraphy-recognition/backend/ 2>&1 | tail -5",
    "sudo chown -R ubuntu:ubuntu /opt/calligraphy-recognition/backend/data/",
    "echo '=== Restarting backend ==='",
    "cd /opt/calligraphy-recognition/deploy && sudo docker compose up -d --build backend 2>&1 | tail -5",
    "sleep 5",
    "sudo docker logs deploy-backend-1 --tail 5 2>&1",
    "curl -sk -o /dev/null -w '%{http_code}' https://localhost/api/v1/composition/history?limit=1 && echo ' API OK'",
]
p = subprocess.Popen(["ssh", "-o", "StrictHostKeyChecking=no", "-i", tk, HOST, " && ".join(cmds)])
out, _ = p.communicate(timeout=600)
print(out.decode() if out else "no output")

# Cleanup
os.unlink(zpath)
os.unlink(tk)
