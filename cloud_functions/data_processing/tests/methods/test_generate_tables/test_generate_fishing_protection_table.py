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
    """
    return pd.DataFrame(
        {
            "iso_sov": [
                "GBR",
                "GBR",
                "GBR",
                "GBR",
                "BRA",
                "HSX",
            ],
            "iso_ter": [
                "",
                "NAT",
                "FLK",
                "PCN",
                "",
                "",
            ],
            "total_area": [
                5000.0,
                2000.0,
                1500.0,
                1500.0,
                3000.0,
                50000.0,
            ],
            "lfp5_area": [
                500.0,
                100.0,
                200.0,
                200.0,
                300.0,
                1000.0,
            ],
            "lfp4_area": [
                50.0,
                20.0,
                15.0,
                15.0,
                30.0,
                100.0,
            ],
            "lfp3_area": [
                200.0,
                80.0,
                60.0,
                60.0,
                150.0,
                2000.0,
            ],
            "lfp2_area": [
                100.0,
                40.0,
                30.0,
                30.0,
                80.0,
                5000.0,
            ],
            "lfp1_area": [
                50.0,
                10.0,
                20.0,
                20.0,
                40.0,
                3000.0,
            ],
        }
    )


@pytest.fixture
def protected_seas_df_with_nan():
    """Same as protected_seas_df but iso_ter uses NaN instead of empty string."""
    return pd.DataFrame(
        {
            "iso_sov": ["GBR", "GBR", "BRA", "HSX"],
            "iso_ter": [np.nan, "NAT", np.nan, np.nan],
            "total_area": [5000.0, 2000.0, 3000.0, 50000.0],
            "lfp5_area": [500.0, 100.0, 300.0, 1000.0],
            "lfp4_area": [50.0, 20.0, 30.0, 100.0],
            "lfp3_area": [200.0, 80.0, 150.0, 2000.0],
            "lfp2_area": [100.0, 40.0, 80.0, 5000.0],
            "lfp1_area": [50.0, 10.0, 40.0, 3000.0],
        }
    )


@pytest.fixture
def combined_regions():
    """
    Minimal combined_regions dict:
    - GBR: sovereign 3-letter key (includes GBR + territories)
    - GBR*: sovereign aggregate key
    - BRA: single country
    - EU: region containing GBR and BRA
    - GLOB: global
    """
    return {
        "GBR": ["GBR"],
        "GBR*": ["GBR", "FLK", "PCN"],
        "BRA": ["BRA"],
        "EU": ["GBR", "BRA"],
        "GLOB": [],
    }


@pytest.fixture
def upload_recorder():
    calls = []

    def _upload_dataframe(*, bucket_name, df, destination_blob_name, **_):
        assert isinstance(df, pd.DataFrame)
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

    monkeypatch.setattr(
        gen_tables,
        "load_regions",
        lambda **_: (combined_regions, {}),
    )
    monkeypatch.setattr(
        gen_tables,
        "read_dataframe",
        lambda *a, **kw: protected_seas_df.copy(),
    )
    monkeypatch.setattr(
        gen_tables,
        "upload_dataframe",
        lambda bucket, df, dest, **kw: upload_mock(
            bucket_name=bucket, df=df, destination_blob_name=dest
        ),
    )

    result = gen_tables.generate_fishing_protection_table(verbose=False)
    return pd.DataFrame(result), calls


# ---------------------------------------------------------------------------
# Tests: Data preparation (aggregate vs NAT row selection)
# ---------------------------------------------------------------------------


class TestDataPreparation:
    def test_aggregate_rows_used_for_sovereign_star_lookup(
        self, monkeypatch, protected_seas_df, combined_regions, upload_recorder
    ):
        """GBR* should use the aggregate row (total_area=5000), not NAT (2000)."""
        df, _ = _run_generate(monkeypatch, protected_seas_df, combined_regions, upload_recorder)
        gbr_star = df[(df["location"] == "GBR*") & (df["fishing_protection_level"] == "highly")]
        assert len(gbr_star) == 1
        assert gbr_star.iloc[0]["total_area"] == 5000

    def test_nat_row_used_for_national_waters(
        self, monkeypatch, protected_seas_df, combined_regions, upload_recorder
    ):
        """GBR (national waters) should use the NAT row (total_area=2000)."""
        df, _ = _run_generate(monkeypatch, protected_seas_df, combined_regions, upload_recorder)
        gbr = df[(df["location"] == "GBR") & (df["fishing_protection_level"] == "highly")]
        assert len(gbr) == 1
        assert gbr.iloc[0]["total_area"] == 2000

    def test_sovereign_star_differs_from_national_waters(
        self, monkeypatch, protected_seas_df, combined_regions, upload_recorder
    ):
        """GBR and GBR* should have different values."""
        df, _ = _run_generate(monkeypatch, protected_seas_df, combined_regions, upload_recorder)
        highly = df[df["fishing_protection_level"] == "highly"]
        gbr = highly[highly["location"] == "GBR"].iloc[0]
        gbr_star = highly[highly["location"] == "GBR*"].iloc[0]
        assert gbr["total_area"] != gbr_star["total_area"]
        assert gbr["area"] != gbr_star["area"]

    def test_single_country_uses_aggregate(
        self, monkeypatch, protected_seas_df, combined_regions, upload_recorder
    ):
        """BRA has no territories, so its aggregate row is used directly."""
        df, _ = _run_generate(monkeypatch, protected_seas_df, combined_regions, upload_recorder)
        bra = df[(df["location"] == "BRA") & (df["fishing_protection_level"] == "highly")]
        assert len(bra) == 1
        assert bra.iloc[0]["total_area"] == 3000
        assert bra.iloc[0]["area"] == 330.0  # lfp5 (300) + lfp4 (30)

    def test_territory_rows_excluded_from_output(
        self, monkeypatch, protected_seas_df, combined_regions, upload_recorder
    ):
        """Individual territory rows (FLK, PCN) should not appear as locations."""
        df, _ = _run_generate(monkeypatch, protected_seas_df, combined_regions, upload_recorder)
        assert "FLK" not in df["location"].values
        assert "PCN" not in df["location"].values

    def test_nan_iso_ter_handled_same_as_empty(
        self, monkeypatch, protected_seas_df_with_nan, combined_regions, upload_recorder
    ):
        """NaN iso_ter should be treated as aggregate rows, same as empty string."""
        df, _ = _run_generate(
            monkeypatch, protected_seas_df_with_nan, combined_regions, upload_recorder
        )
        gbr_star = df[(df["location"] == "GBR*") & (df["fishing_protection_level"] == "highly")]
        assert len(gbr_star) == 1
        assert gbr_star.iloc[0]["total_area"] == 5000


# ---------------------------------------------------------------------------
# Tests: GLOB calculation
# ---------------------------------------------------------------------------


class TestGlobalStats:
    def test_glob_total_area_is_sum_of_aggregates(
        self, monkeypatch, protected_seas_df, combined_regions, upload_recorder
    ):
        """GLOB total_area = sum of all aggregate rows (GBR + BRA + HSX)."""
        df, _ = _run_generate(monkeypatch, protected_seas_df, combined_regions, upload_recorder)
        glob_highly = df[(df["location"] == "GLOB") & (df["fishing_protection_level"] == "highly")]
        assert len(glob_highly) == 1
        # GBR aggregate (5000) + BRA aggregate (3000) + HSX aggregate (50000)
        assert glob_highly.iloc[0]["total_area"] == 58000

    def test_glob_protected_area_sums_all_aggregates(
        self, monkeypatch, protected_seas_df, combined_regions, upload_recorder
    ):
        """GLOB highly protected area = sum of lfp5+lfp4 from all aggregate rows."""
        df, _ = _run_generate(monkeypatch, protected_seas_df, combined_regions, upload_recorder)
        glob_highly = df[(df["location"] == "GLOB") & (df["fishing_protection_level"] == "highly")]
        # GBR: 500+50=550, BRA: 300+30=330, HSX: 1000+100=1100 → total=1980
        assert glob_highly.iloc[0]["area"] == 1980.0

    def test_glob_pct_uses_aggregate_total(
        self, monkeypatch, protected_seas_df, combined_regions, upload_recorder
    ):
        """GLOB pct = protected / total_area * 100 using aggregate sums."""
        df, _ = _run_generate(monkeypatch, protected_seas_df, combined_regions, upload_recorder)
        glob_highly = df[(df["location"] == "GLOB") & (df["fishing_protection_level"] == "highly")]
        expected_pct = 100 * 1980.0 / 58000.0
        assert abs(glob_highly.iloc[0]["pct"] - expected_pct) < 0.001

    def test_glob_does_not_double_count_nat_rows(
        self, monkeypatch, protected_seas_df, combined_regions, upload_recorder
    ):
        """GLOB should NOT include NAT or territory rows — only aggregates."""
        df, _ = _run_generate(monkeypatch, protected_seas_df, combined_regions, upload_recorder)
        glob_highly = df[(df["location"] == "GLOB") & (df["fishing_protection_level"] == "highly")]
        # If NAT row (total_area=2000) leaked in, total would be 60000
        assert glob_highly.iloc[0]["total_area"] == 58000


# ---------------------------------------------------------------------------
# Tests: Region aggregation
# ---------------------------------------------------------------------------


class TestRegionStats:
    def test_region_sums_national_waters(
        self, monkeypatch, protected_seas_df, combined_regions, upload_recorder
    ):
        """EU region sums national waters of its members (GBR NAT + BRA aggregate)."""
        df, _ = _run_generate(monkeypatch, protected_seas_df, combined_regions, upload_recorder)
        eu_highly = df[(df["location"] == "EU") & (df["fishing_protection_level"] == "highly")]
        assert len(eu_highly) == 1
        # GBR NAT total_area (2000) + BRA aggregate total_area (3000)
        assert eu_highly.iloc[0]["total_area"] == 5000
        # GBR NAT highly (100+20=120) + BRA highly (300+30=330) = 450
        assert eu_highly.iloc[0]["area"] == 450.0


# ---------------------------------------------------------------------------
# Tests: Protection level calculations
# ---------------------------------------------------------------------------


class TestProtectionLevels:
    def test_all_three_levels_present(
        self, monkeypatch, protected_seas_df, combined_regions, upload_recorder
    ):
        """Output should contain highly, moderately, and less protection levels."""
        df, _ = _run_generate(monkeypatch, protected_seas_df, combined_regions, upload_recorder)
        levels = set(df["fishing_protection_level"].unique())
        assert levels == {"highly", "moderately", "less"}

    def test_highly_is_lfp5_plus_lfp4(
        self, monkeypatch, protected_seas_df, combined_regions, upload_recorder
    ):
        """Highly protected = lfp5 + lfp4."""
        df, _ = _run_generate(monkeypatch, protected_seas_df, combined_regions, upload_recorder)
        bra = df[(df["location"] == "BRA") & (df["fishing_protection_level"] == "highly")].iloc[0]
        assert bra["area"] == 330.0  # 300 + 30

    def test_moderately_is_lfp3(
        self, monkeypatch, protected_seas_df, combined_regions, upload_recorder
    ):
        """Moderately protected = lfp3."""
        df, _ = _run_generate(monkeypatch, protected_seas_df, combined_regions, upload_recorder)
        bra = df[(df["location"] == "BRA") & (df["fishing_protection_level"] == "moderately")].iloc[
            0
        ]
        assert bra["area"] == 150.0

    def test_less_is_lfp2_plus_lfp1(
        self, monkeypatch, protected_seas_df, combined_regions, upload_recorder
    ):
        """Less protected = lfp2 + lfp1."""
        df, _ = _run_generate(monkeypatch, protected_seas_df, combined_regions, upload_recorder)
        bra = df[(df["location"] == "BRA") & (df["fishing_protection_level"] == "less")].iloc[0]
        assert bra["area"] == 120.0  # 80 + 40

    def test_pct_capped_at_100(self, monkeypatch, combined_regions, upload_recorder):
        """Percentage should be capped at 100 even if area > total_area."""
        # Create a row where lfp5+lfp4 > total_area
        ps = pd.DataFrame(
            {
                "iso_sov": ["TST"],
                "iso_ter": [""],
                "total_area": [100.0],
                "lfp5_area": [80.0],
                "lfp4_area": [80.0],  # highly = 160 > total 100
                "lfp3_area": [0.0],
                "lfp2_area": [0.0],
                "lfp1_area": [0.0],
            }
        )
        regions = {**combined_regions, "TST": ["TST"]}
        df, _ = _run_generate(monkeypatch, ps, regions, upload_recorder)
        tst = df[(df["location"] == "TST") & (df["fishing_protection_level"] == "highly")].iloc[0]
        assert tst["pct"] == 100


# ---------------------------------------------------------------------------
# Tests: CRV → HRV fix
# ---------------------------------------------------------------------------


class TestCRVFix:
    def test_crv_remapped_to_hrv(self, monkeypatch, combined_regions, upload_recorder):
        """CRV sovereign code should be remapped to HRV (Croatia)."""
        ps = pd.DataFrame(
            {
                "iso_sov": ["CRV"],
                "iso_ter": [""],
                "total_area": [1000.0],
                "lfp5_area": [100.0],
                "lfp4_area": [10.0],
                "lfp3_area": [50.0],
                "lfp2_area": [20.0],
                "lfp1_area": [5.0],
            }
        )
        regions = {**combined_regions, "HRV": ["HRV"], "GLOB": []}
        df, _ = _run_generate(monkeypatch, ps, regions, upload_recorder)
        assert "CRV" not in df["location"].values
        hrv = df[(df["location"] == "HRV") & (df["fishing_protection_level"] == "highly")]
        assert len(hrv) == 1


# ---------------------------------------------------------------------------
# Tests: Upload
# ---------------------------------------------------------------------------


class TestUpload:
    def test_result_uploaded_to_gcs(
        self, monkeypatch, protected_seas_df, combined_regions, upload_recorder
    ):
        """The resulting table should be uploaded to GCS."""
        _, calls = _run_generate(monkeypatch, protected_seas_df, combined_regions, upload_recorder)
        assert len(calls) == 1
        assert calls[0]["destination_blob_name"] == gen_tables.FISHING_PROTECTION_FILE_NAME

    def test_total_area_is_int64_in_output(
        self, monkeypatch, protected_seas_df, combined_regions, upload_recorder
    ):
        """total_area should be rounded and cast to Int64 in the uploaded dataframe."""
        _, calls = _run_generate(monkeypatch, protected_seas_df, combined_regions, upload_recorder)
        uploaded_df = calls[0]["df"]
        assert uploaded_df["total_area"].dtype == pd.Int64Dtype()

    def test_zero_total_area_rows_filtered(self, monkeypatch, combined_regions, upload_recorder):
        """Rows with total_area <= 0 should be filtered out."""
        ps = pd.DataFrame(
            {
                "iso_sov": ["ZZZ"],
                "iso_ter": [""],
                "total_area": [0.0],
                "lfp5_area": [0.0],
                "lfp4_area": [0.0],
                "lfp3_area": [0.0],
                "lfp2_area": [0.0],
                "lfp1_area": [0.0],
            }
        )
        regions = {**combined_regions, "ZZZ": ["ZZZ"]}
        df, _ = _run_generate(monkeypatch, ps, regions, upload_recorder)
        assert len(df) == 0 or "ZZZ" not in df["location"].values
