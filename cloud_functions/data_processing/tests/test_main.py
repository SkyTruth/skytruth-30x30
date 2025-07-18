import pytest

import main
from tests.fixtures.utils.util_mocks import MockRequest


@pytest.fixture(autouse=True)
def reset_patches(monkeypatch):
    """
    Ensure for each test that:
    - download_zip_to_gcs, download_habitats, download_mpatlas,
      download_protected_seas, download_protected_planet are patched back.
      This just makes sure we don't acidently download data during a test
    - verbose is set to False for quieter tests (you can override per-test).
    """
    # Default no-ops
    monkeypatch.setattr(main, "download_zip_to_gcs", lambda *a, **k: None)
    monkeypatch.setattr(main, "download_habitats", lambda **kw: None)
    monkeypatch.setattr(main, "download_mpatlas", lambda **kw: None)
    monkeypatch.setattr(main, "download_protected_seas", lambda **kw: None)
    monkeypatch.setattr(main, "download_protected_planet", lambda **kw: None)
    # Silence verbose by default
    monkeypatch.setattr(main, "verbose", False)
    yield


def test_dry_run_only_prints_and_returns_ok(capsys):
    req = MockRequest({"METHOD": "dry_run"})
    result = main.main(req)

    assert result == ("OK", 200)

    out = capsys.readouterr().out
    assert "Dry Run Complete!" in out
    assert "Process complete!" in out


def test_download_eezs_invokes_download_zip_to_gcs(monkeypatch, capsys):
    calls = []

    def mock_download_zip_to_gcs(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(main, "download_zip_to_gcs", mock_download_zip_to_gcs)
    monkeypatch.setattr(main, "verbose", True)

    req = MockRequest({"METHOD": "download_eezs"})
    result = main.main(req)

    assert result == ("OK", 200)
    out = capsys.readouterr().out

    assert "Process complete!" in out
    assert len(calls) == 1
    args, kwargs = calls[0]

    assert args[0] is main.MARINE_REGIONS_URL
    assert args[1] == main.BUCKET
    assert args[2] == main.EEZ_ZIPFILE_NAME

    assert kwargs["data"] == main.MARINE_REGIONS_BODY
    assert kwargs["params"] == main.EEZ_PARAMS
    assert kwargs["headers"] == main.MARINE_REGIONS_HEADERS
    assert kwargs["chunk_size"] == main.CHUNK_SIZE
    assert kwargs["verbose"] is True


def test_download_high_seas_invokes_download_zip_to_gcs(monkeypatch, capsys):
    calls = []

    def mock_download_zip_to_gcs(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(main, "download_zip_to_gcs", mock_download_zip_to_gcs)
    monkeypatch.setattr(main, "verbose", True)

    req = MockRequest({"METHOD": "download_high_seas"})
    result = main.main(req)

    assert result == ("OK", 200)
    out = capsys.readouterr().out

    assert "Process complete!" in out
    assert len(calls) == 1
    args, kwargs = calls[0]

    assert args[0] is main.MARINE_REGIONS_URL
    assert args[1] == main.BUCKET
    assert args[2] == main.HIGH_SEAS_ZIPFILE_NAME

    assert kwargs["data"] == main.MARINE_REGIONS_BODY
    assert kwargs["params"] == main.HIGH_SEAS_PARAMS
    assert kwargs["headers"] == main.MARINE_REGIONS_HEADERS
    assert kwargs["chunk_size"] == main.CHUNK_SIZE
    assert kwargs["verbose"] is True


def test_download_gadm_invokes_download_zip_to_gcs(monkeypatch, capsys):
    calls = []

    def mock_download_zip_to_gcs(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(main, "download_zip_to_gcs", mock_download_zip_to_gcs)
    monkeypatch.setattr(main, "verbose", True)

    req = MockRequest({"METHOD": "download_gadm"})
    result = main.main(req)

    assert result == ("OK", 200)

    out = capsys.readouterr().out
    assert "Process complete!" in out

    assert len(calls) == 1
    args, kwargs = calls[0]

    assert args[0] is main.GADM_URL
    assert args[1] == main.BUCKET
    assert args[2] == main.GADM_ZIPFILE_NAME

    assert kwargs["chunk_size"] == main.CHUNK_SIZE
    assert kwargs["verbose"] is True


def test_download_habitats_invokes_correct_function(monkeypatch):
    called = {"count": 0}

    def mock_habitats(**kwargs):
        called["count"] += 1

    monkeypatch.setattr(main, "download_habitats", mock_habitats)
    req = MockRequest({"METHOD": "download_habitats"})
    result = main.main(req)

    assert result == ("OK", 200)
    assert called["count"] == 1


def test_download_mpatlas_invokes_correct_function(monkeypatch):
    called = {"count": 0}

    def mock_mpatlas(**kwargs):
        called["count"] += 1

    monkeypatch.setattr(main, "download_mpatlas", mock_mpatlas)
    req = MockRequest({"METHOD": "download_mpatlas"})
    result = main.main(req)

    assert result == ("OK", 200)
    assert called["count"] == 1


def test_download_protected_seas_invokes_correct_function(monkeypatch):
    called = {"count": 0}

    def mock_protected_seas(**kwargs):
        called["count"] += 1

    monkeypatch.setattr(main, "download_protected_seas", mock_protected_seas)
    req = MockRequest({"METHOD": "download_protected_seas"})
    result = main.main(req)

    assert result == ("OK", 200)
    assert called["count"] == 1


def test_download_protected_planet_invokes_correct_function(monkeypatch):
    called = {"count": 0}

    def mock_protected_planet(**kwargs):
        called["count"] += 1

    monkeypatch.setattr(main, "download_protected_planet", mock_protected_planet)
    req = MockRequest({"METHOD": "download_protected_planet_wdpa"})
    result = main.main(req)

    assert result == ("OK", 200)
    assert called["count"] == 1


def test_unknown_method_prints_warning_and_returns_ok(capsys):
    req = MockRequest({"METHOD": "something_else"})
    result = main.main(req)

    assert result == ("OK", 200)
    out = capsys.readouterr().out
    assert "METHOD: something_else not a valid option" in out
    assert "Process complete!" in out


def test_exception_in_handler_returns_500_and_logs(capsys, monkeypatch):
    # Simulate download_mpatlas raising
    def bad_mpatlas(**kwargs):
        raise RuntimeError("mpatlas boom")

    monkeypatch.setattr(main, "download_mpatlas", bad_mpatlas)

    req = MockRequest({"METHOD": "download_mpatlas"})
    result = main.main(req)

    assert result[1] == 500
    assert "Internal Server Error: mpatlas boom" in result[0]

    out = capsys.readouterr().out
    assert "METHOD download_mpatlas failed: mpatlas boom" in out
