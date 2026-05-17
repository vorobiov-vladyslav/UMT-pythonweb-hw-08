# UMT-pythonweb-hw-08 — Specification

## 1. Goal

Build a REST API for storing and managing personal contacts. The API must
expose CRUD over a `contacts` resource, support search by name / email, and
expose an "upcoming birthdays" view.

This is a learning exercise; scope is the homework rubric (15 pts) plus a
small test suite, Docker packaging, and a service-oriented layering — nothing
beyond that.

## 2. Tech stack (fixed)

| Concern         | Choice                                                       |
|-----------------|--------------------------------------------------------------|
| Web framework   | **FastAPI**                                                  |
| ORM             | **SQLAlchemy 2.0** (typed `Mapped[...]` style, sync session) |
| Database        | **PostgreSQL 16** (run via `docker compose`)                 |
| DB driver       | `psycopg[binary]` v3                                         |
| Validation      | **Pydantic v2** (with `pydantic[email]` for `EmailStr`)      |
| Settings        | `pydantic-settings` (`.env` loader)                          |
| Migrations      | Alembic                                                      |
| Server          | Uvicorn                                                      |
| Containers      | Docker + Docker Compose (Postgres **and** API both in Docker)|
| Tests           | pytest, httpx (via `fastapi.testclient.TestClient`)          |
| Dependency mgmt | `uv` (lockfile committed)                                    |
| Docs            | Swagger/OpenAPI auto-served at `/docs` and `/redoc`          |
| Python          | `>=3.10` (image: `python:3.12-slim`)                         |

Repo name on GitHub: **`UMT-pythonweb-hw-08`** (public).

## 3. Data model

Single table `contacts`:

| Column            | Type            | Constraints                               | Notes                            |
|-------------------|-----------------|-------------------------------------------|----------------------------------|
| `id`              | `INTEGER`       | PK, autoincrement                         |                                  |
| `first_name`      | `VARCHAR(50)`   | NOT NULL                                  |                                  |
| `last_name`       | `VARCHAR(50)`   | NOT NULL                                  |                                  |
| `email`           | `VARCHAR(120)`  | NOT NULL, UNIQUE, indexed                 | format-validated by Pydantic     |
| `phone`           | `VARCHAR(20)`   | NOT NULL                                  | free-form string, not unique     |
| `birthday`        | `DATE`          | NOT NULL                                  | stored as `date`, not `datetime` |
| `additional_data` | `TEXT`          | NULL                                      | optional notes                   |
| `created_at`      | `TIMESTAMP`     | NOT NULL, server default `now()`          | bookkeeping                      |
| `updated_at`      | `TIMESTAMP`     | NOT NULL, server default + on-update      | bookkeeping                      |

Index for the upcoming-birthdays query is **not** required (dataset is small);
a sequential scan with a `(month, day)` predicate is acceptable.

## 4. Pydantic schemas

```text
ContactBase
  first_name: str        (1..50, stripped, non-empty)
  last_name:  str        (1..50, stripped, non-empty)
  email:      EmailStr   (Pydantic-validated)
  phone:      str        (1..20)
  birthday:   date       (must parse as ISO date; reject pure strings)
  additional_data: str | None  (<=500 chars)

ContactCreate(ContactBase): all required.
ContactUpdate(ContactBase): all required (full-replacement PUT).
ContactRead(ContactBase):   adds `id: int`, `created_at`, `updated_at`.
                            `model_config = ConfigDict(from_attributes=True)`
```

`birthday` MUST be typed as `datetime.date` so Pydantic rejects "not a real
date" strings — this is explicitly worth 0.5 pts in the rubric.

All schemas live in a single file `src/schemas.py` (small enough to not need
a package; can be split later if more aggregates are added).

## 5. API surface

Base path: `/api`. All endpoints documented in OpenAPI.

| Method | Path                          | Purpose                                      | Success | Errors           |
|--------|-------------------------------|----------------------------------------------|---------|------------------|
| POST   | `/api/contacts`               | Create contact                               | 201     | 409 (dup email), 422 |
| GET    | `/api/contacts`               | List + search (query params, see §6)         | 200     | 422              |
| GET    | `/api/contacts/birthdays`     | Upcoming-birthdays window (see §7)           | 200     | 422              |
| GET    | `/api/contacts/{contact_id}`  | Get one                                      | 200     | 404              |
| PUT    | `/api/contacts/{contact_id}`  | Full update                                  | 200     | 404, 409, 422    |
| DELETE | `/api/contacts/{contact_id}`  | Delete                                       | 204     | 404              |

