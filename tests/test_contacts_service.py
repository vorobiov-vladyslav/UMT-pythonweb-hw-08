from datetime import date

import pytest

from services.exceptions import ContactNotFound, DuplicateEmail


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


def test_get_missing_raises_contact_not_found(contact_service):
    with pytest.raises(ContactNotFound):
        contact_service.get(999_999)


def test_create_duplicate_raises_duplicate_email(contact_service):
    contact_service.create(_payload(email="dup@x.com"))
    with pytest.raises(DuplicateEmail):
        contact_service.create(_payload(email="dup@x.com"))


def test_update_missing_raises_contact_not_found(contact_service):
    with pytest.raises(ContactNotFound):
        contact_service.update(999_999, _payload())


def test_update_duplicate_email_raises(contact_service):
    a = contact_service.create(_payload(email="a@x.com"))
    contact_service.create(_payload(email="b@x.com"))
    with pytest.raises(DuplicateEmail):
        contact_service.update(a.id, _payload(email="b@x.com"))


def test_delete_missing_raises_contact_not_found(contact_service):
    with pytest.raises(ContactNotFound):
        contact_service.delete(999_999)


def test_get_returns_contact_when_present(contact_service):
    c = contact_service.create(_payload())
    fetched = contact_service.get(c.id)
    assert fetched.email == "ada@example.com"
