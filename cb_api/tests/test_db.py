from collections.abc import Iterator

import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError

from src.analysis import AnalysisTable
from src.config import Settings
from src.db import build_database_url, create_db_engine

SETTINGS = Settings(
    _env_file=None,
    database_host="db.example.org",
    database_name="skytruth",
    database_username="analysis",
    database_password=SecretStr("s3cret"),
    database_port=5434,
)


def test_url_is_assembled_from_settings():
    url = build_database_url(SETTINGS)

    assert url.drivername == "postgresql+pg8000"
    assert url.username == "analysis"
    assert url.password == "s3cret"
    assert url.host == "db.example.org"
    assert url.port == 5434
    assert url.database == "skytruth"


def test_url_does_not_render_the_password():
    assert "s3cret" not in str(build_database_url(SETTINGS))


def test_engine_is_pooled_but_not_connected():
    engine = create_db_engine(SETTINGS)

    assert engine.pool.size() == SETTINGS.database_pool_size
    # The service starts before the database is necessarily reachable
    assert engine.pool.checkedout() == 0


def test_pool_settings_are_tunable_from_the_environment():
    settings = SETTINGS.model_copy(update={"database_pool_size": 2})

    assert create_db_engine(settings).pool.size() == 2


def test_engine_connections_are_read_only():
    engine = create_db_engine(SETTINGS)

    assert engine.get_execution_options()["postgresql_readonly"] is True


@pytest.fixture
def read_only_engine(postgis: Engine) -> Iterator[Engine]:
    """An engine built by create_db_engine, pointed at the test container."""
    url = postgis.url
    settings = SETTINGS.model_copy(
        update={
            "database_host": url.host,
            "database_port": url.port,
            "database_name": url.database,
            "database_username": url.username,
            "database_password": SecretStr(url.password),
            "database_pool_size": 1,
            "database_max_overflow": 0,
        }
    )
    engine = create_db_engine(settings)
    try:
        yield engine
    finally:
        engine.dispose()


TABLE = f"data.{AnalysisTable.MARINE.value}"

WRITES = [
    "CREATE TABLE cb_api_write_check (id int)",
    f"UPDATE {TABLE} SET location = 'ZZZ'",
    f"DELETE FROM {TABLE}",
]


@pytest.mark.integration
@pytest.mark.parametrize("statement", WRITES)
def test_writes_are_rejected(analysis_tables: Engine, read_only_engine: Engine, statement: str):
    with (
        pytest.raises(DBAPIError, match="read-only transaction"),
        read_only_engine.connect() as conn,
    ):
        conn.execute(text(statement))


@pytest.mark.integration
def test_writes_are_rejected_on_a_pooled_connection(
    analysis_tables: Engine, read_only_engine: Engine
):
    """The pool holds one connection, so the second checkout reuses the first."""
    with read_only_engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    with (
        pytest.raises(DBAPIError, match="read-only transaction"),
        read_only_engine.connect() as conn,
    ):
        conn.execute(text(f"DELETE FROM {TABLE}"))


@pytest.mark.integration
def test_reads_are_allowed(analysis_tables: Engine, read_only_engine: Engine):
    with read_only_engine.connect() as conn:
        assert conn.execute(text(f"SELECT count(*) FROM {TABLE}")).scalar() == 3