Route order matters: `/contacts/birthdays` MUST be declared before
`/contacts/{contact_id}` so FastAPI doesn't try to parse `"birthdays"` as an
int id.

Health endpoint `GET /api/healthchecker` is included (does a `SELECT 1`)
for sanity but is not part of the rubric.

## 6. Search (`GET /api/contacts`)

Optional query params, all combined with **AND**:

- `first_name: str | None` — case-insensitive `ILIKE %value%`
- `last_name:  str | None` — case-insensitive `ILIKE %value%`
- `email:      str | None` — case-insensitive `ILIKE %value%`
- `skip:       int = 0` (≥0)
- `limit:      int = 100` (1..500)

Empty/whitespace strings are treated as "no filter" (trim, then ignore if
empty). Result is ordered by `id ASC` for determinism.

## 7. Upcoming birthdays (`GET /api/contacts/birthdays`)

Returns contacts whose birthday falls **within the next 7 days, inclusive of
today** — i.e. window `[today, today+6]` covering 7 distinct calendar days.

Comparison is **year-agnostic** (compare `(month, day)` only). The window may
cross a year boundary (e.g. today = Dec 28 ⇒ window covers Dec 28..Jan 03);
the implementation must handle that.

Suggested SQL pattern:

```sql
-- pseudocode
WHERE to_char(birthday, 'MM-DD') BETWEEN :start AND :end
   OR (year_wrap AND to_char(birthday, 'MM-DD') >= :start)
   OR (year_wrap AND to_char(birthday, 'MM-DD') <= :end)
```

Optional query param `days: int = 7` (1..30) for tweaking the window — useful
during testing but not required by the rubric.

Result ordered by upcoming birthday (closest first). Feb 29 birthdays are
matched against Feb 28 in non-leap years.

## 8. Errors & response shapes

- 404 → `{"detail": "Contact not found"}`
- 409 → `{"detail": "Email already exists"}` (raised on `IntegrityError`
  for the unique-email constraint, mapped explicitly — don't leak the raw
  psycopg error)
- 422 → FastAPI default Pydantic error envelope (untouched)

## 9. Architecture / layering

The app uses an explicit 4-layer separation. Even with a single `Contact`
aggregate this is overkill in pure LOC terms, but the layering was the
topic of the lecture preceding this homework, so it's set up properly to
demonstrate the pattern.

```
HTTP request
   │
   ▼
┌──────────────┐    Pydantic in/out, status codes, HTTPException
│  API layer   │    src/api/contacts.py
└──────┬───────┘
       │ calls
       ▼
┌──────────────┐    business rules, domain exceptions, orchestration
│ Service layer│    src/services/contacts.py  (ContactService)
└──────┬───────┘
       │ calls
       ▼
┌──────────────┐    SQLAlchemy queries only, no HTTP / no Pydantic
│ Repository   │    src/repository/contacts.py  (ContactRepository)
└──────┬───────┘
       │
       ▼
┌──────────────┐    engine, SessionLocal, ORM models
│   Database   │    src/database/db.py + src/database/models.py
└──────────────┘
```

### Layer responsibilities

**API layer (`src/api/contacts.py`)** — HTTP / presentation concerns only.
- Parse path / query / body via FastAPI dependencies.
- Call the service.
- Translate domain exceptions to `HTTPException` with the right status code.
- Set `response_model` + `status_code`; return Pydantic schemas.
- No DB sessions, no SQL, no business rules.

**Service layer (`src/services/contacts.py`)** — business / domain logic.
- One service per aggregate: `ContactService`.
- Constructor takes a `ContactRepository` (injected via FastAPI `Depends`).
- Validates invariants (e.g. "email must be unique" → catch repo's
  `IntegrityError` and raise `DuplicateEmail`).
- Composes repository calls if needed; returns ORM objects or primitives.
- Does **not** know about HTTP or Pydantic schemas.

**Repository layer (`src/repository/contacts.py`)** — data access only.
- One repo per aggregate: `ContactRepository`.
- Constructor takes a `Session`.
- Methods: `get_by_id`, `list`, `search`, `birthdays_in_window`,
  `add`, `update`, `delete`.
