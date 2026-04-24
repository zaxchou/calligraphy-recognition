"""
任务状态管理与进度跟踪模块
"""

import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from .models import KnowledgeTask, PdfBook
from .database import get_db_context


class TaskManager:
    """任务管理器"""
    
    # 任务状态
    STATUS_QUEUED = "queued"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"
    
    # 任务类型
    TYPE_TEXT_EXTRACT = "text_extract"
    TYPE_IMAGE_EXTRACT = "image_extract"
    TYPE_FULL_PROCESS = "full_process"
    
    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self._local_db = db is None
    
    def __enter__(self):
        if self._local_db:
            self.db_context = get_db_context()
            self.db = self.db_context.__enter__()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._local_db:
            self.db_context.__exit__(exc_type, exc_val, exc_tb)
    
    def create_task(self, 
                    book_id: str, 
                    task_type: str = TYPE_FULL_PROCESS,
                    message: str = "等待处理") -> KnowledgeTask:
        """
        创建新任务
        
        Args:
            book_id: 书籍ID
            task_type: 任务类型
            message: 初始消息
        
        Returns:
            创建的任务对象
        """
        task = KnowledgeTask(
            book_id=book_id,
            task_type=task_type,
            status=self.STATUS_QUEUED,
            progress=0,
            stage="等待中",
            message=message,
        )
        
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        
        # 更新书籍状态
        book = self.db.query(PdfBook).filter(PdfBook.id == book_id).first()
        if book:
            book.status = "processing"
            self.db.commit()
        
        return task
    
    def update_progress(self, 
                        task_id: str, 
                        progress: int, 
                        stage: Optional[str] = None,
                        message: Optional[str] = None):
        """
        更新任务进度
        
        Args:
            task_id: 任务ID
            progress: 进度 0-100
            stage: 当前阶段
            message: 状态消息
        """
        task = self.db.query(KnowledgeTask).filter(KnowledgeTask.id == task_id).first()
        if not task:
            return
        
        task.progress = min(max(progress, 0), 100)
        task.status = self.STATUS_PROCESSING
        
        if stage:
            task.stage = stage
        if message:
            task.message = message
        
        task.updated_at = datetime.utcnow()
        self.db.commit()
    
    def complete_task(self, 
                      task_id: str, 
                      result: Optional[Dict[str, Any]] = None,
                      message: str = "处理完成"):
        """
        标记任务完成
        
        Args:
            task_id: 任务ID
            result: 处理结果
            message: 完成消息
        """
        task = self.db.query(KnowledgeTask).filter(KnowledgeTask.id == task_id).first()
        if not task:
            return
        
        task.status = self.STATUS_COMPLETED
        task.progress = 100
        task.stage = "完成"
        task.message = message
        task.result = result
        task.updated_at = datetime.utcnow()
        
        self.db.commit()
        
        # 更新书籍状态
        book = self.db.query(PdfBook).filter(PdfBook.id == task.book_id).first()
        if book:
            book.status = "completed"
            self.db.commit()
    
    def fail_task(self, 
                  task_id: str, 
                  error_message: str,
                  stage: Optional[str] = None):
        """
        标记任务失败
        
        Args:
            task_id: 任务ID
            error_message: 错误信息
            stage: 失败时的阶段
        """
        task = self.db.query(KnowledgeTask).filter(KnowledgeTask.id == task_id).first()
        if not task:
            return
        
        task.status = self.STATUS_FAILED
        task.stage = stage or "失败"
        task.message = f"处理失败: {error_message[:200]}"
        task.error_message = error_message
        task.updated_at = datetime.utcnow()
        
        self.db.commit()
        
        # 更新书籍状态
        book = self.db.query(PdfBook).filter(PdfBook.id == task.book_id).first()
        if book:
            book.status = "failed"
            self.db.commit()
    
    def cancel_task(self, task_id: str, message: str = "任务已取消"):
        """
        取消任务
        
        Args:
            task_id: 任务ID
            message: 取消消息
        """
        task = self.db.query(KnowledgeTask).filter(KnowledgeTask.id == task_id).first()
        if not task or task.status == self.STATUS_COMPLETED:
            return False
        
        task.status = self.STATUS_CANCELLED
        task.stage = "已取消"
        task.message = message
        task.updated_at = datetime.utcnow()
        
        self.db.commit()
        return True
    
    def get_task(self, task_id: str) -> Optional[KnowledgeTask]:
        """获取任务详情"""
        return self.db.query(KnowledgeTask).filter(KnowledgeTask.id == task_id).first()
    
    def get_tasks_by_book(self, book_id: str) -> List[KnowledgeTask]:
        """获取书籍的所有任务"""
        return self.db.query(KnowledgeTask).filter(
            KnowledgeTask.book_id == book_id
        ).order_by(KnowledgeTask.created_at.desc()).all()
    
    def get_recent_tasks(self, limit: int = 20, status: Optional[str] = None) -> List[KnowledgeTask]:
        """
        获取最近任务
        
        Args:
            limit: 数量限制
            status: 可选的状态过滤
        """
        query = self.db.query(KnowledgeTask)
        
        if status:
            query = query.filter(KnowledgeTask.status == status)
        
        return query.order_by(KnowledgeTask.created_at.desc()).limit(limit).all()
    
    def get_task_stats(self) -> Dict[str, int]:
        """获取任务统计"""
        stats = {}
        
        for status in [self.STATUS_QUEUED, self.STATUS_PROCESSING, 
                       self.STATUS_COMPLETED, self.STATUS_FAILED, self.STATUS_CANCELLED]:
            count = self.db.query(KnowledgeTask).filter(
                KnowledgeTask.status == status
            ).count()
            stats[status] = count
        
        stats["total"] = sum(stats.values())
        return stats


# 便捷函数
def create_processing_task(book_id: str, task_type: str = "full_process") -> str:
    """
    创建处理任务的便捷函数
    
    Returns:
        任务ID
    """
    with TaskManager() as manager:
        task = manager.create_task(book_id, task_type)
        return task.id


def update_task_progress(task_id: str, progress: int, stage: str, message: str):
    """更新任务进度的便捷函数"""
    with TaskManager() as manager:
        manager.update_progress(task_id, progress, stage, message)


def complete_processing_task(task_id: str, result: Dict[str, Any]):
    """完成任务处理的便捷函数"""
    with TaskManager() as manager:
        manager.complete_task(task_id, result)


def fail_processing_task(task_id: str, error: str):
    """标记任务失败的便捷函数"""
    with TaskManager() as manager:
        manager.fail_task(task_id, error)


# 测试代码
if __name__ == "__main__":
    # 测试任务管理
    with TaskManager() as manager:
        # 创建测试任务
        task = manager.create_task("test-book-id", "full_process")
        print(f"创建任务: {task.id}")
        
        # 更新进度
        manager.update_progress(task.id, 30, "文本提取", "正在提取PDF文本...")
        print(f"更新进度: {task.progress}%")
        
        # 完成任务
        manager.complete_task(task.id, {"chunks": 100, "images": 20})
        print(f"任务完成")
        
        # 获取统计
        stats = manager.get_task_stats()
        print(f"任务统计: {stats}")
