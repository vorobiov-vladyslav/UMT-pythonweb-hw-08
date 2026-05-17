from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from schemas import ContactCreate, ContactRead, ContactUpdate
from services.contacts import ContactService
from services.deps import get_contact_service
from services.exceptions import ContactNotFound, DuplicateEmail

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.post("", response_model=ContactRead, status_code=201)
def create_contact(
    payload: ContactCreate,
    service: ContactService = Depends(get_contact_service),
) -> ContactRead:
    try:
        contact = service.create(payload.model_dump())
    except DuplicateEmail:
        raise HTTPException(status_code=409, detail="Email already exists")
    return contact


@router.get("", response_model=list[ContactRead])
def list_contacts(
    first_name: str | None = Query(default=None),
    last_name: str | None = Query(default=None),
    email: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    service: ContactService = Depends(get_contact_service),
) -> list[ContactRead]:
    return service.list_or_search(
        first_name=first_name,
        last_name=last_name,
        email=email,
        skip=skip,
        limit=limit,
    )


@router.get("/birthdays", response_model=list[ContactRead])
def upcoming_birthdays(
    days: int = Query(default=7, ge=1, le=30),
    service: ContactService = Depends(get_contact_service),
) -> list[ContactRead]:
    return service.upcoming_birthdays(date.today(), days)


@router.get("/{contact_id}", response_model=ContactRead)
def get_contact(
    contact_id: int,
    service: ContactService = Depends(get_contact_service),
) -> ContactRead:
    try:
        return service.get(contact_id)
    except ContactNotFound:
        raise HTTPException(status_code=404, detail="Contact not found")


@router.put("/{contact_id}", response_model=ContactRead)
def update_contact(
    contact_id: int,
    payload: ContactUpdate,
    service: ContactService = Depends(get_contact_service),
) -> ContactRead:
    try:
        return service.update(contact_id, payload.model_dump())
    except ContactNotFound:
        raise HTTPException(status_code=404, detail="Contact not found")
    except DuplicateEmail:
        raise HTTPException(status_code=409, detail="Email already exists")


@router.delete("/{contact_id}", status_code=204)
def delete_contact(
    contact_id: int,
    service: ContactService = Depends(get_contact_service),
) -> None:
    try:
        service.delete(contact_id)
    except ContactNotFound:
        raise HTTPException(status_code=404, detail="Contact not found")
