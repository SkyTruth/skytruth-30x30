import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import Point

import src.methods.static_processes.eez as eez_module
from src.methods.static_processes.eez import (
    _pick_eez_parents,
    _proccess_eez_multiple_sovs,
    _process_eez_by_sov,
)


@pytest.fixture
def mock_eez():
    """
    Minimal EEZ features with ISO_TER#/ISO_SOV# columns so _pick_eez_parents can run.
    Includes:
      - A shared area (2 parents)
      - A single-parent area
    """
    crs = "EPSG:4326"
    df = gpd.GeoDataFrame(
        {
            "ISO_TER1": ["PRI", None],
            "ISO_SOV1": ["USA", "AAA"],
            "ISO_TER2": [None, None],
            "ISO_SOV2": ["AAA", "FRA"],
            "ISO_TER3": [None, None],
            "ISO_SOV3": ["AAA", None],
            "AREA_KM2": [10.0, 5.0],
            "MRGID": [101, 102],
            "POL_TYPE": ["EEZ", "EEZ"],
            "geometry": [Point(0, 0).buffer(1.0), Point(3, 0).buffer(1.0)],
        },
        crs=crs,
    )
    return df


@pytest.fixture
def mock_high_seas():
    """
    Minimal High Seas slice. process_eez_geoms overwrites several columns; keep what's needed.
    """
    crs = "EPSG:4326"
    df = gpd.GeoDataFrame(
        {
            "area_km2": [1000.0],
            "mrgid": [63203],
            "POL_TYPE": ["HS"],
            "GEONAME": ["HS"],
            "geometry": [Point(20, 20).buffer(2.0)],
        },
        crs=crs,
    )
    return df


@pytest.fixture
def mock_eez_translations():
    """Translations keyed by MRGID."""
    return pd.DataFrame(
        {
            "MRGID": [101, 102, 999],
            "name": ["Area A", "Area B", "High Seas"],
            "name_es": ["Zona A", "Zona B", "Alta Mar"],
            "name_fr": ["Zone A", "Zone B", "Haute mer"],
            "name_pt": ["Área A", "Área B", "Alto-mar"],
            "name_id": ["Área A", "Área B", "Laut Lepas"],
            "name_sw": ["Área A", "Área B", "Bahari Kuu"],
        }
    )


