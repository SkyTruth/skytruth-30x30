import pandas as pd
import pytest

import src.methods.generate_tables as gen_tables

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mpatlas_country():
    return pd.DataFrame(
        {
            "id": ["BRA"],
            "highly_protected_km2": [100_000.0],
            "highly_protected_percent": [10.0],
            "wdpa_marine_km2": [1_000_000.0],
        }
    )


@pytest.fixture
def mpatlas_global():
    return pd.DataFrame(
        {
            "total_km2": [363_046_756],
            "mpaguide_total_if_km2": [6_055_530],
            "mpaguide_total_ih_km2": [6_226_802],
        }
    )


@pytest.fixture
def combined_regions():
    return {
        "BRA": ["BRA"],
        "GLOB": [],
    }


@pytest.fixture
def upload_recorder():
    calls = []

    def _upload_dataframe(*, bucket_name, df, destination_blob_name, **_):
        calls.append(
            {
                "bucket_name": bucket_name,
                "destination_blob_name": destination_blob_name,
                "df": df.copy(),
            }
        )

    return calls, _upload_dataframe


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_generate(monkeypatch, mpatlas_country, mpatlas_global, combined_regions, upload_recorder):
    """"""
    calls, upload_mock = upload_recorder

    monkeypatch.setattr(gen_tables, "load_regions", lambda **_: (combined_regions, {}))
    monkeypatch.setattr(gen_tables, "load_mpatlas_country", lambda *a, **kw: mpatlas_country.copy())
    monkeypatch.setattr(gen_tables, "load_mpatlas_global", lambda *a, **kw: mpatlas_global.copy())
    monkeypatch.setattr(
        gen_tables,
        "load_marine_regions",
        lambda *a, **kw: pd.DataFrame({"area_km2": [5_000_000.0]}),
    )

    monkeypatch.setattr(
        gen_tables,
        "upload_dataframe",
        lambda bucket, df, dest, **kw: upload_mock(
            bucket_name=bucket, df=df, destination_blob_name=dest
        ),
    )

    result = gen_tables.generate_marine_protection_level_stats_table(verbose=False)
    return pd.DataFrame(result), calls


def _get_row(df, location):
    rows = df[df["location"] == location]
    assert len(rows) == 1, f"Expected 1 row for {location}, got {len(rows)}"
    return rows.iloc[0]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_total_area(
    monkeypatch, mpatlas_country, mpatlas_global, combined_regions, upload_recorder
):
    """total_area GLOBAL should equal total_km2 from mpatlas_global"""
    df, _ = _run_generate(
        monkeypatch, mpatlas_country, mpatlas_global, combined_regions, upload_recorder
    )
    row = _get_row(df, "GLOB")
    assert row["total_area"] == 363_046_756


def test_combined_area(
    monkeypatch, mpatlas_country, mpatlas_global, combined_regions, upload_recorder
):
    """protected area should be a sum of highly and fully protected"""
    df, _ = _run_generate(
        monkeypatch, mpatlas_country, mpatlas_global, combined_regions, upload_recorder
    )
    row = _get_row(df, "GLOB")
    assert row["area"] == 12_282_332


def test_non_GLOB_location(
    monkeypatch, mpatlas_country, mpatlas_global, combined_regions, upload_recorder
):
    """non global sums should use their own country's data"""
    df, _ = _run_generate(
        monkeypatch, mpatlas_country, mpatlas_global, combined_regions, upload_recorder
    )
    row = _get_row(df, "BRA")
    assert row["area"] == 100_000
