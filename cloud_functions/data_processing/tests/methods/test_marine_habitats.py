import pandas as pd
import pytest

from src.methods.marine_habitats import (
    CLIMATE_RESILIENT_CORALS_HABITATS,
    _rollup_corals_subtable,
)


@pytest.fixture
def country_class_areas():
    """Per-country class areas as compute_class_areas_by_country would emit them."""
    total = pd.DataFrame(
        [
            {"country": "USA", "climate-resilient-corals": 100.0, "other-corals": 50.0},
            {"country": "MEX", "climate-resilient-corals": 20.0, "other-corals": 80.0},
        ]
    )
    protected = pd.DataFrame(
        [
            {"country": "USA", "climate-resilient-corals": 30.0, "other-corals": 10.0},
            {"country": "MEX", "climate-resilient-corals": 5.0, "other-corals": 8.0},
        ]
    )
    return total, protected


@pytest.fixture
def combined_regions():
    return {
        "USA": ["USA"],
        "MEX": ["MEX"],
        "NA": ["USA", "MEX"],
        "GLOB": [],
    }


def test_rollup_emits_one_row_per_habitat_per_location(country_class_areas, combined_regions):
    total, protected = country_class_areas
    result = _rollup_corals_subtable(total, protected, combined_regions)

    expected_rows = len(CLIMATE_RESILIENT_CORALS_HABITATS) * len(combined_regions)
    assert len(result) == expected_rows
    assert set(result["habitat"]) == set(CLIMATE_RESILIENT_CORALS_HABITATS)
    assert set(result["location"]) == set(combined_regions.keys())
    assert (result["environment"] == "marine").all()


def test_rollup_country_passes_through(country_class_areas, combined_regions):
    total, protected = country_class_areas
    result = _rollup_corals_subtable(total, protected, combined_regions)

    usa_crc = result[
        (result["location"] == "USA") & (result["habitat"] == "climate-resilient-corals")
    ].iloc[0]
    assert usa_crc["total_area"] == 100.0
    assert usa_crc["protected_area"] == 30.0


def test_rollup_region_sums_member_countries(country_class_areas, combined_regions):
    total, protected = country_class_areas
    result = _rollup_corals_subtable(total, protected, combined_regions)

    na_crc = result[
        (result["location"] == "NA") & (result["habitat"] == "climate-resilient-corals")
    ].iloc[0]
    # USA + MEX climate-resilient corals
    assert na_crc["total_area"] == 120.0
    assert na_crc["protected_area"] == 35.0

    na_other = result[(result["location"] == "NA") & (result["habitat"] == "other-corals")].iloc[0]
    assert na_other["total_area"] == 130.0
    assert na_other["protected_area"] == 18.0


def test_rollup_glob_sums_all_countries(country_class_areas, combined_regions):
    total, protected = country_class_areas
    result = _rollup_corals_subtable(total, protected, combined_regions)

    glob_crc = result[
        (result["location"] == "GLOB") & (result["habitat"] == "climate-resilient-corals")
    ].iloc[0]
    assert glob_crc["total_area"] == 120.0
    assert glob_crc["protected_area"] == 35.0


def test_rollup_handles_country_missing_from_protected_stats(combined_regions):
    """A country with coral pixels but no PA coverage shouldn't break the rollup."""
    total = pd.DataFrame(
        [
            {"country": "USA", "climate-resilient-corals": 100.0, "other-corals": 50.0},
            {"country": "MEX", "climate-resilient-corals": 20.0, "other-corals": 80.0},
        ]
    )
    protected = pd.DataFrame(
        [{"country": "USA", "climate-resilient-corals": 30.0, "other-corals": 10.0}]
    )

    result = _rollup_corals_subtable(total, protected, combined_regions)

    mex_crc = result[
        (result["location"] == "MEX") & (result["habitat"] == "climate-resilient-corals")
    ].iloc[0]
    assert mex_crc["total_area"] == 20.0
    assert mex_crc["protected_area"] == 0.0


def test_rollup_handles_missing_class_column():
    """If a class never appeared in any country, total_area and protected_area should be 0."""
    total = pd.DataFrame([{"country": "USA", "climate-resilient-corals": 100.0}])
    protected = pd.DataFrame([{"country": "USA", "climate-resilient-corals": 30.0}])
    combined_regions = {"USA": ["USA"], "GLOB": []}

    result = _rollup_corals_subtable(total, protected, combined_regions)

    usa_other = result[(result["location"] == "USA") & (result["habitat"] == "other-corals")].iloc[
        0
    ]
    assert usa_other["total_area"] == 0.0
    assert usa_other["protected_area"] == 0.0


def test_rollup_handles_empty_inputs(combined_regions):
    """Pipeline should still produce structured rows even if no countries had coral pixels."""
    empty = pd.DataFrame()
    result = _rollup_corals_subtable(empty, empty, combined_regions)

    expected_rows = len(CLIMATE_RESILIENT_CORALS_HABITATS) * len(combined_regions)
    assert len(result) == expected_rows
    assert (result["total_area"] == 0).all()
    assert (result["protected_area"] == 0).all()
