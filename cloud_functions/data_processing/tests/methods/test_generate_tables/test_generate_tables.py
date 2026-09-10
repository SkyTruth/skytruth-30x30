import pandas as pd
import pytest

import src.methods.generate_tables as generate_tables


@pytest.fixture
def upload_recorder():
    """Record dataframes uploaded by the protection-coverage table wrapper."""
    calls = []

    def _upload(bucket, df, destination, **kwargs):
        calls.append(
            {
                "bucket": bucket,
                "destination": destination,
                "df": df.copy(),
                "kwargs": kwargs,
            }
        )

    return calls, _upload


def test_generate_protection_coverage_combines_rounds_and_uploads(monkeypatch, upload_recorder):
    """Combine country and IHO rows, round areas, and publish both output datasets."""
    country_coverage = pd.DataFrame(
        [
            {
                "location": "BRA",
                "environment": "marine",
                "total_area": 10.4,
                "protected_area": 2.0,
            }
        ]
    )
    country_areas = country_coverage[["location", "environment", "total_area"]].copy()
    iho_coverage = pd.DataFrame(
        [
            {
                "location": "123",
                "environment": "marine",
                "total_area": 20.6,
                "protected_area": 5.0,
            }
        ]
    )

    country_calls = []
    monkeypatch.setattr(
        generate_tables,
        "compute_country_global_coverage",
        lambda **kwargs: country_calls.append(kwargs) or (country_coverage, country_areas),
    )
    iho_calls = []
    monkeypatch.setattr(
        generate_tables,
        "compute_iho_protection_coverage",
        lambda **kwargs: iho_calls.append(kwargs) or iho_coverage,
    )
    uploads, upload = upload_recorder
    monkeypatch.setattr(generate_tables, "upload_dataframe", upload)

    result = pd.DataFrame(
        generate_tables.generate_protection_coverage_stats_table(
            bucket="bucket",
            project="project",
            protection_coverage_file_name="coverage.csv",
            wdpa_country_level_file_name="country.csv",
            wdpa_global_level_file_name="global.csv",
            verbose=False,
        )
    )

    assert country_calls == [
        {
            "bucket": "bucket",
            "wdpa_country_level_file_name": "country.csv",
            "wdpa_global_level_file_name": "global.csv",
            "percent_type": "area",
            "verbose": False,
        }
    ]
    assert iho_calls == [
        {"bucket": "bucket", "wdpa_global_level_file_name": "global.csv", "verbose": False}
    ]
    assert result.set_index("location")["total_area"].to_dict() == {"BRA": 10, "123": 21}

    assert [call["destination"] for call in uploads] == [
        "coverage.csv",
        "temporary/country_areas.csv",
    ]
    assert uploads[0]["df"]["total_area"].dtype == pd.Int64Dtype()
    assert uploads[1]["df"].equals(country_areas)
    assert all(call["bucket"] == "bucket" for call in uploads)
    assert all(call["kwargs"]["project_id"] == "project" for call in uploads)