def _mock_clean_geometries(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Mock clean geometries processor
    """
    return gpd.GeoDataFrame(gdf.copy(), crs=gdf.crs)


def _mock_load_marine_regions(eez_gdf, hs_gdf):
    """Return a loader that returns EEZ for EEZ_PARAMS and HS for HIGH_SEAS_PARAMS."""

    def _loader(params, bucket):
        if params is eez_module.EEZ_PARAMS:
            return eez_gdf.copy()
        if params is eez_module.HIGH_SEAS_PARAMS:
            return hs_gdf.copy()
        raise ValueError("Unexpected params passed to load_marine_regions")

    return _loader


def _mock_load_iho_regions(buffer=False):
    """Two IHO sea areas, keyed on MRGID like the real loader."""
    return gpd.GeoDataFrame(
        {"MRGID": ["1", "2"], "location": ["1", "2"]},
        geometry=[Point(30, 30).buffer(1.0), Point(40, 40).buffer(1.0)],
        crs="EPSG:4326",
    )


def _mock_read_dataframe(translations_df):
    def _reader(bucket, blob_name):
        return translations_df.copy()

    return _reader


def _mock_read_json_from_gcs(json):
    def _reader(bucket, blob_name, verbose=True):
        return json

    return _reader


def test_pick_eez_parents_basic(mock_related_countries_map):
    row = pd.Series(
        {
            "ISO_TER1": "MYT",
            "ISO_SOV1": "COM",
            "ISO_TER2": "MYT",
            "ISO_SOV2": "FRA",
            "ISO_TER3": None,
            "ISO_SOV3": None,
        }
    )
    parents, sovs = _pick_eez_parents(row, mock_related_countries_map)
    # MYT should be chosen (deduped), no None, order not guaranteed
    assert set(parents) == {"MYT"}
    assert set(sovs) == {"COM*", "FRA*"}


def test_process_eez_by_sov_happy_path(mock_eez, mock_high_seas, mock_related_countries_map):
    # Precompute parents like process_eez_geoms would
    eez = mock_eez.copy()
    eez[["parents", "sovs"]] = eez.apply(
        _pick_eez_parents, args=(mock_related_countries_map,), axis=1, result_type="expand"
    )
    eez.loc[eez["parents"].apply(lambda parents: len(parents) > 1), "has_shared_marine_area"] = True

    # Emulate high seas standardization done in process_eez_geoms
    hs = mock_high_seas.copy()
    hs[["GID_0"]] = "ABNJ"
    hs[["ISO_SOV1"]] = "ABNJ"
    hs[["POL_TYPE"]] = "High Seas"
    hs[["GEONAME"]] = "High Seas"
    hs[["has_shared_marine_area"]] = False
    hs.rename(columns={"area_km2": "AREA_KM2", "mrgid": "MRGID"}, inplace=True)

    out = _process_eez_by_sov(eez, hs)

    # Structure checks
    assert isinstance(out, gpd.GeoDataFrame)
    assert set(["location", "AREA_KM2", "has_shared_marine_area", "geometry"]).issubset(out.columns)

    assert {"AAA", "PRI", "ABNJ"}.issubset(set(out["location"]))

    np.testing.assert_array_equal(out["location"].unique(), out["location"])

    shared_area = out[out["location"] == "AAA"]
    assert shared_area.loc[0, "AREA_KM2"] == 15  # sum of shared area locations
    assert shared_area.loc[0, "has_shared_marine_area"]


def test_proccess_eez_multiple_sovs_happy_path(
    mock_eez, mock_high_seas, mock_eez_translations, mock_related_countries_map
):
    eez = mock_eez.copy()
    eez[["parents", "sovs"]] = eez.apply(
        _pick_eez_parents, args=(mock_related_countries_map,), axis=1, result_type="expand"
    )

    # Standardize HS as process_eez_geoms does
    hs = mock_high_seas.copy()
    hs[["GID_0"]] = "ABNJ"
    hs[["ISO_SOV1"]] = "ABNJ"
    hs[["POL_TYPE"]] = "High Seas"
    hs[["GEONAME"]] = "High Seas"
    hs[["has_shared_marine_area"]] = False
    hs.rename(columns={"area_km2": "AREA_KM2", "mrgid": "MRGID"}, inplace=True)

    out = _proccess_eez_multiple_sovs(eez, hs, mock_eez_translations)

    # Structure checks
    assert isinstance(out, gpd.GeoDataFrame)
    expect_cols = {
        "ISO_SOV1",
        "ISO_SOV2",
        "ISO_SOV3",
        "ISO_TER1",
        "ISO_TER2",
        "ISO_TER3",
        "geometry",
        "AREA_KM2",
        "POL_TYPE",
        "MRGID",
        "name",
        "name_es",
        "name_fr",
        "name_pt",
        "name_id",
        "name_sw",
    }

    assert expect_cols.issubset(out.columns)

    row1 = out[out["MRGID"] == 101].iloc[0]
    ters = ["AAA", "PRI"]
    assert row1["ISO_TER1"] in ters
    assert row1["ISO_SOV1"] == "USA*"
    assert row1["ISO_TER2"] in ters
    assert row1["ISO_SOV2"] is None
    assert row1["ISO_TER3"] is None
    assert row1["ISO_SOV3"] is None

    row2 = out[out["MRGID"] == 102].iloc[0]
    ters = ["FRA", "AAA"]
    assert row2["ISO_TER1"] in ters
    assert row2["ISO_TER2"] in ters
    assert row2["ISO_SOV1"] == "FRA*"


def test_process_eez_geoms_happy_path(
    monkeypatch,
    uploads_recorder,
    mock_eez,
    mock_high_seas,
    mock_eez_translations,
    mock_related_countries_map,
):
    calls, upload_gdf_mock = uploads_recorder

    eez = mock_eez.copy()
    hs = mock_high_seas.copy()

    # Patch dependencies in the module under test
    monkeypatch.setattr(
        eez_module, "load_marine_regions", _mock_load_marine_regions(eez, hs), raising=True
    )
    monkeypatch.setattr(
        eez_module,
        "read_dataframe",
        _mock_read_dataframe(mock_eez_translations),
        raising=True,
    )
    monkeypatch.setattr(
        eez_module,
        "read_json_from_gcs",
        _mock_read_json_from_gcs(mock_related_countries_map),
    )
    monkeypatch.setattr(eez_module, "clean_geometries", _mock_clean_geometries, raising=True)
    monkeypatch.setattr(eez_module, "upload_gdf", upload_gdf_mock, raising=True)
    monkeypatch.setattr(eez_module, "load_iho_regions", _mock_load_iho_regions, raising=True)
    monkeypatch.setattr(eez_module, "TOLERANCE", 0.7, raising=True)
    monkeypatch.setattr(eez_module, "EEZ_FILE_NAME", "eez.geojson", raising=True)
    monkeypatch.setattr(eez_module, "EEZ_MULTIPLE_SOV_FILE_NAME", "eez_multi.geojson", raising=True)
    monkeypatch.setattr(
        eez_module, "MARINE_LOCATIONS_FILE_NAME", "marine_locations.geojson", raising=True
    )

    resp = eez_module.process_eez_geoms(
        eez_file_name=eez_module.EEZ_FILE_NAME,
        eez_params=eez_module.EEZ_PARAMS,
        bucket="test-bucket",
        related_countries_file_name=eez_module.RELATED_COUNTRIES_FILE_NAME,
        tolerance=eez_module.TOLERANCE,
        verbose=False,
    )
    # Function returns None; uploads recorded via our mock
    assert resp is None

    # One eez_by_sov upload + the eez/IHO locations + one final multi-sov upload
    assert len(calls) == 3

    assert calls[0]["destination_blob"] == f"eez_{eez_module.TOLERANCE}.geojson"
    assert calls[1]["destination_blob"] == f"marine_locations_{eez_module.TOLERANCE}.geojson"
    assert calls[2]["destination_blob"] == f"eez_multi_{eez_module.TOLERANCE}.geojson"

    # The locations file carries both the EEZs and the IHO sea areas
    marine_locations = calls[1]["df"]
    assert {"AAA", "PRI", "ABNJ"}.issubset(set(marine_locations["location"]))
    assert {"1", "2"}.issubset(set(marine_locations["location"]))

    # Basic structure of uploaded frames
    for c in calls:
        df = c["df"]
        assert isinstance(df, gpd.GeoDataFrame)
        assert df.crs is not None


def test_process_eez_geoms_loader_failure(
    monkeypatch,
    uploads_recorder,
    mock_eez,
    mock_high_seas,
    mock_eez_translations,
    mock_related_countries_map,
):
    calls, upload_gdf_mock = uploads_recorder

    def failing_loader(params, bucket):
        raise RuntimeError("load failed")

    monkeypatch.setattr(eez_module, "load_marine_regions", failing_loader, raising=True)
    monkeypatch.setattr(
        eez_module,
        "read_dataframe",
        _mock_read_dataframe(mock_eez_translations),
        raising=True,
    )
    monkeypatch.setattr(
        eez_module,
        "read_json_from_gcs",
        _mock_read_json_from_gcs(mock_related_countries_map),
    )
    monkeypatch.setattr(eez_module, "clean_geometries", lambda g: g, raising=True)
    monkeypatch.setattr(eez_module, "upload_gdf", upload_gdf_mock, raising=True)
    monkeypatch.setattr(eez_module, "EEZ_FILE_NAME", "eez.geojson", raising=True)
    monkeypatch.setattr(eez_module, "EEZ_MULTIPLE_SOV_FILE_NAME", "eez_multi.geojson", raising=True)

    with pytest.raises(RuntimeError, match="load failed"):
        eez_module.process_eez_geoms(verbose=False)

    assert calls == []


def test_process_eez_geoms_missing_columns(
    monkeypatch, uploads_recorder, mock_eez_translations, mock_related_countries_map
):
    """
    If EEZ input lacks required columns, we should fail before uploading.
    e.g., remove ISO_TER#/ISO_SOV# so _pick_eez_parents explodes.
    """
    calls, upload_gdf_mock = uploads_recorder

    crs = "EPSG:4326"
    bad_eez = gpd.GeoDataFrame(
        {
            "AREA_KM2": [1.0],
            "MRGID": [1],
            "POL_TYPE": ["EEZ"],
            "geometry": [Point(0, 0).buffer(1.0)],
            # Missing ISO_TER#/ISO_SOV#
        },
        crs=crs,
    )
    hs = gpd.GeoDataFrame(
        {
            "area_km2": [1.0],
            "mrgid": [2],
            "POL_TYPE": ["HS"],
            "GEONAME": ["HS"],
            "geometry": [Point(1, 1).buffer(1.0)],
        },
        crs=crs,
    )

    monkeypatch.setattr(
        eez_module,
        "load_marine_regions",
        _mock_load_marine_regions(bad_eez, hs),
        raising=True,
    )
    monkeypatch.setattr(
        eez_module,
        "read_dataframe",
        _mock_read_dataframe(mock_eez_translations),
        raising=True,
    )
    monkeypatch.setattr(
        eez_module,
        "read_json_from_gcs",
        _mock_read_json_from_gcs(mock_related_countries_map),
    )
    monkeypatch.setattr(eez_module, "clean_geometries", lambda g: g, raising=True)
    monkeypatch.setattr(eez_module, "upload_gdf", upload_gdf_mock, raising=True)

    with pytest.raises(AttributeError):
        eez_module.process_eez_geoms(verbose=False)

    assert calls == []


@pytest.fixture
def mock_eez_land_union():
    """
    Minimal Marine Regions EEZ-land-union features exercising the parent logic:
      - NIC: ordinary single-territory feature.
      - A bank with no ISO_TER and a single ISO_SOV (COL) -> attributed to COL only.
      - A disputed feature with no ISO_TER and two ISO_SOVs (SDN, EGY)
        -> attributed to BOTH claimants (intentional over-attribution).
    """
    crs = "EPSG:4326"
    return gpd.GeoDataFrame(
        {
            "ISO_TER1": ["NIC", None, None],
            "ISO_SOV1": ["NIC", "COL", "SDN"],
            "ISO_TER2": [None, None, None],
            "ISO_SOV2": [None, None, "EGY"],
            "ISO_TER3": [None, None, None],
            "ISO_SOV3": [None, None, None],
            "geometry": [
                Point(0, 0).buffer(1.0),
                Point(5, 0).buffer(1.0),
                Point(10, 0).buffer(1.0),
            ],
        },
        crs=crs,
    )


def test_process_eez_land_union_happy_path(
    monkeypatch, uploads_recorder, mock_eez_land_union, mock_related_countries_map
):
    calls, upload_gdf_mock = uploads_recorder
    union = mock_eez_land_union.copy()

    def _loader(params, bucket):
        assert params is eez_module.EEZ_LAND_UNION_PARAMS
        return union.copy()

    monkeypatch.setattr(eez_module, "load_marine_regions", _loader, raising=True)
    monkeypatch.setattr(
        eez_module,
        "read_json_from_gcs",
        _mock_read_json_from_gcs(mock_related_countries_map),
    )
    monkeypatch.setattr(eez_module, "clean_geometries", _mock_clean_geometries, raising=True)
    monkeypatch.setattr(eez_module, "upload_gdf", upload_gdf_mock, raising=True)

    resp = eez_module.process_eez_land_union(
        eez_land_union_params=eez_module.EEZ_LAND_UNION_PARAMS,
        gadm_eez_union_file_name="GADM_eez_union.geojson",
        related_countries_file_name=eez_module.RELATED_COUNTRIES_FILE_NAME,
        tolerance=0.001,
        bucket="test-bucket",
        verbose=False,
    )
    # Function returns None; uploads recorded via our mock
    assert resp is None

    # A single upload to the tolerance-suffixed union file consumed downstream
    assert len(calls) == 1
    out = calls[0]
    assert out["destination_blob"] == "GADM_eez_union_0.001.geojson"

    df = out["df"]
    assert isinstance(df, gpd.GeoDataFrame)
    assert set(df.columns) == {"location", "geometry"}
    assert df.crs is not None

    locations = set(df["location"])
    # Single-territory feature and single-sovereign bank attributed to their owner
    assert {"NIC", "COL"}.issubset(locations)
    # Disputed feature double-counted to BOTH claimants
    assert {"SDN", "EGY"}.issubset(locations)
    # One row per location (exploded then dissolved)
    assert len(df) == df["location"].nunique()


def test_process_eez_land_union_no_fill_preserves_holes(
    monkeypatch, uploads_recorder, mock_related_countries_map
):
    """A neighbour's enclave carved out as a hole must NOT be filled/swallowed."""
    calls, upload_gdf_mock = uploads_recorder

    # NIC EEZ is a ring with a hole; a separate COL feature sits inside that hole.
    nic_with_hole = Point(0, 0).buffer(5.0).difference(Point(0, 0).buffer(2.0))
    col_enclave = Point(0, 0).buffer(1.5)
    union = gpd.GeoDataFrame(
        {
            "ISO_TER1": ["NIC", None],
            "ISO_SOV1": ["NIC", "COL"],
            "ISO_TER2": [None, None],
            "ISO_SOV2": [None, None],
            "ISO_TER3": [None, None],
            "ISO_SOV3": [None, None],
            "geometry": [nic_with_hole, col_enclave],
        },
        crs="EPSG:4326",
    )

    monkeypatch.setattr(
        eez_module, "load_marine_regions", lambda params, bucket: union.copy(), raising=True
    )
    monkeypatch.setattr(
        eez_module,
        "read_json_from_gcs",
        _mock_read_json_from_gcs(mock_related_countries_map),
    )
    monkeypatch.setattr(eez_module, "clean_geometries", _mock_clean_geometries, raising=True)
    monkeypatch.setattr(eez_module, "upload_gdf", upload_gdf_mock, raising=True)

    eez_module.process_eez_land_union(
        gadm_eez_union_file_name="GADM_eez_union.geojson", tolerance=None, bucket="b", verbose=False
    )

    df = calls[0]["df"]
    nic_geom = df.loc[df["location"] == "NIC", "geometry"].iloc[0]
    # The COL enclave (centre) must remain OUTSIDE NIC's geometry - holes are kept.
    assert not nic_geom.contains(Point(0, 0))
