from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError


def _payload(**overrides):
    base = {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "ada@example.com",
        "phone": "+1",
        "birthday": date(1815, 12, 10),
        "additional_data": None,
    }
    base.update(overrides)
    return base


def test_add_persists_row(contact_repository):
    c = contact_repository.add(_payload())
    assert c.id is not None
    assert c.created_at is not None
    assert c.updated_at is not None


def test_get_by_id_hit(contact_repository):
    c = contact_repository.add(_payload())
    assert contact_repository.get_by_id(c.id).email == "ada@example.com"


def test_get_by_id_miss(contact_repository):
    assert contact_repository.get_by_id(999_999) is None


def test_list_id_asc(contact_repository):
    a = contact_repository.add(_payload(email="a@x.com"))
    b = contact_repository.add(_payload(email="b@x.com"))
    c = contact_repository.add(_payload(email="c@x.com"))
    rows = contact_repository.list()
    assert [r.id for r in rows] == [a.id, b.id, c.id]


def test_list_pagination(contact_repository):
    contact_repository.add(_payload(email="a@x.com"))
    second = contact_repository.add(_payload(email="b@x.com"))
    contact_repository.add(_payload(email="c@x.com"))
    page = contact_repository.list(skip=1, limit=1)
    assert len(page) == 1
    assert page[0].id == second.id


def test_search_partial_ilike(contact_repository):
    contact_repository.add(_payload(first_name="Ada", email="a@x.com"))
    contact_repository.add(_payload(first_name="Alan", email="b@x.com"))
    matches = contact_repository.search(first_name="al")
    assert {c.first_name for c in matches} == {"Alan"}


def test_search_and_combines(contact_repository):
    contact_repository.add(_payload(first_name="Alan", last_name="Turing", email="a@x.com"))
    contact_repository.add(_payload(first_name="Alan", last_name="Kay", email="b@x.com"))
    matches = contact_repository.search(first_name="alan", last_name="tur")
    assert {c.last_name for c in matches} == {"Turing"}


def test_search_blank_filter_ignored(contact_repository):
    contact_repository.add(_payload(email="a@x.com"))
    contact_repository.add(_payload(email="b@x.com"))
    assert len(contact_repository.search(first_name="   ")) == 2


def test_update_mutates_fields(contact_repository):
    c = contact_repository.add(_payload())
    contact_repository.update(c, {"phone": "+999", "additional_data": "note"})
    fresh = contact_repository.get_by_id(c.id)
    assert fresh.phone == "+999"
    assert fresh.additional_data == "note"


def test_delete_removes_row(contact_repository):
    c = contact_repository.add(_payload())
    contact_repository.delete(c)
    assert contact_repository.get_by_id(c.id) is None


def test_duplicate_email_raises_integrity_error(contact_repository, db_session):
    contact_repository.add(_payload(email="dup@x.com"))
    with pytest.raises(IntegrityError):
        contact_repository.add(_payload(email="dup@x.com"))
    db_session.rollback()
