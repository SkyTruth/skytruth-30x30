import numpy as np
import pandas as pd
import pytest

import src.methods.generate_tables as gen_tables

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def protected_seas_df():
    """
    Minimal Protected Seas data with:
    - GBR: sovereign with territories (aggregate + NAT + 2 territories)
    - BRA: single country (aggregate only, no territories)
    - HSX: high seas (aggregate only)
    - OCN: global ocean (used exclusively for GLOB stats)
    """
    return pd.DataFrame(
        {
            "iso_sov": ["GBR", "GBR", "GBR", "GBR", "BRA", "HSX", "OCN"],
            "iso_ter": ["", "NAT", "FLK", "PCN", "", "", ""],
            "total_area": [5500.0, 2000.0, 1500.0, 1500.0, 3000.0, 50000.0, 100000.0],
            "lfp5_area": [560.0, 100.0, 200.0, 200.0, 300.0, 1000.0, 2500.0],
            "lfp4_area": [55.0, 20.0, 15.0, 15.0, 30.0, 100.0, 250.0],
            "lfp3_area": [200.0, 80.0, 60.0, 60.0, 150.0, 2000.0, 5000.0],
            "lfp2_area": [100.0, 40.0, 30.0, 30.0, 80.0, 5000.0, 10000.0],
            "lfp1_area": [50.0, 10.0, 20.0, 20.0, 40.0, 3000.0, 8000.0],
        }
    )


