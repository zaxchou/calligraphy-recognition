"""
MinerU 云 API 客户端
支持精准解析 API（/api/v4/file-urls/batch）
"""

import os
import time
import json
import zipfile
import logging
import requests
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


def _get_mineru_config():
    """从 Settings 类获取 MinerU 配置（优先），回退到 os.getenv"""
    try:
        from app.core.config import Settings
        settings = Settings()
        return settings.MINERU_API_TOKEN, settings.MINERU_API_BASE, settings.MINERU_MODEL_VERSION
    except Exception:
        return os.getenv("MINERU_API_TOKEN", ""), os.getenv("MINERU_API_BASE", "https://mineru.net"), os.getenv("MINERU_MODEL_VERSION", "vlm")


@dataclass
class MineruResult:
    """MinerU 解析结果"""
    success: bool
    zip_path: Optional[str] = None
    content_list: Optional[list] = None
    full_md: Optional[str] = None
    images_dir: Optional[str] = None
    error: Optional[str] = None
    page_count: Optional[int] = None


class MinerUClient:
    """MinerU 云 API 客户端"""
    
    def __init__(
        self,
        api_token: Optional[str] = None,
        api_base: Optional[str] = None,
        model_version: Optional[str] = None,
        timeout: int = 300,
        poll_interval: int = 3,
    ):
        # 从 Settings 或环境变量获取配置
        default_token, default_base, default_version = _get_mineru_config()
        
        self.api_token = api_token or default_token
        self.api_base = (api_base or default_base).rstrip("/")
        self.model_version = model_version or default_version
        self.timeout = timeout
        self.poll_interval = poll_interval
        
        if not self.api_token:
            raise ValueError("MINERU_API_TOKEN 未配置，请在 .env 中设置")
    
    @property
    def headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }
    
    def request_upload_urls(self, pdf_files: list[Dict[str, Any]]) -> Dict[str, Any]:
        """申请文件上传链接
        
        Args:
            pdf_files: 文件列表，每项包含 name, is_ocr, data_id 等
        
        Returns:
            包含 batch_id 和 file_urls 的字典
        """
        url = f"{self.api_base}/api/v4/file-urls/batch"
        payload = {
            "enable_formula": True,
            "enable_table": True,
            "model_version": self.model_version,
            "language": "ch",
            "files": pdf_files,
        }
        
        logger.info(f"申请上传链接: {len(pdf_files)} 个文件")
        resp = requests.post(url, headers=self.headers, json=payload, timeout=30)
        resp.raise_for_status()
        
        result = resp.json()
        if result.get("code") != 0:
            raise RuntimeError(f"MinerU API 错误: {result.get('msg')}")
        
        data = result["data"]
        logger.info(f"获取 batch_id: {data.get('batch_id')}")
        return data
    
    def upload_file(self, upload_url: str, file_path: str) -> bool:
        """上传文件到指定 URL
        
        Args:
            upload_url: OSS 上传链接
            file_path: 本地文件路径
        
        Returns:
            是否上传成功
        """
        logger.info(f"上传文件: {Path(file_path).name}")
        
        with open(file_path, "rb") as f:
            resp = requests.put(upload_url, data=f, timeout=120)
        
        if resp.status_code == 200:
            logger.info("上传成功")
            return True
        else:
            logger.error(f"上传失败: {resp.status_code}")
            return False
    
    def poll_batch_result(self, batch_id: str) -> Dict[str, Any]:
        """轮询批量任务结果
        
        Args:
            batch_id: 批次 ID
        
        Returns:
            批次结果字典
        """
        url = f"{self.api_base}/api/v4/extract-results/batch/{batch_id}"
        
        logger.info(f"轮询任务结果: {batch_id}")
        start_time = time.time()
        
        while time.time() - start_time < self.timeout:
            resp = requests.get(url, headers={"Authorization": f"Bearer {self.api_token}"}, timeout=30)
            resp.raise_for_status()
            
            result = resp.json()
            if result.get("code") != 0:
                logger.warning(f"轮询返回错误: {result.get('msg')}")
                time.sleep(self.poll_interval)
                continue
            
            batch_result = result.get("data", {})
            extract_result = batch_result.get("extract_result", [])
            
            # 检查所有任务状态
            all_done = True
            for item in extract_result:
                state = item.get("state", "")
                if state == "failed":
                    raise RuntimeError(f"任务失败: {item.get('err_msg')}")
                if state != "done":
                    all_done = False
                    logger.debug(f"状态: {state}")
                    break
            
            if all_done:
                logger.info("所有任务完成")
                return batch_result
            
            time.sleep(self.poll_interval)
        
        raise TimeoutError(f"轮询超时 ({self.timeout}秒)")
    
    def download_result(self, zip_url: str, output_dir: str) -> str:
        """下载解析结果
        
        Args:
            zip_url: 结果 zip 下载链接
            output_dir: 输出目录
        
        Returns:
            zip 文件路径
        """
        os.makedirs(output_dir, exist_ok=True)
        zip_path = os.path.join(output_dir, "mineru_result.zip")
        
        logger.info(f"下载解析结果...")
        resp = requests.get(zip_url, timeout=120)
        resp.raise_for_status()
        
        with open(zip_path, "wb") as f:
            f.write(resp.content)
        
        logger.info(f"已保存到: {zip_path}")
        return zip_path
    
    def parse_pdf(self, pdf_path: str, output_dir: Optional[str] = None) -> MineruResult:
        """完整流程：上传 → 轮询 → 下载 → 解析
        
        Args:
            pdf_path: PDF 文件路径
            output_dir: 输出目录（默认为 PDF 同目录）
        
        Returns:
            MineruResult
        """
        pdf_path = os.path.abspath(pdf_path)
        if not os.path.exists(pdf_path):
            return MineruResult(success=False, error=f"文件不存在: {pdf_path}")
        
        if output_dir is None:
            output_dir = os.path.dirname(pdf_path)
        
        file_name = os.path.basename(pdf_path)
        file_size_mb = os.path.getsize(pdf_path) / 1024 / 1024
        
        logger.info(f"开始解析: {file_name} ({file_size_mb:.1f} MB)")
        
        try:
            # Step 1: 申请上传链接
            pdf_files = [{"name": file_name, "is_ocr": False}]
            upload_data = self.request_upload_urls(pdf_files)
            
            batch_id = upload_data.get("batch_id")
            file_urls = upload_data.get("file_urls", [])
            
            if not file_urls:
                return MineruResult(success=False, error="未获取到上传链接")
            
            # file_urls 可能是字符串列表或字典列表
            first = file_urls[0]
            upload_url = first if isinstance(first, str) else first.get("url")
            
            # Step 2: 上传文件
            if not self.upload_file(upload_url, pdf_path):
                return MineruResult(success=False, error="文件上传失败")
            
            # Step 3: 轮询结果
            logger.info("等待解析完成...")
            time.sleep(2)  # 等待系统处理
            
            batch_result = self.poll_batch_result(batch_id)
            extract_result = batch_result.get("extract_result", [])
            
            if not extract_result:
                return MineruResult(success=False, error="未获取到解析结果")
            
            first_result = extract_result[0]
            
            if first_result.get("state") != "done":
                return MineruResult(
                    success=False,
                    error=f"解析失败: {first_result.get('err_msg')}"
                )
            
            # Step 4: 下载结果
            full_zip_url = first_result.get("full_zip_url")
            if not full_zip_url:
                return MineruResult(success=False, error="未获取到下载链接")
            
            zip_path = self.download_result(full_zip_url, output_dir)
            
            # Step 5: 解析 zip 内容
            return self._parse_zip(zip_path)
            
        except Exception as e:
            logger.error(f"MinerU 解析失败: {e}")
            return MineruResult(success=False, error=str(e))
    
    def _parse_zip(self, zip_path: str) -> MineruResult:
        """解析 MinerU 输出的 zip 文件
        
        Args:
            zip_path: zip 文件路径
        
        Returns:
            MineruResult
        """
        try:
            with zipfile.ZipFile(zip_path, "r") as z:
                # 读取 content_list.json
                content_list = None
                for name in z.namelist():
                    if name.endswith("_content_list.json") or name == "content_list.json":
                        content_list = json.loads(z.read(name).decode("utf-8"))
                        break
                
                # 读取 full.md
                full_md = None
                for name in z.namelist():
                    if name == "full.md":
                        full_md = z.read(name).decode("utf-8")
                        break
                
                # 解压 images/ 目录
                images_dir = os.path.join(os.path.dirname(zip_path), "mineru_images")
                os.makedirs(images_dir, exist_ok=True)
                
                for name in z.namelist():
                    if name.startswith("images/") and not name.endswith("/"):
                        # 提取图片文件
                        img_data = z.read(name)
                        img_name = os.path.basename(name)
                        img_path = os.path.join(images_dir, img_name)
                        with open(img_path, "wb") as f:
                            f.write(img_data)
                
                # 统计页数
                page_count = None
                if content_list:
                    pages = set()
                    for item in content_list:
                        if "page_idx" in item:
                            pages.add(item["page_idx"])
                    if pages:
                        page_count = max(pages) + 1  # 0-based -> 1-based
                
                logger.info(
                    f"解析完成: {len(content_list or [])} 内容块, "
                    f"{len(full_md or '')} 字符, "
                    f"{page_count} 页"
                )
                
                return MineruResult(
                    success=True,
                    zip_path=zip_path,
                    content_list=content_list,
                    full_md=full_md,
                    images_dir=images_dir,
                    page_count=page_count,
                )
                
        except Exception as e:
            logger.error(f"解析 zip 失败: {e}")
            return MineruResult(success=False, error=str(e))


# 便捷函数
def parse_pdf_with_mineru(pdf_path: str, output_dir: Optional[str] = None) -> MineruResult:
    """使用 MinerU 云 API 解析 PDF
    
    Args:
        pdf_path: PDF 文件路径
        output_dir: 输出目录
    
    Returns:
        MineruResult
    """
    client = MinerUClient()
    return client.parse_pdf(pdf_path, output_dir)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        pdf_file = sys.argv[1]
        print(f"使用 MinerU 云 API 解析: {pdf_file}")
        
        result = parse_pdf_with_mineru(pdf_file)
        
        if result.success:
            print(f"解析成功!")
            print(f"  页数: {result.page_count}")
            print(f"  内容块: {len(result.content_list or [])}")
            print(f"  Markdown 字符: {len(result.full_md or '')}")
            print(f"  图片目录: {result.images_dir}")
            print(f"  zip 路径: {result.zip_path}")
        else:
            print(f"解析失败: {result.error}")
