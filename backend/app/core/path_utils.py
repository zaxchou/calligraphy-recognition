"""
跨平台路径处理工具
解决 Windows 和 Linux 路径分隔符兼容问题
"""
import os
from pathlib import Path


def normalize_path(path: str) -> str:
    """
    将路径标准化，统一使用正斜杠 '/'
    用于存储到数据库的路径
    """
    if not path:
        return path
    # 将所有反斜杠替换为正斜杠
    return path.replace('\\', '/')


def to_url_path(path: str) -> str:
    """
    将路径转换为 URL 格式（正斜杠）
    用于生成静态文件 URL
    """
    if not path:
        return path
    # 确保路径以 / 开头
    if not path.startswith('/'):
        path = '/' + path
    # 统一使用正斜杠
    return path.replace('\\', '/')


def to_os_path(path: str, base_dir: str = None) -> str:
    """
    将存储的路径转换为当前操作系统的本地路径
    用于文件系统操作
    """
    if not path:
        return path
    
    # 标准化路径分隔符
    normalized = path.replace('\\', '/')
    
    # 如果是绝对路径（以/开头），去掉开头的/
    if normalized.startswith('/'):
        normalized = normalized[1:]
    
    # 如果提供了基础目录，拼接路径
    if base_dir:
        return os.path.join(base_dir, *normalized.split('/'))
    
    # 否则使用当前操作系统的路径分隔符
    return os.path.join(*normalized.split('/'))


def join_url_path(*parts: str) -> str:
    """
    使用正斜杠拼接 URL 路径
    用于生成静态文件 URL
    """
    # 过滤空值
    parts = [p for p in parts if p]
    if not parts:
        return ''
    
    # 拼接并处理多余的分隔符
    result = '/'.join(parts)
    # 将反斜杠替换为正斜杠
    result = result.replace('\\', '/')
    # 处理多个连续的斜杠
    while '//' in result:
        result = result.replace('//', '/')
    
    return result


def get_static_url(relative_path: str) -> str:
    """
    生成静态文件 URL
    确保使用正斜杠，以 /static/ 开头
    """
    if not relative_path:
        return ''
    
    # 标准化路径
    normalized = normalize_path(relative_path)
    
    # 确保以 /static/ 开头
    if normalized.startswith('/static/'):
        return normalized
    elif normalized.startswith('static/'):
        return '/' + normalized
    else:
        return '/static/' + normalized.lstrip('/')


def get_full_file_path(stored_path: str, base_dir: str) -> str:
    """
    根据存储的路径和基础目录，获取完整的文件系统路径
    兼容 Windows 和 Linux
    """
    if not stored_path:
        return ''
    
    # 标准化存储的路径
    normalized = normalize_path(stored_path)
    
    # 去掉开头的 /static/ 或 static/
    if normalized.startswith('/static/'):
        relative = normalized[8:]  # 去掉 '/static/'
    elif normalized.startswith('static/'):
        relative = normalized[7:]  # 去掉 'static/'
    else:
        relative = normalized.lstrip('/')
    
    # 使用 os.path.join 拼接路径
    return os.path.join(base_dir, *relative.split('/'))
