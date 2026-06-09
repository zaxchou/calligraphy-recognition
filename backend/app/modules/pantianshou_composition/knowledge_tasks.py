"""
任务管理 API
从 knowledge_api.py 拆出
"""

import os
import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from .database import get_db
from .models import PdfBook, KnowledgeTask
from .task_manager import TaskManager
from .knowledge_ingest_v2 import process_pdf_file_sync

router = APIRouter()
logger = logging.getLogger(__name__)


class TaskResponse(BaseModel):
    id: str
    book_id: str
    task_type: str
    status: str
    progress: int
    stage: Optional[str]
    message: Optional[str]
    result: Optional[dict]
    error_message: Optional[str]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


@router.get("/tasks", response_model=List[TaskResponse])
async def list_tasks(
    book_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    获取任务列表
    """
    query = db.query(KnowledgeTask)

    if book_id:
        query = query.filter(KnowledgeTask.book_id == book_id)
    if status:
        query = query.filter(KnowledgeTask.status == status)

    tasks = query.order_by(KnowledgeTask.created_at.desc()).limit(limit).all()

    return [TaskResponse(
        id=t.id,
        book_id=t.book_id,
        task_type=t.task_type,
        status=t.status,
        progress=t.progress,
        stage=t.stage,
        message=t.message,
        result=t.result,
        error_message=t.error_message,
        created_at=t.created_at.isoformat() if t.created_at else None,
        updated_at=t.updated_at.isoformat() if t.updated_at else None,
    ) for t in tasks]


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, db: Session = Depends(get_db)):
    """
    获取任务详情
    """
    task = db.query(KnowledgeTask).filter(KnowledgeTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "任务不存在")

    return TaskResponse(
        id=task.id,
        book_id=task.book_id,
        task_type=task.task_type,
        status=task.status,
        progress=task.progress,
        stage=task.stage,
        message=task.message,
        result=task.result,
        error_message=task.error_message,
        created_at=task.created_at.isoformat() if task.created_at else None,
        updated_at=task.updated_at.isoformat() if task.updated_at else None,
    )


@router.post("/tasks/{task_id}/retry")
async def retry_task(task_id: str, db: Session = Depends(get_db)):
    """
    重试失败的任务
    """
    task = db.query(KnowledgeTask).filter(KnowledgeTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "任务不存在")

    if task.status not in ["failed", "cancelled"]:
        raise HTTPException(400, "只有失败或取消的任务可以重试")

    book = db.query(PdfBook).filter(PdfBook.id == task.book_id).first()
    if not book or not os.path.exists(book.stored_path):
        raise HTTPException(404, "PDF 文件不存在")

    # 重新处理
    try:
        result = process_pdf_file_sync(book.stored_path, task_id=task_id, book_id=book.id)
        return {"message": "任务已重新提交", "result": result}
    except Exception as e:
        raise HTTPException(500, f"重试失败: {str(e)}")


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str, db: Session = Depends(get_db)):
    """
    取消任务
    """
    task_manager = TaskManager(db)
    success = task_manager.cancel_task(task_id)

    if not success:
        raise HTTPException(400, "任务无法取消")

    return {"message": "任务已取消"}
