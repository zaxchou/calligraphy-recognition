from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import logging
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
logger.info("Using database: %s", settings.DATABASE_URL)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"timeout": 30},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_connection():
    """Raw SQLite connection for legacy scripts."""
    import sqlite3
    db_url = settings.DATABASE_URL
    db_path = db_url.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn
