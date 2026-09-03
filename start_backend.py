#!/usr/bin/env python3
"""
启动后端服务脚本
- 先杀掉所有在端口8003上运行的进程
- 然后启动一个新的后端服务
- 确保前端配置与后端端口一致
"""
import os
import subprocess
import time
import socket

def get_processes_by_port(port):
    """获取在指定端口上运行的进程ID列表"""
    try:
        # 使用netstat命令获取在指定端口上运行的进程
        output = subprocess.check_output(['netstat', '-ano'], universal_newlines=True)
        processes = []
        for line in output.split('\n'):
            if f':{port}' in line and 'LISTENING' in line:
                # 提取进程ID
                parts = line.strip().split()
                if len(parts) >= 5:
                    pid = parts[4]
                    processes.append(pid)
        return processes
    except Exception as e:
        print(f"获取进程列表时出错: {e}")
        return []

def kill_process(pid):
    """杀掉指定的进程"""
    try:
        subprocess.run(['taskkill', '/F', '/PID', pid], check=True)
        print(f"成功终止进程 {pid}")
        return True
    except Exception as e:
        print(f"终止进程 {pid} 时出错: {e}")
        return False

def check_port_available(port):
    """检查指定端口是否可用"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    try:
        result = sock.connect_ex(('localhost', port))
        return result != 0
    except Exception:
        return False
    finally:
        sock.close()

def start_backend():
    """启动后端服务"""
    port = 8003
    backend_dir = os.path.join(os.path.dirname(__file__), 'backend')
    
    print("=== 启动后端服务 ===")
    
    # 1. 获取并杀掉在端口8003上运行的进程
    print(f"检查端口 {port} 上的进程...")
    processes = get_processes_by_port(port)
    
    if processes:
        print(f"发现 {len(processes)} 个在端口 {port} 上运行的进程:")
        for pid in processes:
            kill_process(pid)
        # 等待进程完全终止
        time.sleep(2)
    else:
        print(f"端口 {port} 上没有运行的进程")
    
    # 2. 检查端口是否可用
    print(f"检查端口 {port} 是否可用...")
    if not check_port_available(port):
        print(f"错误: 端口 {port} 仍然被占用")
        return False
    
    # 3. 启动后端服务
    print(f"启动后端服务，端口: {port}...")
    
    # 构建启动命令
    command = [
        'python', '-m', 'uvicorn', 'app.main:app',
        '--host', '0.0.0.0',
        '--port', str(port),
        '--log-level', 'info'
    ]
    
    # 在新的终端中启动后端服务
    print(f"在目录 {backend_dir} 中执行命令: {' '.join(command)}")
    
    # 使用PowerShell启动新终端
    powershell_command = f"cd '{backend_dir}'; {' '.join(command)}"
    subprocess.Popen(
        ['powershell', '-Command', powershell_command],
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    
    # 等待服务启动
    print("等待后端服务启动...")
    time.sleep(5)
    
    # 4. 检查服务是否成功启动
    if check_port_available(port):
        print("错误: 后端服务启动失败")
        return False
    else:
        print("✓ 后端服务启动成功")
        return True

if __name__ == "__main__":
    start_backend()
