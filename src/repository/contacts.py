from __future__ import annotations

from calendar import isleap
from datetime import date, timedelta
from typing import Any

from sqlalchemy import extract, select
from sqlalchemy.orm import Session

from database.models import Contact


class ContactRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, data: dict[str, Any]) -> Contact:
        contact = Contact(**data)
        self.db.add(contact)
        self.db.commit()
        self.db.refresh(contact)
        return contact

    def get_by_id(self, contact_id: int) -> Contact | None:
        return self.db.get(Contact, contact_id)

    def list(self, skip: int = 0, limit: int = 100) -> list[Contact]:
        stmt = select(Contact).order_by(Contact.id).offset(skip).limit(limit)
        return list(self.db.scalars(stmt).all())

    def search(
        self,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Contact]:
        stmt = select(Contact)
        if fn := (first_name or "").strip():
            stmt = stmt.where(Contact.first_name.ilike(f"%{fn}%"))
        if ln := (last_name or "").strip():
            stmt = stmt.where(Contact.last_name.ilike(f"%{ln}%"))
        if em := (email or "").strip():
            stmt = stmt.where(Contact.email.ilike(f"%{em}%"))
        stmt = stmt.order_by(Contact.id).offset(skip).limit(limit)
        return list(self.db.scalars(stmt).all())

    def birthdays_in_window(self, today: date, days: int = 7) -> list[Contact]:
        # Map every (month, day) in [today, today+days-1] to its distance from
        # today (0 = today). Real dates are used so year-wrap is automatic:
        # today=Dec 28, days=7 yields Dec 28..Jan 3 across two years.
        window_dates = [today + timedelta(days=i) for i in range(days)]
        md_to_pos = {(d.month, d.day): i for i, d in enumerate(window_dates)}

        # Feb 29 fallback: in a non-leap year, a window containing Feb 28
        # also matches Feb-29 birthdays (celebrated that year on Feb 28).
        for i, d in enumerate(window_dates):
            if d.month == 2 and d.day == 28 and not isleap(d.year):
                md_to_pos.setdefault((2, 29), i)
                break

        # Pre-filter in SQL by the months the window touches (≤3 for days≤30)
        # so we don't pull the whole table. Exact (month, day) match is Python.
        months = {m for m, _ in md_to_pos}
        stmt = (
            select(Contact)
            .where(extract("month", Contact.birthday).in_(months))
            .order_by(Contact.id)
        )
        candidates = self.db.scalars(stmt).all()

        matched = [
            (c, md_to_pos[(c.birthday.month, c.birthday.day)])
            for c in candidates
            if (c.birthday.month, c.birthday.day) in md_to_pos
        ]
        matched.sort(key=lambda pair: pair[1])
        return [c for c, _ in matched]

    def update(self, contact: Contact, data: dict[str, Any]) -> Contact:
        for field, value in data.items():
            setattr(contact, field, value)
        self.db.commit()
        self.db.refresh(contact)
        return contact

    def delete(self, contact: Contact) -> None:
        self.db.delete(contact)
        self.db.commit()
