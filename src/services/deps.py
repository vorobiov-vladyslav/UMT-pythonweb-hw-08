from fastapi import Depends
from sqlalchemy.orm import Session

from database.db import get_db
from repository.contacts import ContactRepository
from services.contacts import ContactService


def get_contact_repository(db: Session = Depends(get_db)) -> ContactRepository:
    return ContactRepository(db)


def get_contact_service(
    repo: ContactRepository = Depends(get_contact_repository),
) -> ContactService:
    return ContactService(repo)
