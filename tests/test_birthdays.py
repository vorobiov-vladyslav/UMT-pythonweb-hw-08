from datetime import date

import pytest


def _payload(**overrides):
    base = {
        "first_name": "X",
        "last_name": "Y",
        "email": "x@x.com",
        "phone": "1",
        "birthday": date(1990, 1, 1),
        "additional_data": None,
    }
    base.update(overrides)
    return base


@pytest.fixture()
def seed_birthdays(contact_repository):
    """Helper: seed contacts with specific birthdays and return the repo."""

    def _seed(*birthdays):
        for i, b in enumerate(birthdays):
            contact_repository.add(_payload(birthday=b, email=f"c{i}@x.com"))
        return contact_repository

    return _seed


def test_birthday_today_included(seed_birthdays):
    today = date(2026, 6, 15)
    repo = seed_birthdays(date(1990, 6, 15))
    rows = repo.birthdays_in_window(today)
    assert len(rows) == 1


def test_birthday_today_plus_6_included(seed_birthdays):
    today = date(2026, 6, 15)
    repo = seed_birthdays(date(1990, 6, 21))
    rows = repo.birthdays_in_window(today)
    assert len(rows) == 1


def test_birthday_today_plus_7_excluded(seed_birthdays):
    today = date(2026, 6, 15)
    repo = seed_birthdays(date(1990, 6, 22))
    rows = repo.birthdays_in_window(today)
    assert len(rows) == 0


def test_year_wrap_dec_to_jan(seed_birthdays):
    today = date(2026, 12, 28)
    repo = seed_birthdays(date(1990, 1, 3))
    rows = repo.birthdays_in_window(today)
    assert len(rows) == 1


def test_feb_29_in_non_leap_year_matches_feb_28(seed_birthdays):
    today = date(2025, 2, 25)  # 2025 is non-leap; window covers Feb 28
    repo = seed_birthdays(date(2000, 2, 29))
    rows = repo.birthdays_in_window(today)
    assert len(rows) == 1


def test_feb_29_in_leap_year_matches_feb_29(seed_birthdays):
    today = date(2024, 2, 25)  # 2024 leap; window covers Feb 29
    repo = seed_birthdays(date(2000, 2, 29))
    rows = repo.birthdays_in_window(today)
    assert len(rows) == 1


def test_feb_29_not_matched_when_window_misses_feb_28(seed_birthdays):
    today = date(2025, 3, 1)  # window: Mar 1..Mar 7, no Feb 28
    repo = seed_birthdays(date(2000, 2, 29))
    rows = repo.birthdays_in_window(today)
    assert len(rows) == 0


def test_results_ordered_closest_first(seed_birthdays):
    today = date(2026, 6, 14)
    repo = seed_birthdays(
        date(1990, 6, 16),  # +2
        date(1990, 6, 14),  # 0
        date(1990, 6, 15),  # +1
    )
    rows = repo.birthdays_in_window(today)
    assert [(r.birthday.month, r.birthday.day) for r in rows] == [
        (6, 14),
        (6, 15),
        (6, 16),
    ]
