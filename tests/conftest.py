import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session, sessionmaker

from conf.config import settings
from database.db import Base, get_db
from main import app
from repository.contacts import ContactRepository
from services.contacts import ContactService

TEST_DB_NAME = "hw08_test"


def _test_database_url() -> str:
    base = settings.database_url.rsplit("/", 1)[0]
    return f"{base}/{TEST_DB_NAME}"


@pytest.fixture(scope="session", autouse=True)
def _create_test_database():
    """Create the test database if it doesn't exist (connect to maintenance DB)."""
    maintenance_url = settings.database_url.rsplit("/", 1)[0] + "/postgres"
    admin_engine = create_engine(maintenance_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        try:
            conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
        except ProgrammingError:
            pass  # already exists
    admin_engine.dispose()
    yield


@pytest.fixture(scope="session")
def engine(_create_test_database):
    eng = create_engine(_test_database_url(), future=True)
    yield eng
    eng.dispose()


@pytest.fixture(scope="session", autouse=True)
def tables(engine):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture()
def db_session(engine):
    """Session bound to a connection in a transaction with nested SAVEPOINTs.

    The repo commits internally; without the SAVEPOINT trick those commits
    would persist and tests would leak. Each session.commit() ends a
    SAVEPOINT (not the outer transaction); the listener immediately opens
    a new one so the next commit has somewhere to release. Teardown rolls
    the outer transaction, undoing everything.
    """
    connection = engine.connect()
    transaction = connection.begin()
    TestingSession = sessionmaker(bind=connection, autoflush=False, autocommit=False, future=True)
    session = TestingSession()
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, trans):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db_session: Session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass  # session lifecycle is managed by db_session fixture

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def contact_repository(db_session: Session) -> ContactRepository:
    return ContactRepository(db_session)


@pytest.fixture()
def contact_service(contact_repository: ContactRepository) -> ContactService:
    return ContactService(contact_repository)
