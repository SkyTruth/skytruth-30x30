from pydantic import SecretStr

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
