#!/usr/bin/env python3
"""
启动后端服务脚本
"""
import subprocess
import sys
import os

def main():
    """启动后端服务"""
    backend_dir = os.path.join(os.path.dirname(__file__), 'backend')
    
    print("正在启动书法碑帖字体认证系统后端服务...")
    print(f"工作目录: {backend_dir}")
    
    # 检查依赖
    try:
        import fastapi
        import sqlalchemy
        import cv2
        import numpy
        print("✓ 依赖检查通过")
    except ImportError as e:
        print(f"✗ 缺少依赖: {e}")
        print("请先安装依赖: pip install -r backend/requirements.txt")
        sys.exit(1)
    
    # 启动服务
    try:
        subprocess.run(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
            cwd=backend_dir,
            check=True
        )
    except KeyboardInterrupt:
        print("\n服务已停止")
    except Exception as e:
        print(f"启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
