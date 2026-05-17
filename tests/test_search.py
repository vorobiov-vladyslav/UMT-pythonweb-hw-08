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


def _seed(client):
    client.post(
        "/api/contacts", json=_body(first_name="Ada", last_name="Lovelace", email="ada@x.com")
    )
    client.post(
        "/api/contacts", json=_body(first_name="Alan", last_name="Turing", email="alan@x.com")
    )
    client.post(
        "/api/contacts", json=_body(first_name="Grace", last_name="Hopper", email="grace@x.com")
    )


def test_filter_by_first_name_partial(client):
    _seed(client)
    rows = client.get("/api/contacts?first_name=al").json()
    assert {r["first_name"] for r in rows} == {"Alan"}


def test_filter_by_first_name_case_insensitive(client):
    _seed(client)
    rows = client.get("/api/contacts?first_name=AL").json()
    assert {r["first_name"] for r in rows} == {"Alan"}


def test_filter_by_email_substring(client):
    _seed(client)
    rows = client.get("/api/contacts?email=ada").json()
    assert {r["email"] for r in rows} == {"ada@x.com"}


def test_filter_first_and_last_combine_with_and(client):
    _seed(client)
    rows = client.get("/api/contacts?first_name=a&last_name=hopper").json()
    assert {r["first_name"] for r in rows} == {"Grace"}


def test_whitespace_filter_is_ignored(client):
    _seed(client)
    rows = client.get("/api/contacts?first_name=%20%20").json()
    assert len(rows) == 3


def test_pagination(client):
    _seed(client)
    rows = client.get("/api/contacts?skip=1&limit=1").json()
    assert len(rows) == 1
    assert rows[0]["first_name"] == "Alan"
