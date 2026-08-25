import os

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

from alembic import command

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="session")
def postgres_url():
    with PostgresContainer("pgvector/pgvector:pg15", driver="psycopg") as container:
        yield container.get_connection_url()


@pytest.fixture(scope="session")
def _migrated_engine(postgres_url):
    os.environ["DATABASE_URL"] = postgres_url

    alembic_cfg = Config(os.path.join(REPO_ROOT, "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", postgres_url)
    alembic_cfg.set_main_option("script_location", os.path.join(REPO_ROOT, "alembic"))
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(postgres_url)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(_migrated_engine):
    connection = _migrated_engine.connect()
    session = sessionmaker(bind=connection)()
    yield session
    session.close()
    # every test rolls back its own writes so seeded fixtures don't leak across tests
    connection.execute(
        text(
            "TRUNCATE citations, saved_searches, chunks, judgments, users RESTART IDENTITY CASCADE"
        )
    )
    connection.commit()
    connection.close()


@pytest.fixture()
def client(_migrated_engine, db_session):
    from app.api.deps import get_db
    from app.main import app

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
