"""鉴权收口契约测试：seals 写操作与 content_analysis 读写策略。"""



def test_seals_list_public(client):
    assert client.get("/api/v1/seals").status_code == 200


def test_seal_create_anonymous_rejected(client):
    resp = client.post("/api/v1/seals", json={"name": "anon-seal"})
    assert resp.status_code in (401, 403)


def test_seal_create_reader_rejected(client, reader_token):
    resp = client.post("/api/v1/seals", headers={"Authorization": f"Bearer {reader_token}"},
                       json={"name": "reader-seal"})
    assert resp.status_code == 403


def test_seal_create_editor_ok(client, editor_token):
    resp = client.post("/api/v1/seals", headers={"Authorization": f"Bearer {editor_token}"},
                       json={"name": "editor-seal", "seal_type": "名章"})
    assert resp.status_code == 200, resp.text
    seal_id = resp.json().get("id") or resp.json().get("seal", {}).get("id")
    # 再验证修改也要鉴权
    resp2 = client.put(f"/api/v1/seals/{seal_id}", json={"name": "editor-seal-2"})
    assert resp2.status_code in (401, 403)


def test_seal_delete_needs_admin(client, editor_token):
    resp = client.post("/api/v1/seals", headers={"Authorization": f"Bearer {editor_token}"},
                       json={"name": "del-seal"})
    seal_id = resp.json().get("id") or resp.json().get("seal", {}).get("id")
    # editor 不能删（需 admin）
    resp2 = client.delete(f"/api/v1/seals/{seal_id}",
                          headers={"Authorization": f"Bearer {editor_token}"})
    assert resp2.status_code == 403


def test_seal_delete_admin_ok(client, admin_token):
    resp = client.post("/api/v1/seals", headers={"Authorization": f"Bearer {admin_token}"},
                       json={"name": "admin-del-seal"})
    seal_id = resp.json().get("id") or resp.json().get("seal", {}).get("id")
    resp2 = client.delete(f"/api/v1/seals/{seal_id}",
                          headers={"Authorization": f"Bearer {admin_token}"})
    assert resp2.status_code in (200, 204)


def test_content_analysis_reads_public(client):
    """2026-09-06 S6 取消：统计为公开站点数据，匿名可读。"""
    assert client.get("/api/v1/content-analysis/stats").status_code == 200
    assert client.get("/api/v1/content-analysis/artists").status_code == 200


def test_content_analysis_write_anonymous_rejected(client):
    """写操作（AI 解读/翻译/校对）仍需登录。"""
    resp = client.post("/api/v1/content-analysis/summary", json={})
    assert resp.status_code in (401, 403)


def test_content_analysis_with_token(client, reader_token):
    resp = client.get("/api/v1/content-analysis/stats",
                      headers={"Authorization": f"Bearer {reader_token}"})
    assert resp.status_code == 200
