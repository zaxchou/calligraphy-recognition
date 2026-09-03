"""
v2.0 测试安全网 — API 契约测试夹具。

关键点：必须在导入 app 之前设置 DATA_DIR 环境变量，
使应用建表/迁移指向临时目录中的全新 SQLite，而非开发库。
"""
import os
import sqlite3
import tempfile

# ── 在任何 app 模块导入之前 ─────────────────────────────────────
_TEST_DATA_DIR = tempfile.mkdtemp(prefix="molin-test-data-")
os.environ["DATA_DIR"] = _TEST_DATA_DIR
os.environ.setdefault("ENVIRONMENT", "test")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402  (导入即建表+迁移，指向临时 DATA_DIR)
from app.core.config import get_settings  # noqa: E402

settings = get_settings()
DB_PATH = settings.DATABASE_URL.replace("sqlite:///", "")

client = TestClient(app)


def _db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    return conn


def _register_and_get_token(username: str, password: str = "test-pass-123", role: str = None):
    """注册一个用户并返回 (token, user_id)；role 非空时直接改库提权。"""
    resp = client.post("/api/v1/auth/register", json={
        "username": username, "password": password,
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    token, user_id = data["token"], data["user_id"]

    if role:
        conn = _db()
        conn.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
        conn.commit()
        conn.close()
        # 重新登录以拿到新角色的 token
        resp = client.post("/api/v1/auth/login-password", json={
            "account": username, "password": password,
        })
        assert resp.status_code == 200, resp.text
        token = resp.json()["token"]

    return token, user_id


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def reader_token():
    token, _ = _register_and_get_token("reader_user")
    return token


@pytest.fixture(scope="session")
def editor_token():
    token, _ = _register_and_get_token("editor_user", role="editor")
    return token


@pytest.fixture(scope="session")
def admin_token():
    token, _ = _register_and_get_token("admin_user", role="super_admin")
    return token
