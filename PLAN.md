# UMT-pythonweb-hw-08 — Implementation Plan

This plan turns `SPEC.md` into small, reviewable steps. Each step is sized so
that the diff is easy to read in one sitting; each one has a short "FastAPI
note" explaining the framework concept introduced, on the assumption that
you know web development but not FastAPI specifically.

## How to use this plan

- Tick the box `[x]` when the step is reviewed, committed, and pushed.
- One commit per step is the recommended cadence; commit message can be the
  step title.
- Don't skip ahead — earlier steps set up context (sys.path, models, fixtures)
  that later steps rely on.
- If a step's diff feels too big once you start, split it: nothing forces a
  one-to-one mapping between this list and your commits.

## Decisions (locked in)

- Commit-per-step cadence: **yes**.
- Tests in one dedicated phase, with one early TestClient sanity step: **yes**.
- Pre-commit linters (ruff via pre-commit): **yes**, set up before any code
  is written (step 0.4).

---

## Phase 0 — Repository bootstrap

### [x] 0.1 Create the public GitHub repo and initialize the local working tree

- Create a public GitHub repo named `UMT-pythonweb-hw-08`.
- `git init` inside the existing local directory (`SPEC.md` already lives
  there); set `origin` to the new repo URL.
- First commit: just `SPEC.md` + `PLAN.md`.

**Why**: the submission needs a public repo, and pushing early means every
later step is reviewable on GitHub.

### [x] 0.2 Add `.gitignore`, `.env.example`

- `.gitignore`: `.venv/`, `__pycache__/`, `*.pyc`, `.env`, `.pytest_cache/`,
  `dist/`, `*.egg-info/`.
- `.env.example`: `DATABASE_URL=postgresql+psycopg://postgres:hw08secret@localhost:5432/hw08`

**Why**: `.env.example` documents the only env var the app reads; copy it to
`.env` for local runs (not committed).

### [x] 0.3 Create `pyproject.toml` and lock dependencies

- Add deps: `fastapi`, `uvicorn[standard]`, `sqlalchemy>=2.0,<3`,
  `psycopg[binary]>=3.1`, `alembic>=1.13`, `pydantic>=2`, `pydantic[email]`,
  `pydantic-settings`.
- Dev deps (`[dependency-groups] dev`): `pytest>=8`, `httpx`, `ruff`, `pre-commit`.
- Add `[tool.pytest.ini_options]` with `testpaths = ["tests"]`,
  `pythonpath = ["src"]`, `addopts = "-ra --strict-markers"`.
- Run `uv sync` → produces `.venv/` and `uv.lock`.

**FastAPI note**: `uvicorn` is the ASGI server; `[standard]` pulls in
`uvloop`, `httptools`, and `watchfiles` (needed for `--reload`). FastAPI
itself is a thin layer over Starlette + Pydantic.

### [x] 0.4 Configure ruff and install pre-commit hooks

- Add a `[tool.ruff]` block to `pyproject.toml`: `line-length = 100`,
  `target-version = "py312"`. Add `[tool.ruff.lint]` enabling at least the
  default rules plus `I` (import sort).
- Create `.pre-commit-config.yaml` with two hooks: `ruff` (`ruff check --fix`)
  and `ruff-format`. Use the `astral-sh/ruff-pre-commit` repo with a pinned
  rev.
