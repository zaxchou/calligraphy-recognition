"""
聊天会话管理 API — 会话 CRUD

端点:
    POST   /api/v1/knowledge/chat/sessions       — 创建新会话
    GET    /api/v1/knowledge/chat/sessions       — 获取当前用户的会话列表
    GET    /api/v1/knowledge/chat/sessions/{id}/messages — 获取会话消息
    DELETE /api/v1/knowledge/chat/sessions/{id}  — 删除会话
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.core.database import SessionLocal
from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)


class SessionOut(BaseModel):
    id: str
    title: str
    message_count: int
    session_type: Optional[str] = 'global'
    artist_id: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    sources: Optional[list] = None
    token_index: int
    created_at: Optional[str] = None


@router.post("/chat/sessions", response_model=SessionOut)
def create_session(user: User = Depends(get_current_user)):
    """创建新聊天会话"""
    sid = str(uuid.uuid4())
    now = datetime.utcnow()
    db = SessionLocal()
    try:
        db.execute(
            text(
                "INSERT INTO chat_sessions (id, user_id, title, message_count, created_at, updated_at) "
                "VALUES (:id, :uid, :title, 0, :now, :now)"
            ),
            {"id": sid, "uid": user.id, "title": "新对话", "now": now},
        )
        db.commit()
        logger.info("创建会话: id=%s, user=%d", sid, user.id)
    finally:
        db.close()
    return SessionOut(id=sid, title="新对话", message_count=0,
                      created_at=now.isoformat(), updated_at=now.isoformat())


@router.get("/chat/sessions", response_model=List[SessionOut])
def list_sessions(user: User = Depends(get_current_user)):
    """获取当前用户的会话列表（按更新时间倒序）"""
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                "SELECT id, title, message_count, session_type, artist_id, created_at, updated_at "
                "FROM chat_sessions WHERE user_id = :uid ORDER BY updated_at DESC LIMIT 50"
            ),
            {"uid": user.id},
        ).fetchall()
    finally:
        db.close()

    now = datetime.utcnow()
    results = []
    for row in rows:
        try:
            raw_created = row[5]
            raw_updated = row[6]
            created_str = raw_created if isinstance(raw_created, str) else str(raw_created)
            updated_str = raw_updated if isinstance(raw_updated, str) else str(raw_updated)

            results.append(SessionOut(
                id=row[0],
                title=row[1] or "新对话",
                message_count=int(row[2] or 0),
                session_type=row[3] or 'global',
                artist_id=row[4],
                created_at=created_str,
                updated_at=updated_str,
            ))
        except Exception as e:
            logger.error("Session row error: %s, row=%s", e, row)
    return results


@router.get("/chat/sessions/{session_id}/messages", response_model=List[MessageOut])
def get_messages(session_id: str, user: User = Depends(get_current_user)):
    """获取会话消息历史（验证所有权）"""
    db = SessionLocal()
    try:
        owner = db.execute(
            text("SELECT user_id FROM chat_sessions WHERE id = :sid"),
            {"sid": session_id},
        ).fetchone()
        if not owner:
            raise HTTPException(404, "会话不存在")
        if owner[0] != user.id:
            raise HTTPException(403, "无权访问此会话")

        rows = db.execute(
            text(
                "SELECT id, role, content, sources, token_index, created_at "
                "FROM chat_messages WHERE session_id = :sid ORDER BY token_index"
            ),
            {"sid": session_id},
        ).fetchall()
    finally:
        db.close()

    results = []
    for row in rows:
        sources = None
        if row[3]:
            try:
                sources = json.loads(row[3]) if isinstance(row[3], str) else row[3]
            except (json.JSONDecodeError, TypeError):
                pass
        raw_created = row[5]
        created_str = raw_created if isinstance(raw_created, str) else str(raw_created) if raw_created else None
        results.append(MessageOut(
            id=row[0],
            role=row[1],
            content=row[2],
            sources=sources,
            token_index=int(row[4] or 0),
            created_at=created_str,
        ))
    return results


@router.delete("/chat/sessions/{session_id}")
def delete_session(session_id: str, user: User = Depends(get_current_user)):
    """删除会话及所有消息（验证所有权）"""
    db = SessionLocal()
    try:
        owner = db.execute(
            text("SELECT user_id FROM chat_sessions WHERE id = :sid"),
            {"sid": session_id},
        ).fetchone()
        if not owner:
            raise HTTPException(404, "会话不存在")
        if owner[0] != user.id:
            raise HTTPException(403, "无权操作此会话")

        db.execute(
            text("DELETE FROM chat_messages WHERE session_id = :sid"), {"sid": session_id})
        db.execute(
            text("DELETE FROM chat_sessions WHERE id = :sid"), {"sid": session_id})
        db.commit()
        logger.info("删除会话: id=%s, user=%d", session_id, user.id)
    finally:
        db.close()
    return {"success": True, "message": "已删除"}
