import ast

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Polygon, box

import src.methods.protection_coverage as protection_coverage


def _iho_gdf(rows):
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:6933")


def _pa_gdf(rows):
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:6933")


def _run_coverage(monkeypatch, iho, pas, wdpa_global):
    monkeypatch.setattr(
        protection_coverage,
        "read_parquet_from_gcs",
        lambda **_: iho.copy(),
    )
    monkeypatch.setattr(
        protection_coverage,
        "read_json_df",
        lambda **_: pas.copy(),
    )
    monkeypatch.setattr(
        protection_coverage, "load_wdpa_global", lambda *_, **__: wdpa_global.copy()
    )
    return protection_coverage.compute_iho_protection_coverage(
        bucket="bucket", tolerance=0.1, verbose=False
    )


@pytest.fixture
def wdpa_country():
    """Minimal country-level marine and terrestrial WDPA statistics."""
    return pd.DataFrame(
        {
            "id": ["BRA"],
            "pas_count": [10],
            "statistics": [
                str(
                    {
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
                    }
                )
            ],
        }
    )


@pytest.fixture
def wdpa_global():
    """Minimal global WDPA values used for GLOB and ABNJ calculations."""
    return pd.DataFrame(
        {
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
                36_319_197.0,
                5_000_000.0,
                10.0,
                500,
                15_000_000.0,
                3_000_000.0,
                10.0,
                300,
                1_000_000.0,
                1.75,
                20_000_000.0,
                25_000_000.0,
                64.0,
            ],
        }
    )


@pytest.fixture
def combined_regions():
    """Country and global groupings needed by the coverage calculation."""
    return {"BRA": ["BRA"], "GLOB": []}


def _run_country_global_coverage(monkeypatch, wdpa_country, wdpa_global, combined_regions):
    monkeypatch.setattr(protection_coverage, "load_regions", lambda **_: (combined_regions, {}))
    monkeypatch.setattr(protection_coverage, "read_dataframe", lambda *_, **__: wdpa_country.copy())
    monkeypatch.setattr(
        protection_coverage, "load_wdpa_global", lambda *_, **__: wdpa_global.copy()
    )
    table, country_areas = protection_coverage.compute_country_global_coverage(verbose=False)
    return table, country_areas


def _get_country_global_row(df, location, environment="marine"):
    rows = df[(df["location"] == location) & (df["environment"] == environment)]
    assert len(rows) == 1, f"Expected 1 row for {location}/{environment}, got {len(rows)}"
    return rows.iloc[0]


def _global_value(wdpa_global, stat_type):
    return float(wdpa_global.loc[wdpa_global["type"] == stat_type, "value"].iloc[0])


def _global_area(wdpa_global, environment2):
    """Global area the fixture implies: its protected area over the share of the globe it covers."""
    protected_area = _global_value(wdpa_global, f"total_{environment2}_area_oecms_pas")
    coverage = _global_value(wdpa_global, f"total_{environment2}_oecms_pas_coverage_percentage")
    return protected_area * 100 / coverage


def _country_stat(wdpa_country, key):
    return ast.literal_eval(wdpa_country["statistics"].iloc[0])[key]


def test_country_global_coverage_calculates_global_marine_area(
    monkeypatch, wdpa_country, wdpa_global, combined_regions
):
    """Back-calculate global marine area from protected area and coverage."""
    table, _ = _run_country_global_coverage(
        monkeypatch, wdpa_country, wdpa_global, combined_regions
    )

    row = _get_country_global_row(table, "GLOB")
    assert row["total_area"] == pytest.approx(_global_area(wdpa_global, "ocean"))


def test_country_global_coverage_calculates_global_terrestrial_area(
    monkeypatch, wdpa_country, wdpa_global, combined_regions
):
    """Back-calculate global terrestrial area from protected area and coverage."""
    table, _ = _run_country_global_coverage(
        monkeypatch, wdpa_country, wdpa_global, combined_regions
    )

    row = _get_country_global_row(table, "GLOB", environment="terrestrial")
    assert row["total_area"] == pytest.approx(_global_area(wdpa_global, "land"))


def test_country_global_coverage_sets_global_contribution(
    monkeypatch, wdpa_country, wdpa_global, combined_regions
):
    """Use global coverage as the global row's contribution percentage."""
    table, _ = _run_country_global_coverage(
        monkeypatch, wdpa_country, wdpa_global, combined_regions
    )

    row = _get_country_global_row(table, "GLOB")
    assert row["global_contribution"] == _global_value(
        wdpa_global, "total_ocean_oecms_pas_coverage_percentage"
    )


def test_country_global_coverage_measures_group_contribution_against_global_area(
    monkeypatch, wdpa_country, wdpa_global, combined_regions
):
    """Compare a group's protected area to the global area, not to its own coverage."""
    table, _ = _run_country_global_coverage(
        monkeypatch, wdpa_country, wdpa_global, combined_regions
    )

    marine = _get_country_global_row(table, "BRA")
    terrestrial = _get_country_global_row(table, "BRA", environment="terrestrial")

    assert marine["global_contribution"] == pytest.approx(
        100
        * _country_stat(wdpa_country, "oecms_pa_marine_area")
        / _global_area(wdpa_global, "ocean")
    )
    assert terrestrial["global_contribution"] == pytest.approx(
        100 * _country_stat(wdpa_country, "oecms_pa_land_area") / _global_area(wdpa_global, "land")
    )


