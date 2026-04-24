"""
知识库数据库会话管理
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator

from .models import Base, init_knowledge_tables

# 数据库路径
DB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")
DB_PATH = os.path.join(DB_DIR, "knowledge.db")

# 确保目录存在
os.makedirs(DB_DIR, exist_ok=True)

# 创建引擎
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    echo=False,
)

# 会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """获取数据库会话（用于依赖注入）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """上下文管理器方式获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_database():
    """初始化数据库表"""
    init_knowledge_tables(engine)
    # 自动迁移：为已有表添加新列
    _auto_migrate(engine)
    print(f"[Knowledge DB] 数据库初始化完成: {DB_PATH}")


def _auto_migrate(engine):
    """自动迁移：检查并添加缺失的列"""
    import logging
    from sqlalchemy import inspect, text
    
    logger = logging.getLogger(__name__)
    inspector = inspect(engine)
    
    # extracted_images 表迁移：添加 caption 列
    if "extracted_images" in inspector.get_table_names():
        existing_columns = {c["name"] for c in inspector.get_columns("extracted_images")}
        if "caption" not in existing_columns:
            logger.info("[Knowledge DB] 迁移: 为 extracted_images 添加 caption 列")
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE extracted_images ADD COLUMN caption TEXT"))
                conn.commit()
    
    # text_chunks 表迁移：添加 bbox 列
    if "text_chunks" in inspector.get_table_names():
        existing_columns = {c["name"] for c in inspector.get_columns("text_chunks")}
        if "bbox" not in existing_columns:
            logger.info("[Knowledge DB] 迁移: 为 text_chunks 添加 bbox 列")
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE text_chunks ADD COLUMN bbox JSON"))
                conn.commit()


# 启动时自动初始化
init_database()