- Pure SQLAlchemy; no business rules, no HTTP concepts.

**Database / Models / Schemas** — engine + session factory + `Contact` ORM
model + Pydantic boundary types. No logic.

### Domain exceptions

`src/services/exceptions.py` defines:
- `ContactNotFound` → mapped to 404 in API layer.
- `DuplicateEmail`  → mapped to 409 in API layer.

API handlers import these and translate. Services raise these. Repository
raises only raw SQLAlchemy errors (which the service translates).

### Dependency injection

Two FastAPI dependency factories live in `src/services/deps.py`:

```python
def get_contact_repository(db: Session = Depends(get_db)) -> ContactRepository:
    return ContactRepository(db)

def get_contact_service(
    repo: ContactRepository = Depends(get_contact_repository),
) -> ContactService:
    return ContactService(repo)
```

API handlers depend only on `get_contact_service`. Tests can override either:
- `get_db` (default) → exercises the full stack against the test DB.
- `get_contact_service` → swap in a fake when isolating API logic.

## 10. Project layout

Layout follows the lecture's structure: `main.py` at the project root,
`src/` as the source root with per-layer subdirectories.

```
UMT-pythonweb-hw-08/
├── main.py                           # entry point — FastAPI app, router include, lifespan
├── pyproject.toml                    # uv-managed; pytest pythonpath = ["src"]
├── uv.lock
├── alembic.ini                       # prepend_sys_path = .:src
├── docker-compose.yml                # postgres + api services
├── Dockerfile
├── .dockerignore
├── .env.example                      # DATABASE_URL template
├── .gitignore
├── README.md
├── src/
│   ├── api/
│   │   ├── __init__.py
│   │   └── contacts.py               # APIRouter; thin handlers (presentation layer)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── contacts.py               # ContactService (business logic)
│   │   ├── deps.py                   # FastAPI Depends factories
│   │   └── exceptions.py             # ContactNotFound, DuplicateEmail
│   ├── repository/
│   │   ├── __init__.py
│   │   └── contacts.py               # ContactRepository (data access)
│   ├── database/
│   │   ├── __init__.py
│   │   ├── db.py                     # engine, SessionLocal, Base, get_db
│   │   └── models.py                 # Contact ORM model
│   ├── conf/
│   │   ├── __init__.py
│   │   └── config.py                 # Settings (pydantic-settings)
│   └── schemas.py                    # Pydantic Contact{Base,Create,Update,Read}
├── alembic/
│   ├── env.py
│   └── versions/
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_contacts_repository.py
    ├── test_contacts_service.py
    ├── test_contacts_routes.py
    ├── test_search.py
    └── test_birthdays.py
```

### Layout notes

- **`main.py` lives at the project root**, not inside `src/`. It imports
  from the layers (`from api.contacts import router`, etc.) and is the
  uvicorn entry point: `uvicorn main:app`.
- **`src/` is the source root**, not a Python package itself. It needs to be
  on `sys.path` so that `api`, `services`, `repository`, `database`, `conf`,
  and `schemas` resolve as top-level modules. Three places configure that:
  - **Runtime**: `PYTHONPATH=src` (set in `Dockerfile` via `ENV` and in the
    Mode B host run command).
  - **Tests**: `pyproject.toml` → `[tool.pytest.ini_options] pythonpath = ["src"]`.
  - **Alembic**: `alembic.ini` → `prepend_sys_path = .:src`.
- **One file per entity per layer**. With a single `Contact` aggregate that
  means one `contacts.py` per layer; mirrors the lecture's `notes.py` /
  `tags.py` per-entity convention and scales naturally.
- **`schemas.py` stays a single file** as the lecture suggests for small
  schema surface area; would split into `schemas/contacts.py` once we have
  multiple aggregates.

## 11. Configuration

Configuration lives in `src/conf/config.py` using **`pydantic-settings`**.
A single `Settings` class loads `DATABASE_URL` from env (or `.env` file)
and exposes a module-level `settings` instance:

```python
# src/conf/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:hw08secret@localhost:5432/hw08"
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
```

`src/database/db.py` consumes `settings.database_url` to build the engine —
no other module reads env vars directly. `.env.example` is committed; `.env`
is gitignored.

