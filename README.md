# UMT-pythonweb-hw-08

REST API for managing personal contacts. FastAPI + SQLAlchemy 2.0 +
PostgreSQL 16, packaged with Docker Compose.

## API surface

| Method | Path                          | Notes                                                                |
|--------|-------------------------------|----------------------------------------------------------------------|
| POST   | `/api/contacts`               | Create. 201 / 409 (duplicate email) / 422.                           |
| GET    | `/api/contacts`               | List + search by `first_name`, `last_name`, `email` (ILIKE). 200/422. |
| GET    | `/api/contacts/birthdays`     | Upcoming birthdays in the next `days` (default 7, 1..30). 200/422.   |
| GET    | `/api/contacts/{id}`          | Get one. 200 / 404.                                                  |
| PUT    | `/api/contacts/{id}`          | Full update. 200 / 404 / 409 / 422.                                  |
| DELETE | `/api/contacts/{id}`          | 204 / 404.                                                           |
| GET    | `/api/healthchecker`          | `SELECT 1` round-trip.                                               |

Interactive docs at `/docs`; OpenAPI JSON at `/openapi.json`.

## Setup

### Mode A — full Docker (recommended for graders)

```bash
docker compose up -d --build
docker compose run --rm api uv run alembic upgrade head
xdg-open http://localhost:8000/docs        # or just open in your browser

docker compose logs -f api                 # tail logs
docker compose down                        # stop, keep DB volume
docker compose down -v                     # stop + drop DB volume
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
same is set via `ENV PYTHONPATH=/app/src`.)

## Examples

```bash
# create
curl -X POST http://localhost:8000/api/contacts \
  -H "Content-Type: application/json" \
  -d '{"first_name":"Ada","last_name":"Lovelace","email":"ada@example.com",
       "phone":"+1","birthday":"1815-12-10"}'

# list with search
curl "http://localhost:8000/api/contacts?first_name=ad&limit=10"

# upcoming birthdays in the next 14 days
curl "http://localhost:8000/api/contacts/birthdays?days=14"

# get / update / delete
curl http://localhost:8000/api/contacts/1
curl -X PUT http://localhost:8000/api/contacts/1 \
  -H "Content-Type: application/json" \
  -d '{"first_name":"Ada","last_name":"Lovelace","email":"ada@example.com",
       "phone":"+0","birthday":"1815-12-10"}'
curl -X DELETE http://localhost:8000/api/contacts/1
```

## Tests

```bash
uv run pytest
```

The first run creates the `hw08_test` database automatically (against the
`postgres` maintenance DB) and applies the schema via SQLAlchemy
`create_all`. Each test runs inside a SAVEPOINT-wrapped transaction that's
rolled back at teardown — repo-level commits don't leak between tests.

## Architecture

Four-layer separation, one file per layer (see SPEC §9):

```
src/api/contacts.py        — HTTP / Pydantic / HTTPException
src/services/contacts.py   — domain rules, exception translation
src/repository/contacts.py — SQLAlchemy queries
src/database/{db,models}.py — engine, session, ORM
src/schemas.py             — Pydantic in/out
src/conf/config.py         — pydantic-settings
```

The service stays Pydantic-free; the API hands it dicts via
`payload.model_dump()`. The repository is pure SQLAlchemy. Domain
exceptions (`ContactNotFound`, `DuplicateEmail`) live in
`src/services/exceptions.py` and the API layer translates them to HTTP
status codes.

## Tech stack

- **FastAPI** + Uvicorn (`[standard]` for `uvloop`/`httptools`/`watchfiles`)
- **SQLAlchemy 2.0** with typed `Mapped[...]` syntax, sync session
- **PostgreSQL 16** + `psycopg[binary]` v3
- **Pydantic v2** + `pydantic[email]` for `EmailStr`
- **Alembic** for migrations
- **pytest** + `httpx` (via `fastapi.testclient.TestClient`)
- **uv** for dependency management (lockfile committed)
- **ruff** + pre-commit hooks