def test_country_global_coverage_calculates_unrounded_abnj_area(
    monkeypatch, wdpa_country, wdpa_global, combined_regions
):
    """Calculate ABNJ area without the table wrapper's output rounding."""
    table, _ = _run_country_global_coverage(
        monkeypatch, wdpa_country, wdpa_global, combined_regions
    )

    row = _get_country_global_row(table, "ABNJ")
    assert row["total_area"] == pytest.approx(
        _global_area(wdpa_global, "ocean")
        * _global_value(wdpa_global, "global_ocean_percentage")
        / 100
    )


def test_iho_coverage_returns_zero_when_spatial_index_has_no_candidates(monkeypatch, wdpa_global):
    """Return zero coverage when no protected-area bounding boxes overlap a sea."""
    iho = _iho_gdf([{"MRGID": 10, "geometry": box(0, 0, 1000, 1000)}])
    pas = _pa_gdf([{"PA_DEF": 1, "geometry": box(5000, 5000, 6000, 6000)}])

    result = _run_coverage(monkeypatch, iho, pas, wdpa_global).iloc[0]

    assert result["location"] == "10"
    assert result["environment"] == "marine"
    assert result["total_area"] == 1.0
    assert result["protected_area"] == 0.0
    assert result["coverage"] == 0.0
    assert result["pas"] == 0.0
    assert result["oecms"] == 0.0
    assert result["protected_areas_count"] == 0
    assert result["global_contribution"] == 0.0


def test_iho_coverage_discards_bbox_false_positive(monkeypatch, wdpa_global):
    """Discard bounding-box candidates whose actual geometries do not intersect."""
    iho = _iho_gdf([{"MRGID": "sea", "geometry": box(0, 0, 1000, 1000)}])
    # The bounding boxes overlap in the 900-1000 corner, but the triangle itself
    # lies above and to the right of the sea (x + y is always at least 2900).
    false_positive = Polygon([(900, 2000), (2000, 900), (2000, 2000)])
    pas = _pa_gdf([{"PA_DEF": 1, "geometry": false_positive}])

    result = _run_coverage(monkeypatch, iho, pas, wdpa_global).iloc[0]

    assert result["protected_area"] == 0.0
    assert result["protected_areas_count"] == 0


def test_iho_coverage_dissolves_overlapping_protected_areas(monkeypatch, wdpa_global):
    """Dissolve overlapping protected areas to prevent double-counting."""
    iho = _iho_gdf([{"MRGID": "sea", "geometry": box(0, 0, 2000, 1000)}])
    pas = _pa_gdf(
        [
            {"PA_DEF": 1, "geometry": box(0, 0, 1200, 1000)},
            {"PA_DEF": 1, "geometry": box(800, 0, 2000, 1000)},
        ]
    )

    result = _run_coverage(monkeypatch, iho, pas, wdpa_global).iloc[0]

    # The polygons overlap by 0.4 km², so their dissolved union is the 2 km² sea,
    # not the naive 2.4 km² sum.
    assert result["total_area"] == 2.0
    assert result["protected_area"] == 2.0
    assert result["coverage"] == 100.0
    assert result["pas"] == 100.0
    assert result["oecms"] == 0.0
    assert result["protected_areas_count"] == 2


def test_iho_coverage_calculates_pa_and_oecm_shares(monkeypatch, wdpa_global):
    """Calculate overall coverage and the PA/OECM shares of protected area."""
    iho = _iho_gdf([{"MRGID": "sea", "geometry": box(0, 0, 2000, 1000)}])
    pas = _pa_gdf(
        [
            {"PA_DEF": 1, "geometry": box(0, 0, 500, 1000)},
            {"PA_DEF": 0, "geometry": box(1000, 0, 1500, 1000)},
        ]
    )

    result = _run_coverage(monkeypatch, iho, pas, wdpa_global).iloc[0]

    assert result["protected_area"] == 1.0
    assert result["coverage"] == 50.0
    assert result["pas"] == 50.0
    assert result["oecms"] == 50.0
    assert result["protected_areas_count"] == 2


def test_iho_coverage_keeps_results_independent_for_each_sea(monkeypatch, wdpa_global):
    """Calculate each IHO sea independently and retain zero-coverage seas."""
    iho = _iho_gdf(
        [
            {"MRGID": 1, "geometry": box(0, 0, 1000, 1000)},
            {"MRGID": 2, "geometry": box(2000, 0, 3000, 1000)},
        ]
    )
    pas = _pa_gdf([{"PA_DEF": 1, "geometry": box(0, 0, 500, 1000)}])

    result = _run_coverage(monkeypatch, iho, pas, wdpa_global).set_index("location")

    assert set(result.index) == {"1", "2"}
    assert result.loc["1", "coverage"] == pytest.approx(50.0)
    assert result.loc["2", "coverage"] == 0.0


def test_iho_coverage_measures_global_contribution_against_global_ocean_area(
    monkeypatch, wdpa_global
):
    """Express a sea's protected area as a share of the whole ocean, not of the sea."""
    # 2 million km² sea, half of it protected.
    iho = _iho_gdf([{"MRGID": "sea", "geometry": box(0, 0, 2_000_000, 1_000_000)}])
    pas = _pa_gdf([{"PA_DEF": 1, "geometry": box(0, 0, 1_000_000, 1_000_000)}])
    protected_km2 = 1_000_000

    result = _run_coverage(monkeypatch, iho, pas, wdpa_global).iloc[0]

    assert result["coverage"] == 50.0
    assert result["global_contribution"] == pytest.approx(
        round(100 * protected_km2 / _global_area(wdpa_global, "ocean"), 2)
    )
