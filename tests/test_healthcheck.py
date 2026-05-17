def test_healthcheck(client):
    response = client.get("/api/healthchecker")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
