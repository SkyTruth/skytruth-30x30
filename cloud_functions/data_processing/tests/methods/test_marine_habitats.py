import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

from src.core.params import UNEP_POINT_AREA_KM2
from src.methods.marine_habitats import (
    CLIMATE_RESILIENT_CORALS_HABITATS,
    _rollup_corals_subtable,
)
from src.methods.static_processes import _buffer_unep_points
from src.utils.geo import get_area_km2


@pytest.fixture
def country_class_areas():
    """Per-country class areas as compute_class_areas_by_country would emit them."""
    total = pd.DataFrame(
        [
            {"location": "USA", "climate-resilient-corals": 100.0, "other-corals": 50.0},
            {"location": "MEX", "climate-resilient-corals": 20.0, "other-corals": 80.0},
        ]
    )
    protected = pd.DataFrame(
        [
            {"location": "USA", "climate-resilient-corals": 30.0, "other-corals": 10.0},
            {"location": "MEX", "climate-resilient-corals": 5.0, "other-corals": 8.0},
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


def test_rollup_glob_falls_back_to_country_sum_without_override(
    country_class_areas, combined_regions
):
    """Without a deduplicated global override, GLOB falls back to summing countries."""
    total, protected = country_class_areas
    result = _rollup_corals_subtable(total, protected, combined_regions)

    glob_crc = result[
        (result["location"] == "GLOB") & (result["habitat"] == "climate-resilient-corals")
    ].iloc[0]
    assert glob_crc["total_area"] == 120.0
    assert glob_crc["protected_area"] == 35.0


def test_rollup_glob_uses_dedup_override_not_country_sum(country_class_areas, combined_regions):
    """Overlapping-claim double counting may inflate a region but must NOT reach GLOB.

    The per-country rows sum to 120 / 130 km² (climate-resilient / other), which is what
    a region like NA still reports. GLOB instead uses the deduplicated global figures
    (each reef pixel counted once over the whole extent), so it is lower than the sum.
    """
    total, protected = country_class_areas
    global_total = {"climate-resilient-corals": 90.0, "other-corals": 110.0}
    global_protected = {"climate-resilient-corals": 25.0, "other-corals": 12.0}

    result = _rollup_corals_subtable(
        total,
        protected,
        combined_regions,
        global_total=global_total,
        global_protected=global_protected,
    )

    glob_crc = result[
        (result["location"] == "GLOB") & (result["habitat"] == "climate-resilient-corals")
    ].iloc[0]
    # GLOB uses the deduplicated override, NOT the 120 country sum
    assert glob_crc["total_area"] == 90.0
    assert glob_crc["protected_area"] == 25.0

    glob_other = result[
        (result["location"] == "GLOB") & (result["habitat"] == "other-corals")
    ].iloc[0]
    assert glob_other["total_area"] == 110.0
    assert glob_other["protected_area"] == 12.0

    # A region still sums its members (double counting is acceptable below GLOB)
    na_crc = result[
        (result["location"] == "NA") & (result["habitat"] == "climate-resilient-corals")
    ].iloc[0]
    assert na_crc["total_area"] == 120.0


def test_rollup_handles_country_missing_from_protected_stats(combined_regions):
    """A country with coral pixels but no PA coverage shouldn't break the rollup."""
    total = pd.DataFrame(
        [
            {"location": "USA", "climate-resilient-corals": 100.0, "other-corals": 50.0},
            {"location": "MEX", "climate-resilient-corals": 20.0, "other-corals": 80.0},
        ]
    )
    protected = pd.DataFrame(
        [{"location": "USA", "climate-resilient-corals": 30.0, "other-corals": 10.0}]
    )

    result = _rollup_corals_subtable(total, protected, combined_regions)

    mex_crc = result[
        (result["location"] == "MEX") & (result["habitat"] == "climate-resilient-corals")
    ].iloc[0]
    assert mex_crc["total_area"] == 20.0
    assert mex_crc["protected_area"] == 0.0


def test_rollup_handles_missing_class_column():
    """If a class never appeared in any country, total_area and protected_area should be 0."""
    total = pd.DataFrame([{"location": "USA", "climate-resilient-corals": 100.0}])
    protected = pd.DataFrame([{"location": "USA", "climate-resilient-corals": 30.0}])
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


def unep_points(geometries, reported_areas):
    """A UNEP-WCMC point layer as process_marine_unep_habitats receives it."""
    return gpd.GeoDataFrame({"REP_AREA_K": reported_areas}, geometry=geometries, crs="EPSG:4326")


@pytest.mark.parametrize(
    "unreported",
    [0, "Not Reported"],
    ids=["zero", "not_reported_string"],
)
def test_unreported_area_falls_back(unreported):
    """Points with no reported area are buffered so that the total area 
    equals UNEP_POINT_AREA_KM2.
    """
    buffered = _buffer_unep_points(unep_points([Point(0, 0)], [unreported]))

    assert get_area_km2(buffered.geometry.iloc[0]) == pytest.approx(UNEP_POINT_AREA_KM2, rel=0.01)


def test_antimeridian_buffer_preserves_geometry_without_wrapping():
    """A point on the dateline must be split across it are retain the same area."""
    geometry = _buffer_unep_points(unep_points([Point(180, -48)], [0])).geometry.iloc[0]

    assert get_area_km2(geometry) == pytest.approx(UNEP_POINT_AREA_KM2, rel=0.01)
    assert geometry.geom_type == "MultiPolygon"
    assert min(part.bounds[0] for part in geometry.geoms) < -179
    assert max(part.bounds[2] for part in geometry.geoms) > 179
