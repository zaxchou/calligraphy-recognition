"""认证流契约测试：注册 / 密码登录 / 资料 / 改密 / 验证码。"""
from tests.conftest import _register_and_get_token


def test_site_settings_public(client):
    resp = client.get("/api/v1/site-settings")
    assert resp.status_code == 200


def test_register_username_password(client):
    resp = client.post("/api/v1/auth/register", json={
        "username": "contract_user", "password": "secret-123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["token"] and data["user_id"] > 0
    assert data["role"] == "reader"


def test_register_duplicate_username_rejected(client):
    body = {"username": "dup_user", "password": "secret-123"}
    assert client.post("/api/v1/auth/register", json=body).status_code == 200
    resp = client.post("/api/v1/auth/register", json=body)
    assert resp.status_code in (400, 409)


def test_login_password_ok(client):
    client.post("/api/v1/auth/register", json={
        "username": "pwd_login_user", "password": "secret-123"})
    resp = client.post("/api/v1/auth/login-password", json={
        "account": "pwd_login_user", "password": "secret-123"})
    assert resp.status_code == 200
    assert resp.json()["token"]


def test_login_password_wrong_rejected(client):
    resp = client.post("/api/v1/auth/login-password", json={
        "account": "pwd_login_user", "password": "wrong-password"})
    assert resp.status_code == 401


def test_profile_requires_token(client):
    assert client.get("/api/v1/auth/profile").status_code in (401, 403)


def test_profile_with_token(client):
    token, _ = _register_and_get_token(client, "profile_user")
    resp = client.get("/api/v1/auth/profile", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "reader"


def test_change_password_flow(client):
    token, _ = _register_and_get_token(client, "chpwd_user", password="old-pass-123")
    # 已有密码时必须提供旧密码
    resp = client.put("/api/v1/auth/password", headers={"Authorization": f"Bearer {token}"},
                      json={"password": "new-pass-456"})
    assert resp.status_code == 400
    resp = client.put("/api/v1/auth/password", headers={"Authorization": f"Bearer {token}"},
                      json={"password": "new-pass-456", "old_password": "old-pass-123"})
    assert resp.status_code == 200
    # 旧密码失效
    assert client.post("/api/v1/auth/login-password", json={
        "account": "chpwd_user", "password": "old-pass-123"}).status_code == 401
    # 新密码可用
    assert client.post("/api/v1/auth/login-password", json={
        "account": "chpwd_user", "password": "new-pass-456"}).status_code == 200


def test_send_code_no_longer_accepts_fixed_code(client):
    """mock 关停后：发送验证码成功，但固定码 123456 不能通过登录。"""
    assert client.post("/api/v1/auth/send-code", json={"phone": "13900001111"}).status_code == 200
    resp = client.post("/api/v1/auth/login", json={"phone": "13900001111", "code": "123456"})
    assert resp.status_code in (400, 401)


def test_wechat_login_removed(client):
    """微信登录已整体移除（v2.0 安全整改）。"""
    resp = client.post("/api/v1/auth/wechat-login", json={"code": "anything"})
    assert resp.status_code == 404


def test_forged_token_rejected(client):
    resp = client.get("/api/v1/auth/profile", headers={
        "Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.fake.sig"})
    assert resp.status_code == 401
