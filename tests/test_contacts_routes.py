def _body(**overrides):
    base = {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "ada@example.com",
        "phone": "+1",
        "birthday": "1815-12-10",
        "additional_data": None,
    }
    base.update(overrides)
    return base


def test_post_create_returns_201(client):
    response = client.post("/api/contacts", json=_body())
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "ada@example.com"
    assert "id" in body
    assert "created_at" in body


def test_post_duplicate_email_returns_409(client):
    client.post("/api/contacts", json=_body())
    response = client.post("/api/contacts", json=_body(first_name="Other"))
    assert response.status_code == 409
    assert response.json()["detail"] == "Email already exists"


def test_post_bad_email_returns_422(client):
    response = client.post("/api/contacts", json=_body(email="nope"))
    assert response.status_code == 422


def test_post_bad_birthday_returns_422(client):
    response = client.post("/api/contacts", json=_body(birthday="not-a-date"))
    assert response.status_code == 422


def test_post_missing_field_returns_422(client):
    body = _body()
    del body["last_name"]
    response = client.post("/api/contacts", json=body)
    assert response.status_code == 422


def test_get_by_id_returns_200(client):
    created = client.post("/api/contacts", json=_body()).json()
    response = client.get(f"/api/contacts/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_by_id_missing_returns_404(client):
    response = client.get("/api/contacts/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Contact not found"


def test_put_returns_200_and_updates(client):
    created = client.post("/api/contacts", json=_body()).json()
    response = client.put(
        f"/api/contacts/{created['id']}",
        json=_body(first_name="Augusta"),
    )
    assert response.status_code == 200
    assert response.json()["first_name"] == "Augusta"


def test_put_missing_returns_404(client):
    response = client.put("/api/contacts/999999", json=_body())
    assert response.status_code == 404


def test_put_duplicate_email_returns_409(client):
    a = client.post("/api/contacts", json=_body(email="a@x.com")).json()
    client.post("/api/contacts", json=_body(email="b@x.com"))
    response = client.put(f"/api/contacts/{a['id']}", json=_body(email="b@x.com"))
    assert response.status_code == 409


def test_delete_returns_204_then_404(client):
    created = client.post("/api/contacts", json=_body()).json()
    response = client.delete(f"/api/contacts/{created['id']}")
    assert response.status_code == 204
    response2 = client.delete(f"/api/contacts/{created['id']}")
    assert response2.status_code == 404
