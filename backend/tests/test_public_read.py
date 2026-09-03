"""公开只读端点契约测试：artists / steles / tiba 只读面。"""



def test_artists_list_public(client):
    assert client.get("/api/v1/artists").status_code == 200


def test_artists_create_anonymous_rejected(client):
    resp = client.post("/api/v1/artists", json={"name": "anon"})
    assert resp.status_code in (401, 403)


def test_steles_list_public(client):
    resp = client.get("/api/v1/steles")
    assert resp.status_code == 200


def test_tiba_results_public_read(client):
    resp = client.get("/api/v1/tiba/results")
    assert resp.status_code in (200, 400)


def test_tiba_result_missing_id(client):
    resp = client.get("/api/v1/tiba/result/nonexistent-id")
    assert resp.status_code in (404, 400, 200)
