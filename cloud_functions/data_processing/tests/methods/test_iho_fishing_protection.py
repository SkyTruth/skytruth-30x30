import geopandas as gpd
import pytest
from shapely.geometry import box

import src.methods.generate_tables as generate_tables


def _run_iho_fishing_stats(monkeypatch, iho, sites):
    monkeypatch.setattr(
        generate_tables, "load_iho_regions", lambda *args, **kwargs: iho.copy()
    )
    monkeypatch.setattr(
        generate_tables, "read_parquet_from_gcs", lambda *args, **kwargs: sites.copy()
    )
    return generate_tables.get_iho_fishing_protection_region_stats(
        sites_file_name="sites.parquet",
        bucket="bucket",
        verbose=False,
    )


def test_iho_fishing_stats_only_include_highly_protected_sites(monkeypatch):
    """Exclude sites below the highly protected fishing level."""
    iho = gpd.GeoDataFrame(
        {"MRGID": ["sea"], "area": [2.0]},
        geometry=[box(0, 0, 2000, 1000)],
        crs="EPSG:6933",
    )
    sites = gpd.GeoDataFrame(
        {"fishing_protection_level": ["highly", "moderately"]},
        geometry=[box(0, 0, 500, 1000), box(500, 0, 1500, 1000)],
        crs="EPSG:6933",
    )

    result = _run_iho_fishing_stats(monkeypatch, iho, sites).iloc[0]

    assert result["location"] == "sea"
    assert result["fishing_protection_level"] == "highly"
    assert result["total_area"] == 2.0
    assert result["area"] == pytest.approx(0.5)
    assert result["pct"] == pytest.approx(25.0)


def test_iho_fishing_stats_dissolve_overlapping_sites(monkeypatch):
    """Dissolve overlapping highly protected sites before measuring area."""
    iho = gpd.GeoDataFrame(
        {"MRGID": ["sea"], "area": [2.0]},
        geometry=[box(0, 0, 2000, 1000)],
        crs="EPSG:6933",
    )
    sites = gpd.GeoDataFrame(
        {"fishing_protection_level": ["highly", "highly"]},
        geometry=[box(0, 0, 1200, 1000), box(800, 0, 2000, 1000)],
        crs="EPSG:6933",
    )

    result = _run_iho_fishing_stats(monkeypatch, iho, sites).iloc[0]

    # The two 1.2 km² sites overlap by 0.4 km², producing a 2 km² union.
    assert result["area"] == pytest.approx(2.0)
    assert result["pct"] == pytest.approx(100.0)


def test_iho_fishing_stats_clip_sites_to_each_sea(monkeypatch):
    """Clip a protected site independently to every IHO sea it crosses."""
    iho = gpd.GeoDataFrame(
        {
            "MRGID": ["west", "east"],
            "area": [1.0, 1.0],
        },
        geometry=[box(0, 0, 1000, 1000), box(1000, 0, 2000, 1000)],
        crs="EPSG:6933",
    )
    sites = gpd.GeoDataFrame(
        {"fishing_protection_level": ["highly"]},
        geometry=[box(500, 0, 1500, 1000)],
        crs="EPSG:6933",
    )

    result = _run_iho_fishing_stats(monkeypatch, iho, sites).set_index("location")

    assert set(result.index) == {"west", "east"}
    assert result.loc["west", "area"] == pytest.approx(0.5)
    assert result.loc["east", "area"] == pytest.approx(0.5)
    assert result.loc["west", "pct"] == pytest.approx(50.0)
    assert result.loc["east", "pct"] == pytest.approx(50.0)


def test_iho_fishing_stats_return_empty_result_without_highly_protected_sites(monkeypatch):
    """Return a structured empty result when no sites are highly protected."""
    iho = gpd.GeoDataFrame(
        {"MRGID": ["sea"], "area": [1.0]},
        geometry=[box(0, 0, 1000, 1000)],
        crs="EPSG:6933",
    )
    sites = gpd.GeoDataFrame(
        {"fishing_protection_level": ["moderately"]},
        geometry=[box(0, 0, 500, 1000)],
        crs="EPSG:6933",
    )

    result = _run_iho_fishing_stats(monkeypatch, iho, sites)

    assert result.empty
    assert list(result.columns) == [
        "location",
        "area",
        "fishing_protection_level",
        "pct",
        "total_area",
    ]
