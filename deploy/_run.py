import subprocess, os

PEM = r"z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\cali_cloud_20260503.pem"
HOST = "ubuntu@124.223.17.29"
DEPLOY = r"z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\deploy"

def ssh_stream(cmd, timeout=1800):
    with open(PEM, "r") as f: key = f.read()
    tmp = os.path.join(os.environ["TEMP"], "cali.pem")
    with open(tmp, "w") as f: f.write(key.strip() + "\n")
    p = subprocess.Popen(
        ["ssh", "-o", "StrictHostKeyChecking=no", "-i", tmp, HOST, cmd],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
    try:
        while True:
            line = p.stdout.readline()
            if not line:
                break
            txt = line.decode("utf-8", errors="replace").rstrip()
            if txt:
                print(txt)
        p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        print("\n[TIMEOUT]")
    finally:
        os.unlink(tmp)
    print(f"\nEXIT={p.returncode}")

# Upload latest files
print("=== Uploading ===")
with open(PEM, "r") as f: key = f.read()
tmp = os.path.join(os.environ["TEMP"], "cali.pem")
with open(tmp, "w") as f: f.write(key.strip() + "\n")

# mkdir
subprocess.Popen(["ssh", "-o", "StrictHostKeyChecking=no", "-i", tmp, HOST,
    "mkdir -p /opt/calligraphy-recognition/deploy /opt/calligraphy-recognition/.github/workflows"]).communicate(timeout=30)

scp_srcs = {
    os.path.join(DEPLOY, "Dockerfile"): "/opt/calligraphy-recognition/deploy/Dockerfile",
    os.path.join(DEPLOY, "nginx.conf"): "/opt/calligraphy-recognition/deploy/nginx.conf",
    os.path.join(DEPLOY, "docker-compose.yml"): "/opt/calligraphy-recognition/deploy/docker-compose.yml",
    os.path.join(DEPLOY, "setup.sh"): "/opt/calligraphy-recognition/deploy/setup.sh",
    os.path.join(r"z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\.github\workflows", "deploy.yml"):
        "/opt/calligraphy-recognition/.github/workflows/deploy.yml",
}
for src, dest in scp_srcs.items():
    p = subprocess.Popen(["scp", "-o", "StrictHostKeyChecking=no", "-i", tmp, src, f"{HOST}:{dest}"])
    p.communicate(timeout=60)
    print(f"  SCP {os.path.basename(src)} rc={p.returncode}")

os.unlink(tmp)

# Run setup.sh
ssh_stream("bash /opt/calligraphy-recognition/deploy/setup.sh")
