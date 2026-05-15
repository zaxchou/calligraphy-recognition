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


def run_migrations():
    """在应用启动时执行必要的数据库迁移。幂等——可安全重复执行。"""
    import sqlite3
    from app.core.config import get_settings
    settings = get_settings()
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        cur = conn.execute("PRAGMA table_info(users)")
        cols = {row[1] for row in cur.fetchall()}

        if "uid" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN uid TEXT")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_uid ON users(uid)")
            logger.info("Migration: added users.uid column")

        if "nickname_changed_at" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN nickname_changed_at TIMESTAMP")
            logger.info("Migration: added users.nickname_changed_at column")

        # 为已有用户生成 uid（10000001 起）
        rows = conn.execute(
            "SELECT id FROM users WHERE uid IS NULL ORDER BY id"
        ).fetchall()
        for (user_id,) in rows:
            conn.execute(
                "UPDATE users SET uid = ? WHERE id = ?",
                (str(10000000 + user_id), user_id),
            )
        if rows:
            conn.execute("UPDATE users SET uid = '10000001' WHERE id = 1 AND uid IS NULL")
            logger.info("Migration: backfilled uid for %d users", len(rows))

        # ── role_permissions 表 ──
        conn.execute("""
            CREATE TABLE IF NOT EXISTS role_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                permission_key TEXT NOT NULL,
                UNIQUE(role, permission_key)
            )
        """)
        logger.info("Migration: ensured role_permissions table exists")

        # 种子数据：admin 默认拥有除 system.permissions 外的所有权限
        ALL_PERMISSIONS = [
            "content.verify", "content.annotate", "content.upload", "content.batch",
            "metadata.dimensions", "metadata.seals", "metadata.albums",
            "metadata.strips", "metadata.tags",
            "knowledge.artist_info", "knowledge.artist_rules",
            "tools.dedup",
            "system.dashboard", "system.users", "system.permissions", "system.config",
        ]
        EDITOR_PERMISSIONS = [
            "content.verify", "content.annotate", "content.upload",
            "metadata.dimensions", "metadata.seals", "metadata.albums",
            "metadata.strips", "metadata.tags",
            "knowledge.artist_info", "knowledge.artist_rules",
        ]

        existing = conn.execute(
            "SELECT role, permission_key FROM role_permissions"
        ).fetchall()
        existing_set = {(r[0], r[1]) for r in existing}

        for pk in ALL_PERMISSIONS:
            if ("admin", pk) not in existing_set:
                conn.execute(
                    "INSERT OR IGNORE INTO role_permissions (role, permission_key) VALUES (?, ?)",
                    ("admin", pk),
                )
        for pk in EDITOR_PERMISSIONS:
            if ("editor", pk) not in existing_set:
                conn.execute(
                    "INSERT OR IGNORE INTO role_permissions (role, permission_key) VALUES (?, ?)",
                    ("editor", pk),
                )
        if existing_set != {
            ("admin", pk) for pk in ALL_PERMISSIONS
        } | {("editor", pk) for pk in EDITOR_PERMISSIONS}:
            logger.info("Migration: seeded role_permissions defaults")

        # ── site_settings 表 ──
        conn.execute("""
            CREATE TABLE IF NOT EXISTS site_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 种子默认值
        defaults = [
            ("title", "墨林百科"),
            ("subtitle", "最智能的中国画与书法大库"),
            ("full_title", "墨林百科 - 最智能的中国画与书法大库"),
            ("domain", "molin.wiki"),
            ("footer", "墨林百科 © 2026"),
            ("author", "周豪 Zax"),
        ]
        for k, v in defaults:
            conn.execute(
                "INSERT OR IGNORE INTO site_settings (key, value) VALUES (?, ?)",
                (k, v),
            )
        logger.info("Migration: ensured site_settings table exists")

        conn.commit()
    finally:
        conn.close()


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
