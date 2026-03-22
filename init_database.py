#!/usr/bin/env python3
"""
初始化数据库脚本
"""
import subprocess
import sys
import os

def main():
    """初始化数据库"""
    backend_dir = os.path.join(os.path.dirname(__file__), 'backend')
    script_path = os.path.join(backend_dir, 'scripts', 'init_data.py')
    
    print("正在初始化数据库...")
    print(f"脚本路径: {script_path}")
    
    if not os.path.exists(script_path):
        print(f"错误: 找不到脚本文件 {script_path}")
        sys.exit(1)
    
    try:
        subprocess.run(
            [sys.executable, script_path],
            cwd=backend_dir,
            check=True
        )
        print("\n✓ 数据库初始化完成")
    except subprocess.CalledProcessError as e:
        print(f"\n✗ 初始化失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ 发生错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
