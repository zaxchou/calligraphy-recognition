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
    import json
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

        # ── 初始画库（Phase A） ──
        conn.execute("""
            CREATE TABLE IF NOT EXISTS artwork_libraries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(255) NOT NULL,
                artist_name VARCHAR(255),
                description TEXT,
                owner_id INTEGER NOT NULL,
                visibility VARCHAR(20) DEFAULT 'private',
                artwork_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        lib_names = [
            ("李鱓作品全集", "李鱓"),
            ("刘海勇作品全集", "刘海勇"),
            ("郑燮作品全集", "郑燮"),
        ]
        existing_libs = {
            r[0] for r in conn.execute(
                "SELECT artist_name FROM artwork_libraries WHERE owner_id = 1 AND artist_name IS NOT NULL"
            ).fetchall()
        }
        for lib_name, artist_name in lib_names:
            if artist_name not in existing_libs:
                conn.execute(
                    "INSERT INTO artwork_libraries (name, artist_name, owner_id, visibility) VALUES (?, ?, 1, 'public')",
                    (lib_name, artist_name),
                )
                logger.info("Migration: 创建画库 %s", lib_name)
        # 归入现有作品
        lib_map = {
            r[1]: r[0] for r in conn.execute(
                "SELECT id, artist_name FROM artwork_libraries WHERE owner_id = 1 AND artist_name IS NOT NULL"
            ).fetchall()
        }
        if lib_map:
            null_rows = conn.execute(
                "SELECT id, artist FROM tubi_analyses WHERE library_id IS NULL"
            ).fetchall()
            for row_id, artist_name in null_rows:
                lib_id = lib_map.get(artist_name) or lib_map.get("李鱓")
                conn.execute(
                    "UPDATE tubi_analyses SET library_id = ?, owner_id = 1, visibility = 'public' WHERE id = ?",
                    (lib_id, row_id),
                )
            if null_rows:
                logger.info("Migration: 归入 %d 条作品到画库", len(null_rows))
            for lib_id in lib_map.values():
                count = conn.execute(
                    "SELECT COUNT(*) FROM tubi_analyses WHERE library_id = ?", (lib_id,)
                ).fetchone()[0]
                conn.execute(
                    "UPDATE artwork_libraries SET artwork_count = ? WHERE id = ?",
                    (count, lib_id),
                )

        conn.commit()

        # ── Phase 2: change_request 扩展字段 ──
        cr_cols = {row[1] for row in conn.execute("PRAGMA table_info(change_requests)").fetchall()}
        if "draft_data" not in cr_cols:
            conn.execute("ALTER TABLE change_requests ADD COLUMN draft_data TEXT")
            logger.info("Migration: added change_requests.draft_data")
        if "base_revision" not in cr_cols:
            conn.execute("ALTER TABLE change_requests ADD COLUMN base_revision INTEGER")
            logger.info("Migration: added change_requests.base_revision")
        conn.commit()

        # ── Phase 4: notifications 表 ──
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                type VARCHAR(30) NOT NULL,
                title VARCHAR(255) NOT NULL,
                body TEXT,
                reference_type VARCHAR(30),
                reference_id INTEGER,
                is_read INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS ix_notifications_user_id ON notifications(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_notifications_is_read ON notifications(is_read)")
        logger.info("Migration: ensured notifications table exists")
        conn.commit()

        # ── Phase 7: 用户贡献积分 ──
        user_cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "score" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN score INTEGER DEFAULT 0")
            logger.info("Migration: added users.score")
        conn.commit()

        # ════════════════════════════════════════════════════════
        # 画家百科 Phase 1: 扩展 artists 表 + 新建相关表
        # ════════════════════════════════════════════════════════

        # ── artists 表扩展 ──
        artist_cols = {row[1] for row in conn.execute("PRAGMA table_info(artists)").fetchall()}
        for col, col_type in [
            ("alias", "TEXT DEFAULT ''"),
            ("dynasty", "TEXT DEFAULT ''"),
            ("hometown", "TEXT DEFAULT ''"),
            ("avatar_url", "TEXT DEFAULT ''"),
            ("death_year", "INTEGER"),
            ("biography", "TEXT DEFAULT ''"),
            ("bio_events", "TEXT DEFAULT '[]'"),
            ("art_school", "TEXT DEFAULT ''"),
            ("masterpieces", "TEXT DEFAULT '[]'"),
            ("tags", "TEXT DEFAULT '[]'"),
            ("baidu_url", "TEXT DEFAULT ''"),
            ("view_count", "INTEGER DEFAULT 0"),
            ("featured", "INTEGER DEFAULT 0"),
            ("photos", "TEXT DEFAULT '[]'"),
        ]:
            if col not in artist_cols:
                conn.execute(f"ALTER TABLE artists ADD COLUMN {col} {col_type}")
                logger.info("Migration: added artists.%s", col)
        conn.commit()

        # ── 画家百科 Phase 2: 新增百科字段 ──
        _ensure_artist_columns()

        # ── art_schools 表 ──
        conn.execute("""
            CREATE TABLE IF NOT EXISTS art_schools (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT DEFAULT '',
                dynasty TEXT DEFAULT '',
                origin TEXT DEFAULT '',
                rep_artists TEXT DEFAULT '[]',
                style_features TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        logger.info("Migration: ensured art_schools table exists")
        conn.commit()

        # ── artwork_artists 表（作品-画家多对多） ──
        conn.execute("""
            CREATE TABLE IF NOT EXISTS artwork_artists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artwork_id INTEGER NOT NULL,
                artist_id INTEGER NOT NULL,
                role VARCHAR(20) DEFAULT 'author',
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(artwork_id, artist_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS ix_artwork_artists_artwork_id ON artwork_artists(artwork_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_artwork_artists_artist_id ON artwork_artists(artist_id)")
        logger.info("Migration: ensured artwork_artists table exists")
        conn.commit()

        # ── artist_change_requests 表 ──
        conn.execute("""
            CREATE TABLE IF NOT EXISTS artist_change_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artist_id INTEGER NOT NULL,
                request_type VARCHAR(30) NOT NULL,
                field_name VARCHAR(100),
                old_value TEXT,
                new_value TEXT,
                change_summary TEXT,
                submitter_id INTEGER NOT NULL,
                reviewer_id INTEGER,
                status VARCHAR(20) DEFAULT 'pending',
                review_comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS ix_artist_cr_artist_id ON artist_change_requests(artist_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_artist_cr_status ON artist_change_requests(status)")
        logger.info("Migration: ensured artist_change_requests table exists")
        conn.commit()

        # ── seal_images 表 + seals.source 列 ──
        conn.execute("""
            CREATE TABLE IF NOT EXISTS seal_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seal_id INTEGER NOT NULL REFERENCES seals(id) ON DELETE CASCADE,
                path TEXT NOT NULL,
                description TEXT DEFAULT '',
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS ix_seal_images_seal_id ON seal_images(seal_id)")
        logger.info("Migration: ensured seal_images table exists")

        # 迁移：seal_images 加 thumbnail_path 列
        si_cols = {row[1] for row in conn.execute("PRAGMA table_info(seal_images)").fetchall()}
        if "thumbnail_path" not in si_cols:
            conn.execute("ALTER TABLE seal_images ADD COLUMN thumbnail_path TEXT DEFAULT ''")
            logger.info("Migration: added seal_images.thumbnail_path column")

        seal_cols = {row[1] for row in conn.execute("PRAGMA table_info(seals)").fetchall()}
        if "source" not in seal_cols:
            conn.execute("ALTER TABLE seals ADD COLUMN source TEXT DEFAULT ''")
            logger.info("Migration: added seals.source column")

        # 旧数据迁移：将 seals.images JSON 数组迁移到 seal_images 表
        old_seals = conn.execute(
            "SELECT id, images FROM seals WHERE images IS NOT NULL AND images != '' AND images != '[]'"
        ).fetchall()
        migrated = 0
        for seal_id, images_json in old_seals:
            try:
                img_list = json.loads(images_json)
                if isinstance(img_list, list) and len(img_list) > 0:
                    for i, path in enumerate(img_list):
                        if isinstance(path, str) and path.strip():
                            conn.execute(
                                "INSERT INTO seal_images (seal_id, path, sort_order) VALUES (?, ?, ?)",
                                (seal_id, path, i)
                            )
                            migrated += 1
                    conn.execute("UPDATE seals SET images = '[]' WHERE id = ?", (seal_id,))
            except (json.JSONDecodeError, TypeError):
                pass
        if migrated:
            logger.info("Migration: migrated %d old seal images to seal_images table", migrated)
        conn.commit()

        # ── artist_stats_cache 表 ──
        conn.execute("""
            CREATE TABLE IF NOT EXISTS artist_stats_cache (
                artist_id INTEGER PRIMARY KEY,
                stats_data TEXT NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
        """)
        logger.info("Migration: ensured artist_stats_cache table exists")
        conn.commit()
    finally:
        conn.close()


def _ensure_artist_columns():
    """幂等地为 artists 表添加新百科字段"""
    import sqlite3
    from app.core.config import get_settings
    s = get_settings()
    db_path = s.DATABASE_URL.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(artists)").fetchall()}
        new_cols = [
            ("banner_url", "TEXT DEFAULT ''"),
            ("summary", "TEXT DEFAULT ''"),
            ("nationality", "TEXT DEFAULT ''"),
            ("occupation", "TEXT DEFAULT ''"),
            ("main_achievements", "TEXT DEFAULT ''"),
            ("representative_works_text", "TEXT DEFAULT ''"),
            ("art_style", "TEXT DEFAULT ''"),
            ("influence", "TEXT DEFAULT ''"),
            ("historical_evaluation", "TEXT DEFAULT ''"),
            ("character_relations", "TEXT DEFAULT '[]'"),
            ("anecdotes", "TEXT DEFAULT '[]'"),
            ("art_chronology", "TEXT DEFAULT '[]'"),
            ("published_works", "TEXT DEFAULT '[]'"),
            ("gallery_images", "TEXT DEFAULT '[]'"),
            ("references", "TEXT DEFAULT '[]'"),
            ("verified", "INTEGER DEFAULT 0"),
        ]
        for col, col_type in new_cols:
            if col not in existing:
                escaped = f'[{col}]' if col in ('references',) else col
                conn.execute(f"ALTER TABLE artists ADD COLUMN {escaped} {col_type}")
                logger.info("Migration: added artists.%s", col)
        if "verified" not in existing:
            conn.execute("UPDATE artists SET verified = 1 WHERE verified = 0")
            logger.info("Migration: set all existing artists as verified")
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
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
