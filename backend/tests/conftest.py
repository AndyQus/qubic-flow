"""
Shared pytest fixtures for QubicFlow backend tests.

Isolation strategy:
  - Session-scoped engine creates the schema once in :memory:.
  - Each test gets a connection that starts a top-level transaction.
    The session joins that connection.  After the test the outer
    transaction is rolled back, so even db.commit() calls inside the
    test are never permanently committed.  (Standard SQLAlchemy
    "joined transaction" test pattern.)
  - The FastAPI app is created once per session with the scheduler
    disabled to avoid APScheduler re-start errors across tests.
  - The `get_db` dependency is overridden via a thin wrapper that
    reads the *current* per-test session from a mutable container,
    so a single session-scoped TestClient can serve per-test DBs.
"""
import pytest
from sqlalchemy import create_engine, event as sqla_event
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

TEST_DATABASE_URL = "sqlite:///:memory:"

# Mutable holder so the session-scoped client can be pointed at the
# per-test session without recreating the client.
_current_db: dict = {"session": None}


# ------------------------------------------------------------------
# Session-scoped engine — schema created once
# ------------------------------------------------------------------

@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )

    @sqla_event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    # Import all models so Base picks them up, then create tables
    from app.database import Base
    import app.models.wallet       # noqa: F401
    import app.models.event        # noqa: F401
    import app.models.sync_state   # noqa: F401
    import app.models.sync_gap     # noqa: F401
    import app.models.price_cache  # noqa: F401
    import app.models.node         # noqa: F401
    import app.models.settings     # noqa: F401
    import app.models.snapshot     # noqa: F401

    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


# ------------------------------------------------------------------
# Per-test DB fixture using "joined transaction" pattern
# ------------------------------------------------------------------

@pytest.fixture()
def db(test_engine):
    """
    Yields a SQLAlchemy session whose changes are always rolled back
    after the test, even when the code under test calls db.commit().
    """
    connection = test_engine.connect()
    trans = connection.begin()

    TestSession = sessionmaker(bind=connection)
    session = TestSession()

    _current_db["session"] = session
    yield session
    _current_db["session"] = None

    session.close()
    trans.rollback()
    connection.close()


# ------------------------------------------------------------------
# Session-scoped FastAPI app + TestClient
# ------------------------------------------------------------------

@pytest.fixture(scope="session")
def app_client(test_engine):
    """
    Create the FastAPI app once for the entire test session, with:
      - the scheduler disabled (patched out to prevent start errors)
      - get_db overridden to always use the *current* per-test session
        from the `_current_db` mutable holder.
    """
    from unittest.mock import MagicMock, patch
    from app.main import app
    from app.database import get_db

    def _override_get_db():
        session = _current_db.get("session")
        if session is None:
            raise RuntimeError(
                "No active test DB session — ensure the `db` fixture is requested"
            )
        yield session

    app.dependency_overrides[get_db] = _override_get_db

    # Patch the scheduler so lifespan startup/shutdown don't hit APScheduler
    mock_scheduler = MagicMock()
    with patch("app.main.scheduler", mock_scheduler):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c

    app.dependency_overrides.pop(get_db, None)


# ------------------------------------------------------------------
# Per-test `client` alias — requires `db` to be active
# ------------------------------------------------------------------

@pytest.fixture()
def client(db, app_client):
    """
    Returns the session-scoped TestClient while the per-test `db`
    session is active.  Requesting `db` first ensures the mutable
    holder is populated before any request hits the override.
    """
    yield app_client
