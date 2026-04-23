import numpy as np
import pandas as pd
import pytest

import src.methods.generate_tables as gen_tables
from src.core.params import (
    GLOBAL_TERRESTRIAL_AREA_KM2,
)
# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def wdpa_country():
    """ testing for process_protected_area """
    return pd.DataFrame({
        "id": ["BRA"],
        "pas_count": [10],
        "statistics": [
            str({
                "marine_area": 1000.0,
                "oecms_pa_marine_area": 100.0,
                "percentage_oecms_pa_marine_cover": 10.0,
                "pa_marine_area": 80.0,
                "percentage_pa_marine_cover": 8.0,
                "protected_area_polygon_count": 5,
                "protected_area_point_count": 2,
                "oecm_polygon_count": 1,
                "oecm_point_count": 0,
                "land_area": 2000.0,
                "oecms_pa_land_area": 200.0,
                "percentage_oecms_pa_land_cover": 10.0,
                "pa_land_area": 160.0,
                "percentage_pa_land_cover": 8.0,
            })
        ],
    })

@pytest.fixture
def wdpa_global():
    return pd.DataFrame({
        "type": [
            "total_ocean_area_oecms_pas",
            "total_ocean_area_oecms",
            "total_ocean_oecms_pas_coverage_percentage",
            "total_marine_oecms_pas",
            "total_land_area_oecms_pas",
            "total_land_area_oecms",
            "total_land_oecms_pas_coverage_percentage",
            "total_terrestrial_oecms_pas",
            "high_seas_pa_coverage_area",
            "high_seas_pa_coverage_percentage",
            "national_waters_oecms_coverage_area",
            "national_waters_oecms_pas_coverage_area",
            "global_ocean_percentage",
        ],
        "value": [
            36_319_197.0,   # total_ocean_area_oecms_pas
            5_000_000.0,    # total_ocean_area_oecms
            10.0,           # total_ocean_oecms_pas_coverage_percentage
            500,            # total_marine_oecms_pas (count)
            15_000_000.0,   # total_land_area_oecms_pas
            3_000_000.0,    # total_land_area_oecms
            10.0,           # total_land_oecms_pas_coverage_percentage
            300,            # total_terrestrial_oecms_pas (count)
            1_000_000.0,    # high_seas_pa_coverage_area
            1.75,           # high_seas_pa_coverage_percentage
            20_000_000.0,   # national_waters_oecms_coverage_area
            25_000_000.0,   # national_waters_oecms_pas_coverage_area
            64.0,           # global_ocean_percentage
        ],
    })

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

def _run_generate(monkeypatch, wdpa_country, wdpa_global, combined_regions, upload_recorder):
    """"""
    calls, upload_mock = upload_recorder

    monkeypatch.setattr(gen_tables, "load_regions", lambda **_: (combined_regions, {}))
    monkeypatch.setattr(gen_tables, "read_dataframe", lambda *a, **kw: wdpa_country.copy())
    monkeypatch.setattr(gen_tables, "load_wdpa_global", lambda *a, **kw: wdpa_global.copy())

    monkeypatch.setattr(
        gen_tables,
        "upload_dataframe",
        lambda bucket, df, dest, **kw: upload_mock(
            bucket_name=bucket, df=df, destination_blob_name=dest
        ),
    )

    result = gen_tables.generate_protection_coverage_stats_table(verbose=False)
    return pd.DataFrame(result), calls

def _get_row(df, location, environment="marine"):
    rows = df[(df["location"] == location) & (df["environment"] == environment)]
    assert len(rows) == 1, f"Expected 1 row for {location}/{environment}, got {len(rows)}"
    return rows.iloc[0]

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_total_area_marine(monkeypatch, wdpa_country, wdpa_global, combined_regions, upload_recorder):
    """use back calculation correctly for global area in marine env"""
    df, _ = _run_generate(monkeypatch,  wdpa_country, wdpa_global, combined_regions, upload_recorder)
    row = _get_row(df, "GLOB")
    # total area = oecms_pas / (coverage / 100)
    assert row["total_area"] == 363_191_970

def test_total_area_terrestrial(monkeypatch, wdpa_country, wdpa_global, combined_regions, upload_recorder):
    """use back calculation correctly for global area in marine env"""
    df, _ = _run_generate(monkeypatch,  wdpa_country, wdpa_global, combined_regions, upload_recorder)
    row = _get_row(df, "GLOB", environment="terrestrial")
    # total area = GLOBAL_TERRESTRIAL_AREA_KM2
    assert row["total_area"] == GLOBAL_TERRESTRIAL_AREA_KM2

def test_global_contribution(monkeypatch, wdpa_country, wdpa_global, combined_regions, upload_recorder):
    """use back calculation correctly for global area in marine env"""
    df, _ = _run_generate(monkeypatch,  wdpa_country, wdpa_global, combined_regions, upload_recorder)
    row = _get_row(df, "GLOB")
    # global_contribution = coverage
    assert row["global_contribution"] == 10



