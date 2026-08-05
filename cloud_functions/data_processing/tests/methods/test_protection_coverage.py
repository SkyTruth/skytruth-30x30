import geopandas as gpd
import pytest
from shapely.geometry import Polygon, box

import src.methods.protection_coverage as protection_coverage


def _iho_gdf(rows):
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:6933")


def _pa_gdf(rows):
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:6933")


def _run_coverage(monkeypatch, iho, pas):
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
    return protection_coverage.compute_iho_protection_coverage(
        bucket="bucket", tolerance=0.1, verbose=False
    )


def test_iho_coverage_returns_zero_when_spatial_index_has_no_candidates(monkeypatch):
    """Return zero coverage when no protected-area bounding boxes overlap a sea."""
    iho = _iho_gdf([{"MRGID": 10, "geometry": box(0, 0, 1000, 1000)}])
    pas = _pa_gdf([{"PA_DEF": 1, "geometry": box(5000, 5000, 6000, 6000)}])

    result = _run_coverage(monkeypatch, iho, pas).iloc[0]

    assert result["location"] == "10"
    assert result["environment"] == "marine"
    assert result["total_area"] == 1.0
    assert result["protected_area"] == 0.0
    assert result["coverage"] == 0.0
    assert result["pas"] == 0.0
    assert result["oecms"] == 0.0
    assert result["protected_areas_count"] == 0


def test_iho_coverage_discards_bbox_false_positive(monkeypatch):
    """Discard bounding-box candidates whose actual geometries do not intersect."""
    iho = _iho_gdf([{"MRGID": "sea", "geometry": box(0, 0, 1000, 1000)}])
    # The bounding boxes overlap in the 900-1000 corner, but the triangle itself
    # lies above and to the right of the sea (x + y is always at least 2900).
    false_positive = Polygon([(900, 2000), (2000, 900), (2000, 2000)])
    pas = _pa_gdf([{"PA_DEF": 1, "geometry": false_positive}])

    result = _run_coverage(monkeypatch, iho, pas).iloc[0]

    assert result["protected_area"] == 0.0
    assert result["protected_areas_count"] == 0


def test_iho_coverage_dissolves_overlapping_protected_areas(monkeypatch):
    """Dissolve overlapping protected areas to prevent double-counting."""
    iho = _iho_gdf([{"MRGID": "sea", "geometry": box(0, 0, 2000, 1000)}])
    pas = _pa_gdf(
        [
            {"PA_DEF": 1, "geometry": box(0, 0, 1200, 1000)},
            {"PA_DEF": 1, "geometry": box(800, 0, 2000, 1000)},
        ]
    )

    result = _run_coverage(monkeypatch, iho, pas).iloc[0]

    # The polygons overlap by 0.4 km², so their dissolved union is the 2 km² sea,
    # not the naive 2.4 km² sum.
    assert result["total_area"] == 2.0
    assert result["protected_area"] == 2.0
    assert result["coverage"] == 100.0
    assert result["pas"] == 100.0
    assert result["oecms"] == 0.0
    assert result["protected_areas_count"] == 2


def test_iho_coverage_calculates_pa_and_oecm_shares(monkeypatch):
    """Calculate overall coverage and the PA/OECM shares of protected area."""
    iho = _iho_gdf([{"MRGID": "sea", "geometry": box(0, 0, 2000, 1000)}])
    pas = _pa_gdf(
        [
            {"PA_DEF": 1, "geometry": box(0, 0, 500, 1000)},
            {"PA_DEF": 0, "geometry": box(1000, 0, 1500, 1000)},
        ]
    )

    result = _run_coverage(monkeypatch, iho, pas).iloc[0]

    assert result["protected_area"] == 1.0
    assert result["coverage"] == 50.0
    assert result["pas"] == 50.0
    assert result["oecms"] == 50.0
    assert result["protected_areas_count"] == 2


def test_iho_coverage_keeps_results_independent_for_each_sea(monkeypatch):
    """Calculate each IHO sea independently and retain zero-coverage seas."""
    iho = _iho_gdf(
        [
            {"MRGID": 1, "geometry": box(0, 0, 1000, 1000)},
            {"MRGID": 2, "geometry": box(2000, 0, 3000, 1000)},
        ]
    )
    pas = _pa_gdf([{"PA_DEF": 1, "geometry": box(0, 0, 500, 1000)}])

    result = _run_coverage(monkeypatch, iho, pas).set_index("location")

    assert set(result.index) == {"1", "2"}
    assert result.loc["1", "coverage"] == pytest.approx(50.0)
    assert result.loc["2", "coverage"] == 0.0
