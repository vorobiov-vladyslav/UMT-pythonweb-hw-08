from datetime import date

from sqlalchemy.exc import IntegrityError

from database.models import Contact
from repository.contacts import ContactRepository
from services.exceptions import ContactNotFound, DuplicateEmail


class ContactService:
    def __init__(self, repo: ContactRepository) -> None:
        self.repo = repo

    def get(self, contact_id: int) -> Contact:
        contact = self.repo.get_by_id(contact_id)
        if contact is None:
            raise ContactNotFound
        return contact

    def create(self, payload: dict) -> Contact:
        try:
            return self.repo.add(payload)
        except IntegrityError as e:
            self.repo.db.rollback()
            raise DuplicateEmail from e

    def update(self, contact_id: int, payload: dict) -> Contact:
        contact = self.get(contact_id)
        try:
            return self.repo.update(contact, payload)
        except IntegrityError as e:
            self.repo.db.rollback()
            raise DuplicateEmail from e

    def delete(self, contact_id: int) -> None:
        contact = self.get(contact_id)
        self.repo.delete(contact)

    def list_or_search(
        self,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Contact]:
        any_filter = any((v or "").strip() for v in (first_name, last_name, email))
        if any_filter:
            return self.repo.search(
                first_name=first_name,
                last_name=last_name,
                email=email,
                skip=skip,
                limit=limit,
            )
        return self.repo.list(skip=skip, limit=limit)

    def upcoming_birthdays(self, today: date, days: int = 7) -> list[Contact]:
        return self.repo.birthdays_in_window(today, days)