- Run `uv run pre-commit install` to wire the git hook.
- Run `uv run pre-commit run --all-files` once — should pass on the empty
  tree (it'll touch `pyproject.toml` formatting at most).

**Why up front**: every later commit lands already lint-clean and
import-sorted, so review never gets distracted by stylistic noise. Not
FastAPI-specific — ruff is the lint+format tool; pre-commit runs hooks on
`git commit`.

### [x] 0.5 Create the empty package skeleton

- Make every directory from SPEC §10 with an `__init__.py`:
  `src/api/`, `src/services/`, `src/repository/`, `src/database/`,
  `src/conf/`, `tests/`. Leave the layer files empty for now.
- Create stub `main.py` at the project root with just
  `from fastapi import FastAPI; app = FastAPI()`.

**Why**: makes the layout real and importable from the very first step. You
can run `PYTHONPATH=src uv run uvicorn main:app` and get a 404-only app
already — confirms the toolchain works before adding any feature.

---

## Phase 1 — Configuration and database foundation

### [x] 1.1 Implement `src/conf/config.py` (Settings class)

- `Settings(BaseSettings)` with one field `database_url: str` (default from
  SPEC §11), `model_config = SettingsConfigDict(env_file=".env", extra="ignore")`.
- Module-level `settings = Settings()`.

**FastAPI note**: `pydantic-settings` is the canonical way to load config —
type-validated, supports `.env` files, and stays a single source of truth.
Other modules import `settings` and never touch `os.environ` directly.

### [x] 1.2 Implement `src/database/db.py` (engine, SessionLocal, Base, `get_db`)

- `engine = create_engine(settings.database_url, future=True)`.
- `SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)`.
- `class Base(DeclarativeBase): pass`.
- `def get_db()` generator yielding a `SessionLocal()` and closing it in
  `finally:`.

**FastAPI note**: `get_db` is a *FastAPI dependency*. When a route declares
`db: Session = Depends(get_db)`, FastAPI calls the generator, gives the route
the yielded value, and runs the `finally:` block after the response. This is
how you scope a session to a single request.

### [x] 1.3 Implement `src/database/models.py` (`Contact` ORM model)

- `class Contact(Base)` with all fields from SPEC §3 using SQLAlchemy 2.0
  typed `Mapped[...]` syntax.
- `__tablename__ = "contacts"`, `email` `unique=True`, `index=True`.
- `created_at` / `updated_at` use `server_default=func.now()`; `updated_at`
  also `onupdate=func.now()`.

**FastAPI note**: nothing FastAPI-specific here — pure SQLAlchemy. We're
keeping the model in `database/` (not `models.py` at root) per the lecture
layout.

### [x] 1.4 Set up Alembic

- `uv run alembic init alembic`.
- Edit `alembic.ini`: `prepend_sys_path = .:src`, `sqlalchemy.url =` left
  empty (read from env in `env.py`).
- Edit `alembic/env.py`: import `settings` and `Base`, set
  `target_metadata = Base.metadata`, set `config.set_main_option("sqlalchemy.url", settings.database_url)`.
- Run `docker compose up -d postgres` (compose file added next phase, do
  this temporarily with the existing hw-06 pattern, or skip until §3.x).

**FastAPI note**: Alembic isn't a FastAPI thing — it's the migration tool for
SQLAlchemy. Schema changes go through `revision --autogenerate` then
`upgrade head`.

> **Order tweak**: this step needs Postgres running. If you'd rather, do
> step 1.5 (compose for Postgres) *before* this and create the first
> migration after. The plan is not strict on micro-order here.

### [x] 1.5 Add `docker-compose.yml` with the `postgres` service

- Single service `postgres` (image, env, port, volume, healthcheck) — copy
  the hw-06 file and rename volume / env values to `hw08`.
- Verify: `docker compose up -d postgres && docker compose ps` shows healthy.

**Why**: gives you a real DB to point Alembic at without needing the API
container yet. The `api` service comes in Phase 6.

### [x] 1.6 Generate and apply the first Alembic migration

- `uv run alembic revision --autogenerate -m "create contacts table"` →
  inspect the generated file (`alembic/versions/xxx_*.py`); make sure it
  matches the SPEC §3 schema.
- `uv run alembic upgrade head`.
- Smoke check: `docker compose exec postgres psql -U postgres -d hw08 -c "\d contacts"`.

**FastAPI note**: nothing FastAPI; this is the SQLAlchemy → Postgres bridge.

---

## Phase 2 — Pydantic schemas

### [x] 2.1 Implement `src/schemas.py`

- `ContactBase` with all fields from SPEC §4, types per spec
  (`first_name: str = Field(min_length=1, max_length=50)`, `email: EmailStr`,
  `birthday: date`, etc.).
- `ContactCreate(ContactBase)` and `ContactUpdate(ContactBase)` — empty
  bodies; just inherit (full-replace PUT semantics).
- `ContactRead(ContactBase)` adds `id`, `created_at`, `updated_at`;
  `model_config = ConfigDict(from_attributes=True)`.

**FastAPI note**: Pydantic schemas serve two roles in FastAPI — request body
validation (via type-hinted handler params) and response shaping (via
`response_model`). Keeping `Create` / `Update` / `Read` as separate classes
is the standard way to split write-side from read-side fields.

---

## Phase 3 — Repository layer

### [x] 3.1 Implement `ContactRepository` CRUD: `add`, `get_by_id`, `update`, `delete`

- File: `src/repository/contacts.py`. Class `ContactRepository` with
  constructor taking a `Session`.
- Methods return ORM objects or `None`. No HTTP, no Pydantic.
- `update` mutates fields from a dict / `ContactUpdate` model dump and
  flushes; `delete` deletes by id.
- Methods are sync; explicit `self.db.commit()` calls (or commit at the
  service layer — pick one and document; recommend committing in repo for
  simplicity).

**FastAPI note**: the repository pattern is web-framework-agnostic. We use
it here because it gives us a clean test seam (we can hit it directly without
spinning up the app).

### [x] 3.2 Add `list` and `search` to `ContactRepository`

- `list(skip, limit) -> list[Contact]` — `select(Contact).order_by(Contact.id).offset(skip).limit(limit)`.
- `search(first_name, last_name, email, skip, limit)` — same query plus
  `.where(...)` for each non-blank filter using `Contact.first_name.ilike(f"%{value}%")`.
- Trim filters; treat empty/whitespace as "no filter".

**FastAPI note**: `select(...)` is the SQLAlchemy 2.0 `select()` construct,
not the legacy `Query`. Run with `self.db.scalars(stmt).all()`.

### [x] 3.3 Add `birthdays_in_window` to `ContactRepository`

- Signature: `birthdays_in_window(today: date, days: int = 7) -> list[Contact]`.
- Implement the year-agnostic window per SPEC §7. Year-wrap logic is the
  trickiest piece — comment the SQL clearly.
- Sort results by upcoming birthday (closest first). Easiest: compute in
  Python after fetching candidates, or use `(month, day)` ordering with a
  case-when for wrap.

**FastAPI note**: if the SQL gets ugly, accept it — the rubric awards 0.5 pts
for getting it right; clarity matters more than minimalism.

---

## Phase 4 — Service layer

### [x] 4.1 Define domain exceptions

- File: `src/services/exceptions.py`. Two classes:
  `ContactNotFound(Exception)`, `DuplicateEmail(Exception)`.
- No fancy fields — empty bodies are fine.

**FastAPI note**: keeping domain exceptions separate from `HTTPException`
means the service layer has no idea HTTP exists. Translation happens in the
API layer.

### [x] 4.2 Implement `ContactService` (CRUD + search + birthdays)

- File: `src/services/contacts.py`. Constructor takes a `ContactRepository`.
- Each method delegates to the repo:
  - `get(id)` → repo `get_by_id`; raise `ContactNotFound` on `None`.
  - `create(payload)` → repo `add`; on `IntegrityError` raise `DuplicateEmail`.
  - `update(id, payload)` → repo `get_by_id` (raise `ContactNotFound`), repo
    `update`; on `IntegrityError` raise `DuplicateEmail`.
  - `delete(id)` → repo `get_by_id` (raise `ContactNotFound`), repo `delete`.
  - `list_or_search(...)`, `upcoming_birthdays(today, days)` are pass-throughs.

**FastAPI note**: this layer looks thin because there are no real business
rules in this homework — but the test seam and the exception-translation
point are exactly what the lecture is teaching.

### [x] 4.3 Implement `services/deps.py` (FastAPI dependency factories)

- `def get_contact_repository(db: Session = Depends(get_db)) -> ContactRepository`
- `def get_contact_service(repo: ContactRepository = Depends(get_contact_repository)) -> ContactService`

**FastAPI note**: `Depends(...)` chains. When a handler asks for
`get_contact_service`, FastAPI resolves `get_contact_repository` first, which
in turn resolves `get_db`. This is FastAPI's "DI tree" — same idea as
constructor injection in other frameworks, but the wiring lives in function
signatures.

---

## Phase 5 — API layer

### [x] 5.1 Wire `main.py` skeleton: app, healthcheck, CORS-not-yet

- Replace the stub `main.py` with: `FastAPI(title="UMT pythonweb HW08")`,
  one router include placeholder, and `GET /api/healthchecker` doing
  `db.execute(text("SELECT 1"))`.
- Run `PYTHONPATH=src uv run uvicorn main:app --reload`, hit
  `http://localhost:8000/docs` — Swagger should render the healthcheck.

**FastAPI note**: opening `/docs` is the fastest sanity check. Swagger comes
for free; no extra config needed.

### [x] 5.2 Add `POST /api/contacts` (create)

- File: `src/api/contacts.py`. Create the `APIRouter(prefix="/contacts", tags=["contacts"])`.
- Handler signature:
  `def create_contact(payload: ContactCreate, service: ContactService = Depends(get_contact_service))`.
- Decorator: `@router.post("", response_model=ContactRead, status_code=201)`.
- In the handler: try `service.create(payload)`, except `DuplicateEmail`:
  `raise HTTPException(409, "Email already exists")`.
- Include the router in `main.py` under prefix `/api`.

**FastAPI note**: `response_model=ContactRead` is what makes Swagger show the
response shape AND filters the returned object so internal-only fields don't
leak. `status_code=201` is the standard "created" code.

### [x] 5.3 Add `GET /api/contacts` (list + search)

- Handler with optional query params via `Query(default=None, ...)`:
  `first_name`, `last_name`, `email`, `skip` (`Query(0, ge=0)`), `limit`
  (`Query(100, ge=1, le=500)`).
- Returns `list[ContactRead]` via `response_model`.
- Body just calls `service.list_or_search(...)`.

**FastAPI note**: function signature *is* the API contract. Type hints +
`Query()` annotations drive both validation and Swagger docs. No separate
schema needed for query strings.

### [x] 5.4 Add `GET /api/contacts/birthdays` (declare BEFORE `/{id}`)

- Handler with query param `days: int = Query(7, ge=1, le=30)`.
- Call `service.upcoming_birthdays(date.today(), days)`.

**FastAPI note**: route declaration order matters. If `/{contact_id}` comes
first, FastAPI tries to parse `"birthdays"` as an `int` and 422s. Declare
literal-path routes before parametrized ones — this is the single most
common FastAPI footgun.

### [x] 5.5 Add `GET /api/contacts/{contact_id}`

- Path param: `contact_id: int`.
- Call `service.get(contact_id)`; on `ContactNotFound` raise
  `HTTPException(404, "Contact not found")`.

**FastAPI note**: the path-param type hint (`int`) is enforced — non-int ids
get a 422 before your handler runs.

### [x] 5.6 Add `PUT /api/contacts/{contact_id}` and `DELETE /api/contacts/{contact_id}`

- PUT: body is `ContactUpdate`; on `ContactNotFound` 404; on `DuplicateEmail`
  409; otherwise `response_model=ContactRead`.
- DELETE: `status_code=204`; on `ContactNotFound` 404. Return `None` (FastAPI
  emits an empty body for 204).

**FastAPI note**: PUT semantics here are full-replacement. We're not adding
PATCH (out of scope). `204 No Content` must NOT have a body — FastAPI takes
care of that as long as the handler returns `None`.

### [x] 5.7 Manual smoke test via Swagger

- Start the app (Mode B), open `/docs`, exercise each endpoint:
  create two contacts, list, search by partial name, get-by-id, hit a
  not-found, hit a duplicate email, fetch upcoming birthdays, update,
  delete.
- Capture nothing — this is just a checkpoint that the happy path works
  end-to-end before adding tests.

---

## Phase 6 — Tests

### [x] 6.1 Write `tests/conftest.py` with the test-DB and override fixtures

- `engine` (session) pointing at `hw08_test`.
- Auto-creating-the-database fixture (connects to the `postgres` maintenance
  DB and `CREATE DATABASE` if missing).
- `tables` (session, autouse) — `Base.metadata.create_all(engine)` once,
  `drop_all` at end.
- `db_session` (function) — connection + nested transaction + Session;
  rolls back on teardown.
- `client` — `TestClient(app)` with `app.dependency_overrides[get_db]` set
  to a function that yields `db_session`.
- `contact_repository` and `contact_service` fixtures for direct testing.

**FastAPI note**: `app.dependency_overrides` is the test escape-hatch. You
swap a real dependency (`get_db`) for a test version without touching app
code. This is the single most useful FastAPI testing primitive.

### [x] 6.2 First sanity test: healthcheck via `TestClient`

- Single test: `def test_healthcheck(client): assert client.get("/api/healthchecker").status_code == 200`.
- Run `uv run pytest -k healthcheck` — should pass.

**Why this step exists**: separates "does the testing setup work?" from
"does my application logic work?". If this fails, no other test will tell
you anything useful.

### [x] 6.3 Write `tests/test_contacts_repository.py`

- Cases per SPEC §13. Use `contact_repository` and `db_session` fixtures
  directly — no HTTP involved.

**FastAPI note**: testing the repo without the framework is fast and
rebuilds your confidence in the data layer specifically.

### [x] 6.4 Write `tests/test_contacts_service.py`

- Focus: domain exception translation (`ContactNotFound`, `DuplicateEmail`).
  Use `contact_service` fixture.

### [x] 6.5 Write `tests/test_contacts_routes.py`

- Cases per SPEC §13: CRUD happy path + 404 + 409 + 422 cases via `TestClient`.

### [x] 6.6 Write `tests/test_search.py` and `tests/test_birthdays.py`

- Search: ILIKE partial, AND-combine, blank-ignore, pagination.
- Birthdays: today / today+6 / today+7 / year-wrap / Feb-29 — parameterize a
  helper that takes `today` rather than mocking `date.today()`.

**FastAPI note**: the year-wrap and Feb-29 cases are why the spec calls these
out — both are easy to ship broken without an explicit test.

### [x] 6.7 Verify the full test run

- `uv run pytest` — all green.
- (Optional) check coverage informally: are repo / service / api files all
  hit?

---

## Phase 7 — Docker for the API

### [x] 7.1 Write `Dockerfile`

- Base `python:3.12-slim`, install `uv`, copy `pyproject.toml` + `uv.lock`,
  `uv sync --frozen --no-install-project`, copy `main.py` + `src/` +
  `alembic/` + `alembic.ini`, `WORKDIR /app`, `EXPOSE 8000`,
  `ENV PYTHONPATH=/app/src`, `CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]`.

### [x] 7.2 Write `.dockerignore`

- `.venv/`, `__pycache__/`, `*.pyc`, `.git/`, `tests/`, `.pytest_cache/`,
  `.env`, `*.md` is your call (consider keeping README in the image — but
  not required).

**Why**: keeps the build context small and fast, and avoids leaking host
state (`.venv/` from the host arch).

### [x] 7.3 Add the `api` service to `docker-compose.yml`

- `build: .`, `ports: 8000:8000`, `depends_on: postgres
  (condition: service_healthy)`, env `DATABASE_URL=...@postgres:5432/hw08`,
  bind-mount `./main.py:/app/main.py` and `./src:/app/src` for live reload,
  override command to add `--reload`.

**FastAPI note**: bind-mounting source + `--reload` is a dev-mode pattern;
prod would bake the source into the image and skip `--reload`.

### [x] 7.4 Run the full stack via Mode A end-to-end

- `docker compose down -v` (clean slate).
- `docker compose up -d --build`.
- `docker compose run --rm api uv run alembic upgrade head`.
- Hit `/docs`, repeat the smoke test from 5.7.
- `docker compose down`.

---

## Phase 8 — Polish

### [x] 8.1 Write `README.md`

- Two setup modes per SPEC §14, the curl examples, link to `/docs`.
- Include a one-paragraph "Architecture" section pointing at SPEC §9.

### [x] 8.2 Final cleanup pass

- Remove any leftover prints / `# TODO`s.
- Ensure `.env` is gitignored and not committed.
- `uv run pre-commit run --all-files` clean.
- `uv run pytest` green; `docker compose up --build` green.

### [ ] 8.3 Tag and zip for submission

- Tag the final commit (e.g. `v1.0`) and push.
- `git archive --format=zip --output=ДЗ8_ПІБ.zip HEAD` (or build the zip
  manually if filenames need preservation).
- Upload to LMS, paste the repo URL.

---

## Step count: ~32. Estimated review surface per step: 30–150 lines of diff.