@pytest.fixture
def combined_regions():
    return {
        "GBR": ["GBR", "FLK", "PCN"],
        "BRA": ["BRA"],
        "EU": ["GBR", "BRA"],
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


def _run_generate(monkeypatch, protected_seas_df, combined_regions, upload_recorder):
    """Patch dependencies and run generate_fishing_protection_table."""
    calls, upload_mock = upload_recorder

    monkeypatch.setattr(gen_tables, "load_regions", lambda **_: (combined_regions, {}))
    monkeypatch.setattr(gen_tables, "read_dataframe", lambda *a, **kw: protected_seas_df.copy())
    monkeypatch.setattr(
        gen_tables,
        "upload_dataframe",
        lambda bucket, df, dest, **kw: upload_mock(
            bucket_name=bucket, df=df, destination_blob_name=dest
        ),
    )

    result = gen_tables.generate_fishing_protection_table(verbose=False)
    return pd.DataFrame(result), calls


def _get_row(df, location, level="highly"):
    rows = df[(df["location"] == location) & (df["fishing_protection_level"] == level)]
    assert len(rows) == 1, f"Expected 1 row for {location}/{level}, got {len(rows)}"
    return rows.iloc[0]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_national_waters_uses_nat_row(
    monkeypatch, protected_seas_df, combined_regions, upload_recorder
):
    """GBR should use NAT + territory rows (the original fp_location behavior)."""
    df, _ = _run_generate(monkeypatch, protected_seas_df, combined_regions, upload_recorder)
    row = _get_row(df, "GBR")
    # NAT (2000) + FLK (1500) + PCN (1500)
    assert row["total_area"] == 5000
    # NAT highly (120) + FLK (215) + PCN (215) = 550
    assert row["area"] == 550.0


def test_single_country_uses_aggregate(
    monkeypatch, protected_seas_df, combined_regions, upload_recorder
):
    """BRA has no territories, so its aggregate row is used directly."""
    df, _ = _run_generate(monkeypatch, protected_seas_df, combined_regions, upload_recorder)
    row = _get_row(df, "BRA")
    assert row["total_area"] == 3000
    assert row["area"] == 330.0


def test_territory_rows_appear_as_standalone_locations(
    monkeypatch, protected_seas_df, combined_regions, upload_recorder
):
    """Individual territory rows (FLK, PCN) should appear as their own locations."""
    regions = {**combined_regions, "FLK": ["FLK"], "PCN": ["PCN"]}
    df, _ = _run_generate(monkeypatch, protected_seas_df, regions, upload_recorder)
    flk = _get_row(df, "FLK")
    assert flk["total_area"] == 1500
    assert flk["area"] == 215.0


def test_nan_iso_ter_treated_as_aggregate(monkeypatch, combined_regions, upload_recorder):
    """NaN iso_ter should be treated identically to empty string."""
    ps = pd.DataFrame(
        {
            "iso_sov": ["BRA", "OCN"],
            "iso_ter": [np.nan, np.nan],
            "total_area": [3000.0, 100000.0],
            "lfp5_area": [300.0, 2500.0],
            "lfp4_area": [30.0, 250.0],
            "lfp3_area": [150.0, 5000.0],
            "lfp2_area": [80.0, 10000.0],
            "lfp1_area": [40.0, 8000.0],
        }
    )
    df, _ = _run_generate(monkeypatch, ps, combined_regions, upload_recorder)
    row = _get_row(df, "BRA")
    assert row["total_area"] == 3000


def test_glob_uses_ocn_row(monkeypatch, protected_seas_df, combined_regions, upload_recorder):
    """GLOB should use the OCN (Global Ocean) row directly."""
    df, _ = _run_generate(monkeypatch, protected_seas_df, combined_regions, upload_recorder)
    row = _get_row(df, "GLOB")
    assert row["total_area"] == 100000
    assert row["area"] == 2750.0
    assert abs(row["pct"] - 100 * 2750.0 / 100000.0) < 0.001


def test_ocn_excluded_from_country_and_region_stats(
    monkeypatch, protected_seas_df, combined_regions, upload_recorder
):
    """OCN should not appear in any non-GLOB location or inflate region totals."""
    df, _ = _run_generate(monkeypatch, protected_seas_df, combined_regions, upload_recorder)
    assert "OCN" not in df["location"].values
    eu = _get_row(df, "EU")
    # GBR (NAT 2000 + FLK 1500 + PCN 1500 = 5000) + BRA (3000) = 8000 if GBR includes territories
    # but EU = ["GBR", "BRA"] so only GBR(NAT=2000) + BRA(3000) = 5000
    assert eu["total_area"] == 5000


def test_iso_map_merges_territories(monkeypatch, combined_regions, upload_recorder):
    """protected_seas_iso_map should merge component territories into one location."""
    ps = pd.DataFrame(
        {
            "iso_sov": ["GBR", "GBR", "GBR", "GBR", "OCN"],
            "iso_ter": ["NAT", "ASC", "SHN", "TDC", ""],
            "total_area": [1000.0, 200.0, 300.0, 500.0, 50000.0],
            "lfp5_area": [10.0, 20.0, 30.0, 50.0, 1000.0],
            "lfp4_area": [1.0, 2.0, 3.0, 5.0, 100.0],
            "lfp3_area": [0.0, 0.0, 0.0, 0.0, 0.0],
            "lfp2_area": [0.0, 0.0, 0.0, 0.0, 0.0],
            "lfp1_area": [0.0, 0.0, 0.0, 0.0, 0.0],
        }
    )
    regions = {**combined_regions, "SHN": ["SHN"]}
    df, _ = _run_generate(monkeypatch, ps, regions, upload_recorder)
    # ASC + SHN + TDC should be merged into SHN
    shn = _get_row(df, "SHN")
    assert shn["total_area"] == 1000  # 200 + 300 + 500
    assert shn["area"] == 110.0  # (20+30+50) + (2+3+5)
    # Individual territory codes should not exist
    assert "ASC" not in df["location"].values
    assert "TDC" not in df["location"].values


def test_region_sums_country_level_rows(
    monkeypatch, protected_seas_df, combined_regions, upload_recorder
):
    """EU region sums its member locations."""
    df, _ = _run_generate(monkeypatch, protected_seas_df, combined_regions, upload_recorder)
    row = _get_row(df, "EU")
    # EU = ["GBR", "BRA"] → GBR (NAT=2000) + BRA (3000) = 5000
    assert row["total_area"] == 5000


def test_all_three_protection_levels_present(
    monkeypatch, protected_seas_df, combined_regions, upload_recorder
):
    """Output contains highly, moderately, and less with correct area calculations."""
    df, _ = _run_generate(monkeypatch, protected_seas_df, combined_regions, upload_recorder)
    assert set(df["fishing_protection_level"].unique()) == {"highly", "moderately", "less"}
    assert _get_row(df, "BRA", "highly")["area"] == 330.0
    assert _get_row(df, "BRA", "moderately")["area"] == 150.0
    assert _get_row(df, "BRA", "less")["area"] == 120.0


def test_pct_capped_at_100(monkeypatch, combined_regions, upload_recorder):
    """Percentage should be capped at 100 even if protected area > total_area."""
    ps = pd.DataFrame(
        {
            "iso_sov": ["TST", "OCN"],
            "iso_ter": ["", ""],
            "total_area": [100.0, 50000.0],
            "lfp5_area": [80.0, 1000.0],
            "lfp4_area": [80.0, 100.0],
            "lfp3_area": [0.0, 0.0],
            "lfp2_area": [0.0, 0.0],
            "lfp1_area": [0.0, 0.0],
        }
    )
    regions = {**combined_regions, "TST": ["TST"]}
    df, _ = _run_generate(monkeypatch, ps, regions, upload_recorder)
    assert _get_row(df, "TST")["pct"] == 100


def test_crv_remapped_to_hrv(monkeypatch, combined_regions, upload_recorder):
    """CRV sovereign code should be remapped to HRV (Croatia)."""
    ps = pd.DataFrame(
        {
            "iso_sov": ["CRV", "OCN"],
            "iso_ter": ["", ""],
            "total_area": [1000.0, 50000.0],
            "lfp5_area": [100.0, 1000.0],
            "lfp4_area": [10.0, 100.0],
            "lfp3_area": [50.0, 0.0],
            "lfp2_area": [20.0, 0.0],
            "lfp1_area": [5.0, 0.0],
        }
    )
    regions = {**combined_regions, "HRV": ["HRV"]}
    df, _ = _run_generate(monkeypatch, ps, regions, upload_recorder)
    assert "CRV" not in df["location"].values
    assert _get_row(df, "HRV")["area"] == 110.0


def test_upload_format(monkeypatch, protected_seas_df, combined_regions, upload_recorder):
    """Uploaded table should target the correct blob and have Int64 total_area."""
    _, calls = _run_generate(monkeypatch, protected_seas_df, combined_regions, upload_recorder)
    assert len(calls) == 1
    assert calls[0]["destination_blob_name"] == gen_tables.FISHING_PROTECTION_FILE_NAME
    assert calls[0]["df"]["total_area"].dtype == pd.Int64Dtype()


def test_zero_total_area_rows_filtered(monkeypatch, combined_regions, upload_recorder):
    """Rows with total_area <= 0 should be filtered out."""
    ps = pd.DataFrame(
        {
            "iso_sov": ["ZZZ", "OCN"],
            "iso_ter": ["", ""],
            "total_area": [0.0, 50000.0],
            "lfp5_area": [0.0, 1000.0],
            "lfp4_area": [0.0, 100.0],
            "lfp3_area": [0.0, 0.0],
            "lfp2_area": [0.0, 0.0],
            "lfp1_area": [0.0, 0.0],
        }
    )
    regions = {**combined_regions, "ZZZ": ["ZZZ"]}
    df, _ = _run_generate(monkeypatch, ps, regions, upload_recorder)
    assert len(df) == 0 or "ZZZ" not in df["location"].values