In Docker the value is supplied via `docker-compose.yml` env (`@postgres`
hostname instead of `localhost`); pydantic-settings picks it up the same way.

## 12. Docker packaging

### Dockerfile

- Base image: `python:3.12-slim`.
- Install `uv` (single layer).
- Copy `pyproject.toml` + `uv.lock`, run `uv sync --frozen --no-install-project`
  to cache deps.
- Copy `main.py`, `src/`, `alembic/`, `alembic.ini` (use `.dockerignore` to
  exclude `.venv/`, `__pycache__/`, `tests/`, `.git/`).
- `WORKDIR /app`, `EXPOSE 8000`, `ENV PYTHONPATH=/app/src` so the bare
  imports in `main.py` resolve.
- Default `CMD` runs uvicorn:
  `uv run uvicorn main:app --host 0.0.0.0 --port 8000`.
- No reload flag in the default CMD; compose overrides it for dev.

### docker-compose.yml

Two services:

1. **`postgres`** — `postgres:16`, named volume `hw08-pgdata`, port `5432`,
   the existing healthcheck pattern from hw-06.
2. **`api`** — `build: .`, `ports: 8000:8000`, `depends_on: postgres
   (condition: service_healthy)`, env `DATABASE_URL=...@postgres:5432/hw08`.
   For dev convenience, mount `./main.py:/app/main.py` and `./src:/app/src`,
   then override `command` to add `--reload`. Live reload still works while
   exercising the container path.

### Migrations

Run as a one-shot inside the `api` image:

```bash
docker compose run --rm api uv run alembic upgrade head
```

Do **not** run migrations from the app's lifespan startup — keeps app boot
deterministic.

## 13. Tests

### Stack

- `pytest` + `pytest-asyncio` (the latter only if any async path is added;
  default suite is sync via `TestClient`).
- `httpx` (transitive via `fastapi.testclient.TestClient`).
- No `factory_boy` / `freezegun` — keep deps small.

### sys.path

`pyproject.toml` adds:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
addopts = "-ra --strict-markers"
```

so tests can `from database.db import get_db`, `from services.contacts import
ContactService`, etc., without manual `sys.path` edits.

### Test database

- Separate database `hw08_test` on the same Postgres instance.
- A session-scoped fixture issues `CREATE DATABASE` if missing (against the
  `postgres` maintenance DB), then `Base.metadata.create_all()` builds the
  schema. Mirrors hw-06.
- Each test runs inside a transaction rolled back at teardown
  (function-scoped fixture overriding `get_db` to yield a Session bound to a
  savepoint-wrapped connection). Tests stay isolated and fast.

### Fixtures (`conftest.py`)

- `engine` (session) — pointed at `hw08_test`.
- `tables` (session, autouse) — `create_all` once, `drop_all` at end.
- `db_session` (function) — connection + nested transaction + Session.
- `client` (function) — `TestClient(app)` with `app.dependency_overrides[get_db]`
  pointing at `db_session`.
- `contact_repository` (function) — `ContactRepository(db_session)`.
- `contact_service` (function) — `ContactService(contact_repository)`.

### What to test

The layering creates three natural test seams. Aim for ≥80% coverage of
`src/api/`, `src/services/`, `src/repository/`.

`test_contacts_repository.py` — pure data access:
- `add` persists a row; `get_by_id` returns it; missing id returns `None`.
- `list` returns rows in `id ASC` order.
- `search` matches `ILIKE` partial, AND-combines filters, ignores blanks.
- `birthdays_in_window` returns expected rows for several `(today, days)`
  pairs (today, today+6, today+7, year-wrap, Feb-29 fallback).
- `update` mutates fields; `delete` removes the row.
- Duplicate email → repository surfaces SQLAlchemy `IntegrityError`.

`test_contacts_service.py` — domain rules:
- `get` raises `ContactNotFound` for missing id.
- `update` / `delete` raise `ContactNotFound` for missing id.
- `create` with a duplicate email raises `DuplicateEmail` (not the raw
  SQLAlchemy error).
- Otherwise the service is a thin pass-through; tests stay short.

`test_contacts_routes.py` — full stack via `TestClient`:
- POST creates and returns 201 + body with new `id`.
- POST with duplicate email → 409 with `"Email already exists"`.
- POST with bad email / missing fields / non-date birthday → 422.
- GET `/contacts/{id}` returns 200 / 404.
- PUT updates and returns 200; 404 for unknown id.
- DELETE returns 204 and the row is gone; 404 for unknown id.

`test_search.py` — through `TestClient`:
- Filter by `first_name` (partial, case-insensitive) returns matches only.
- Filter by `email` substring works.
- Combined `first_name` + `last_name` AND together.
- Whitespace-only filter is ignored.
- `skip` / `limit` paginate as expected.

`test_birthdays.py` — through `TestClient`, parameterizing the `today`
helper rather than mocking `date.today()`:
- Birthday on `today` is included.
- Birthday on `today + 6` is included.
- Birthday on `today + 7` is excluded.
- Year-wrap: today = Dec 28, birthday Jan 3 is included.
- Feb 29 birthday matches Feb 28 in a non-leap-year window covering Feb 28.

### Running tests

Host:

```bash
uv run pytest
```

Docker (optional one-shot):

```bash
docker compose run --rm api uv run pytest
```

The test suite must NOT depend on the dev `hw08` database state.

## 14. Setup & run (target UX)

### Mode A — full Docker (recommended for graders)

```bash
docker compose up -d --build
docker compose run --rm api uv run alembic upgrade head
xdg-open http://localhost:8000/docs

