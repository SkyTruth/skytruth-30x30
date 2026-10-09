import pytest
from pydantic import ValidationError

from src.config import Settings

REQUIRED = {
    "DATABASE_HOST": "db.example.org",
    "DATABASE_NAME": "skytruth",
    "DATABASE_USERNAME": "analysis",
    "DATABASE_PASSWORD": "s3cret",
}


def build_settings(env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Construct settings from env."""
    for key in (*REQUIRED, "DATABASE_PORT"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return Settings(_env_file=None)


def test_reads_connection_details_from_the_environment(monkeypatch: pytest.MonkeyPatch):
    settings = build_settings(REQUIRED, monkeypatch)

    assert settings.database_host == "db.example.org"
    assert settings.database_name == "skytruth"
    assert settings.database_username == "analysis"
    assert settings.database_password.get_secret_value() == "s3cret"


def test_port_defaults_to_5432(monkeypatch: pytest.MonkeyPatch):
    assert build_settings(REQUIRED, monkeypatch).database_port == 5432


def test_port_can_be_overridden(monkeypatch: pytest.MonkeyPatch):
    settings = build_settings({**REQUIRED, "DATABASE_PORT": "5434"}, monkeypatch)

    assert settings.database_port == 5434


def test_missing_variables_are_reported_together(monkeypatch: pytest.MonkeyPatch):
    with pytest.raises(ValidationError) as excinfo:
        build_settings({"DATABASE_HOST": "db.example.org"}, monkeypatch)

    missing = {error["loc"][0] for error in excinfo.value.errors()}
    assert missing == {"database_name", "database_username", "database_password"}


def test_password_is_not_exposed_by_repr(monkeypatch: pytest.MonkeyPatch):
    settings = build_settings(REQUIRED, monkeypatch)

    assert "s3cret" not in repr(settings)
