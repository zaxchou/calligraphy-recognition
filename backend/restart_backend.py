"""
后端一键重启脚本
================
自动杀掉占用端口的进程，然后启动后端。
如果 8001 端口被僵尸 socket 占用，自动切到 8002。

用法: python restart_backend.py

提示: Windows 偶尔会出现进程已死但端口不释放的情况（僵尸 socket），
     脚本会自动检测并用备用端口。如果两个端口都不可用，请重启电脑。
"""
import subprocess
import sys
import os
import io
import socket

# 修复 Windows 控制台编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

PORT = 8001
BACKUP_PORTS = [8002, 8003, 8010, 8020]


def kill_port(port):
    """杀掉所有占用指定端口的活进程"""
    result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
    pids = set()
    for line in result.stdout.split("\n"):
        if f":{port}" in line and "LISTENING" in line:
            parts = line.split()
            if parts:
                try:
                    pid = int(parts[-1])
                    if pid > 0:
                        pids.add(pid)
                except ValueError:
                    pass
    killed = 0
    for pid in pids:
        try:
            r = subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)],
                capture_output=True, text=True, timeout=5
            )
            if "成功" in r.stdout or "SUCCESS" in r.stdout.upper():
                killed += 1
                print(f"      已杀掉 PID {pid}")
        except (subprocess.TimeoutExpired, Exception):
            print(f"      PID {pid} 不存在（僵尸 socket）")
    return killed


def try_bind(port):
    """测试端口能否真正绑定（模拟 uvicorn 的行为）"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("0.0.0.0", port))
        s.close()
        return True
    except OSError:
        s.close()
        return False


def find_available_port():
    """找到一个可用端口"""
    for p in [PORT] + BACKUP_PORTS:
        kill_port(p)
        if try_bind(p):
            return p
    return None


if __name__ == "__main__":
    print("=" * 50)
    print("  书法碑帖系统 - 后端重启")
    print("=" * 50)
    print()

    # 清理主端口
    print(f"[1/2] 清理 {PORT} 端口 ...")
    kill_port(PORT)

    # 找可用端口
    port = find_available_port()

    if port is None:
        print()
        print("[ERROR] 所有端口都被占用，请重启电脑后重试")
        sys.exit(1)

    if port != PORT:
        print(f"[WARN] 主端口 {PORT} 被僵尸 socket 占用，自动使用 {port}")
        print(f"       前端 proxy 需要指向 {port}，或重启电脑后恢复正常")

    print(f"[2/2] 启动后端 (端口 {port}) ...")
    print(f"      按 Ctrl+C 停止")
    print()

    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "app.main:app",
        "--host", "0.0.0.0",
        "--port", str(port),
    ])