docker compose logs -f api
docker compose down            # keep DB volume
docker compose down -v         # nuke DB volume
```

### Mode B — hybrid (Postgres in Docker, API on host, fastest dev loop)

```bash
docker compose up -d postgres
uv sync
uv run alembic upgrade head
PYTHONPATH=src uv run uvicorn main:app --reload
```

`PYTHONPATH=src` is required because `main.py` lives at the project root and
imports `api`, `services`, etc. as top-level modules. (Inside Docker the
same is set via `ENV PYTHONPATH=/app/src`.) Both modes must work; README
documents both.

## 15. Acceptance criteria — mapped to the 15-point rubric

| Pts | Criterion                                                     | Evidence in this spec |
|-----|---------------------------------------------------------------|------------------------|
| 1.5 | FastAPI project starts and answers requests                   | §14, §5                |
| 1.5 | Swagger/OpenAPI shows all endpoints                           | §2 (auto), §5          |
| 1.5 | PostgreSQL is used and connected                              | §2, §11, §14           |
| 2.0 | `Contact` model has all required fields                       | §3                     |
| 0.5 | DB access via SQLAlchemy sessions/queries (no raw SQL ad-hoc) | §9, §10                |
| 1.5 | Pydantic schemas for create/update with correct types         | §4                     |
| 0.5 | `birthday` validated as a real `date`                         | §4                     |
| 1.0 | Create contact                                                | §5 POST                |
| 1.0 | List all contacts                                             | §5 GET list            |
| 1.0 | Get one by id                                                 | §5 GET by id           |
| 1.0 | Update contact                                                | §5 PUT                 |
| 1.0 | Delete contact                                                | §5 DELETE              |
| 0.5 | Search by first/last/email via query params                   | §6                     |
| 0.5 | Birthdays in the next 7 days                                  | §7                     |
| **15** | **Total**                                                  |                        |

The 4-layer architecture (§9), Docker packaging (§12), and tests (§13) are
not separately graded but harden the implementation against regressions
and reflect the lecture content this HW follows.

## 16. Out of scope

- Authentication, authorization, rate limiting (these belong to later HW).
- Async SQLAlchemy / asyncpg — sync stack is sufficient and simpler.
- Pagination metadata wrapper (just `skip`/`limit` query params).
- Soft deletes, audit trail beyond `created_at`/`updated_at`.
- Frontend, deployment to a public host, CI/CD.
- Seed/fixture data for the dev DB (a manual `POST /contacts` from Swagger
  is enough to demo).
- Generic / abstract base repository or service classes — the layering
  exists to demonstrate the pattern, not to build a framework.

## 17. Submission checklist

- [ ] Public GitHub repo `UMT-pythonweb-hw-08`.
- [ ] All commits pushed to `main`.
- [ ] `docker compose up -d --build` works from a clean clone.
- [ ] `uv run pytest` is green.
- [ ] `README.md` shows setup steps for both modes and a link to `/docs`.
- [ ] Zip the working tree as `ДЗ8_ПІБ.zip` and upload to LMS along with the
      repo URL.
