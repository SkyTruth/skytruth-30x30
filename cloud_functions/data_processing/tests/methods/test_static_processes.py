# tests/test_process_gadm_geoms.py
import gc

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import Point, box

from src.methods import static_processes
from src.methods.static_processes import (
    _pick_eez_parents,
    _proccess_eez_multiple_sovs,
    _process_eez_by_sov,
    process_gadm_geoms,
)


@pytest.fixture
def mock_gadm_layers():
    """
    Build tiny GADM-like GeoDataFrames for ADM_0 (countries) and ADM_1 (sub-countries)
    CRS matches typical WGS84. Geometries are simple polygons around points.
    """
    crs = "EPSG:4326"

    # Minimal "countries" (ADM_0) with a few entities (China, India, Pakistan, Cyprus)
    # plus a contested 'Z01' that suggests India via COUNTRY name.
    countries = gpd.GeoDataFrame(
        {
            "GID_0": ["CHN", "IND", "PAK", "CYP", "Z01", "ATA"],
            "COUNTRY": ["China", "India", "Pakistan", "Cyprus", "India", "Antarctica"],
            "geometry": [
                Point(100, 30).buffer(1.0),  # CHN
                Point(78, 22).buffer(1.0),  # IND
                Point(70, 30).buffer(1.0),  # PAK
                Point(33, 35).buffer(0.5),  # CYP
                Point(76, 34).buffer(0.3),  # Z01 (contested, should dissolve into India by name)
                Point(20, 20).buffer(0.5),  # ATA
            ],
        },
        crs=crs,
    )

    # Minimal "sub_countries" (ADM_1) with Hong Kong inside China
    sub_countries = gpd.GeoDataFrame(
        {
            "GID_1": ["CHN.HKG"],
            "GID_0": ["CHN"],  # typical pattern; we will overwrite to HKG inside the function
            "COUNTRY": ["Hong Kong"],
            "geometry": [Point(114.15, 22.29).buffer(0.05)],
        },
        crs=crs,
    )

    return countries, sub_countries


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
def mock_related_countries_map():
    """
    Mock sample of the related countires json mapping
    """
    return {
        "ABNJ": ["ABNJ", "HS", "ATA"],
        "CHN": ["CHN", "HKG"],
        "CYP": ["CYP", "ZNC"],
        "HKG": ["HKG"],
        "USA*": ["PRI"],
        "FRA*": ["FRA", "MYT"],
        "COM*": ["COM", "MYT"],
    }


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


@pytest.fixture
def uploads_recorder():
    """
    Collect every (bucket, df, destination_blob) call to upload_gdf.
    """
    calls = []

    def _upload_gdf(bucket, df, destination_blob):
        # Serialize to GeoJSON for a light shape/column sanity check (emulates real upload payload)
        # We won't use GCS client here; just record.
        assert isinstance(df, gpd.GeoDataFrame)
        payload = df.to_json()  # not strictly necessary, but proves serializability
        calls.append(
            {
                "bucket": bucket,
                "df": df,
                "destination_blob": destination_blob,
                "payload_len": len(payload),
            }
        )

    return calls, _upload_gdf


def _mock_clean_geometries(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Mock clean geometries processor
    """
    return gpd.GeoDataFrame(gdf.copy(), crs=gdf.crs)


def _mock_read_zipped_gpkg_from_gcs_success(countries, sub_countries):
    def _reader(bucket, zip_name, layers):
        assert layers == ["ADM_0", "ADM_1"]
        # Return in the same order requested
        return countries.copy(), sub_countries.copy()

    return _reader


def _mock_load_marine_regions(eez_gdf, hs_gdf):
    """Return a loader that returns EEZ for EEZ_PARAMS and HS for HIGH_SEAS_PARAMS."""

    def _loader(params, bucket):
        if params is static_processes.EEZ_PARAMS:
            return eez_gdf.copy()
        if params is static_processes.HIGH_SEAS_PARAMS:
            return hs_gdf.copy()
        raise ValueError("Unexpected params passed to load_marine_regions")

    return _loader


def _mock_read_dataframe(translations_df):
    def _reader(bucket, blob_name):
        return translations_df.copy()

    return _reader


def _mock_read_json_from_gcs(json):
    def _reader(bucket, blob_name, verbose=True):
        return json

    return _reader


def _run_process_gadm(
    monkeypatch, mock_gadm_layers, mock_related_countries_map, uploads_recorder, tolerances
):
    countries, sub_countries = mock_gadm_layers
    calls, upload_gdf_mock = uploads_recorder

    monkeypatch.setattr(
        static_processes,
        "read_zipped_gpkg_from_gcs",
        _mock_read_zipped_gpkg_from_gcs_success(countries, sub_countries),
    )
    monkeypatch.setattr(
        static_processes,
        "read_json_from_gcs",
        _mock_read_json_from_gcs(mock_related_countries_map),
    )
    monkeypatch.setattr(static_processes, "clean_geometries", _mock_clean_geometries)
    monkeypatch.setattr(static_processes, "upload_gdf", upload_gdf_mock)

    # Execute
    process_gadm_geoms(
        gadm_file_name="gadm.geojson",
        gadm_zipfile_name="gadm.zip",
        bucket="test-bucket",
        related_countries_file_name="related.json",
        tolerances=tolerances,
        verbose=True,
    )

    return calls


def _assert_output_df_shape_and_columns(df: gpd.GeoDataFrame):
    # structure expectations
    assert isinstance(df, gpd.GeoDataFrame)
    assert set(df.columns) == {"location", "geometry"}
    assert df.crs is not None  # CRS preserved (from input)


# -------------------------------
# Tests for process_gadm
# -------------------------------


def test_process_gadm_geoms_happy_path(
    monkeypatch, mock_gadm_layers, mock_related_countries_map, uploads_recorder
):
    tolerances = [None, 0.25]

    calls = _run_process_gadm(
        monkeypatch, mock_gadm_layers, mock_related_countries_map, uploads_recorder, tolerances
    )

    # One upload per tolerance value
    assert len(calls) == len(tolerances)

    # Filenames include the suffix for each tolerance (None and numeric)
    expected_names = {"gadm_None.geojson", "gadm_0.25.geojson"}
    assert set(call["destination_blob"] for call in calls) == expected_names

    # Validate data structure and key content for each uploaded GeoDataFrame
    for call in calls:
        df = call["df"]
        _assert_output_df_shape_and_columns(df)

        # ABNJ row exists with None geometry
        abnj_rows = df[df["location"] == "ABNJ"]
        assert len(abnj_rows) == 1
        assert abnj_rows.iloc[0]["geometry"].is_empty is False

        assert "HKG" in set(df["location"])
        assert "CHN" in set(df["location"])

        # Northern Cyprus rollup test: we provided relation ZNC -> CYP,
        assert "ZNC" not in set(df["location"])

        # Countries dissolved by ISO code after mapping; there should be no duplicate locations
        assert df["location"].is_unique


def test_process_gadm_geoms_upload_content_changes_with_tolerance(
    monkeypatch, mock_gadm_layers, mock_related_countries_map, uploads_recorder
):
    """
    Check that simplifying (non-None tolerance) changes serialized size for at least one upload.
    We don't assert a specific geometry size—just that something differs vs. None.
    """
    calls = _run_process_gadm(
        monkeypatch, mock_gadm_layers, mock_related_countries_map, uploads_recorder, [None, 0.5]
    )

    # Ensure we indeed produced two different payload sizes or at least different byte strings.
    sizes = [c["payload_len"] for c in calls]

    assert len(sizes) == 2
    assert all(s > 0 for s in sizes)
    assert sizes[1] < sizes[0]


def test_process_gadm_geoms_raises_on_reader_failure(
    monkeypatch, uploads_recorder, mock_related_countries_map
):
    """
    If the GPKG reader fails, the function should bubble the exception and not attempt uploads.
    """
    calls, upload_gdf_mock = uploads_recorder

    def failing_reader(bucket, zip_name, layers):
        raise RuntimeError("failed to read gpkg")

    monkeypatch.setattr(static_processes, "read_zipped_gpkg_from_gcs", failing_reader)
    monkeypatch.setattr(
        static_processes, "read_json_from_gcs", _mock_read_json_from_gcs(mock_related_countries_map)
    )
    monkeypatch.setattr(static_processes, "clean_geometries", _mock_clean_geometries)
    monkeypatch.setattr(static_processes, "upload_gdf", upload_gdf_mock)
    monkeypatch.setattr(static_processes, "pd", pd)
    monkeypatch.setattr(static_processes, "gpd", gpd)
    monkeypatch.setattr(static_processes, "gc", gc)

    with pytest.raises(RuntimeError, match="failed to read gpkg"):
        process_gadm_geoms(
            gadm_file_name="gadm.geojson",
            gadm_zipfile_name="gadm.zip",
            bucket="test-bucket",
            related_countries_file_name="related.json",
            tolerances=[None],
            verbose=False,
        )

    # No uploads should occur
    assert calls == []


def test_process_gadm_geoms_bad_input_columns(
    monkeypatch, mock_related_countries_map, uploads_recorder, mock_gadm_layers
):
    """
    If ADM_0 is missing expected columns, we should see a KeyError (or similar)
    before any upload is attempted.
    """
    crs = "EPSG:4326"
    bad_countries = gpd.GeoDataFrame(
        {
            # Missing COUNTRY; will break when dropping/slicing or dissolving
            "GID_0": ["AAA"],
            "geometry": [Point(0, 0).buffer(1.0)],
        },
        crs=crs,
    )

    _, sub_countries = mock_gadm_layers
    calls, upload_gdf_mock = uploads_recorder

    monkeypatch.setattr(
        static_processes,
        "read_zipped_gpkg_from_gcs",
        _mock_read_zipped_gpkg_from_gcs_success(bad_countries, sub_countries),
    )
    monkeypatch.setattr(
        static_processes, "read_json_from_gcs", _mock_read_json_from_gcs(mock_related_countries_map)
    )
    monkeypatch.setattr(static_processes, "clean_geometries", _mock_clean_geometries)
    monkeypatch.setattr(static_processes, "upload_gdf", upload_gdf_mock)
    monkeypatch.setattr(static_processes, "pd", pd)
    monkeypatch.setattr(static_processes, "gpd", gpd)
    monkeypatch.setattr(static_processes, "gc", gc)

    with pytest.raises(KeyError):
        process_gadm_geoms(
            gadm_file_name="gadm.geojson",
            gadm_zipfile_name="gadm.zip",
            bucket="test-bucket",
            related_countries_file_name="related.json",
            tolerances=[None],
            verbose=False,
        )

    assert calls == []


# -------------------------------
# Tests for process_eezs
# -------------------------------


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
        static_processes, "load_marine_regions", _mock_load_marine_regions(eez, hs), raising=True
    )
    monkeypatch.setattr(
        static_processes,
        "read_dataframe",
        _mock_read_dataframe(mock_eez_translations),
        raising=True,
    )
    monkeypatch.setattr(
        static_processes,
        "read_json_from_gcs",
        _mock_read_json_from_gcs(mock_related_countries_map),
    )
    monkeypatch.setattr(static_processes, "clean_geometries", _mock_clean_geometries, raising=True)
    monkeypatch.setattr(static_processes, "upload_gdf", upload_gdf_mock, raising=True)
    monkeypatch.setattr(static_processes, "TOLERANCES", [0.1, 0.3], raising=True)
    monkeypatch.setattr(static_processes, "EEZ_FILE_NAME", "eez.geojson", raising=True)
    monkeypatch.setattr(
        static_processes, "EEZ_MULTIPLE_SOV_FILE_NAME", "eez_multi.geojson", raising=True
    )
    # Ensure gc exists
    monkeypatch.setitem(globals(), "gc", gc)

    resp = static_processes.process_eez_geoms(
        eez_file_name=static_processes.EEZ_FILE_NAME,
        eez_params=static_processes.EEZ_PARAMS,
        bucket="test-bucket",
        related_countries_file_name=static_processes.RELATED_COUNTRIES_FILE_NAME,
        tolerances=static_processes.TOLERANCES,
        verbose=False,
    )
    # Function returns None; uploads recorded via our mock
    assert resp is None

    # Expect one upload per tolerance for eez_by_sov + one final multi-sov upload
    assert len(calls) == len(static_processes.TOLERANCES) + 1

    # Check filenames for the eez_by_sov uploads
    by_sov_names = {f"eez_{t}.geojson" for t in static_processes.TOLERANCES}
    seen_by_sov = {c["destination_blob"] for c in calls[:-1]}
    assert seen_by_sov == by_sov_names

    # The last call is multi-sovereign
    last_call = calls[-1]
    assert last_call["destination_blob"] == f"eez_multi_{static_processes.TOLERANCES[-1]}.geojson"

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

    monkeypatch.setattr(static_processes, "load_marine_regions", failing_loader, raising=True)
    monkeypatch.setattr(
        static_processes,
        "read_dataframe",
        _mock_read_dataframe(mock_eez_translations),
        raising=True,
    )
    monkeypatch.setattr(
        static_processes,
        "read_json_from_gcs",
        _mock_read_json_from_gcs(mock_related_countries_map),
    )
    monkeypatch.setattr(static_processes, "clean_geometries", lambda g: g, raising=True)
    monkeypatch.setattr(static_processes, "upload_gdf", upload_gdf_mock, raising=True)
    monkeypatch.setattr(static_processes, "TOLERANCES", [None, 0.1], raising=True)
    monkeypatch.setattr(static_processes, "EEZ_FILE_NAME", "eez.geojson", raising=True)
    monkeypatch.setattr(
        static_processes, "EEZ_MULTIPLE_SOV_FILE_NAME", "eez_multi.geojson", raising=True
    )

    with pytest.raises(RuntimeError, match="load failed"):
        static_processes.process_eez_geoms(verbose=False)

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
        static_processes,
        "load_marine_regions",
        _mock_load_marine_regions(bad_eez, hs),
        raising=True,
    )
    monkeypatch.setattr(
        static_processes,
        "read_dataframe",
        _mock_read_dataframe(mock_eez_translations),
        raising=True,
    )
    monkeypatch.setattr(
        static_processes,
        "read_json_from_gcs",
        _mock_read_json_from_gcs(mock_related_countries_map),
    )
    monkeypatch.setattr(static_processes, "clean_geometries", lambda g: g, raising=True)
    monkeypatch.setattr(static_processes, "upload_gdf", upload_gdf_mock, raising=True)

    with pytest.raises(AttributeError):
        static_processes.process_eez_geoms(verbose=False)

    assert calls == []


# -------------------------------
# Tests for process_eez_land_union
# -------------------------------


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
        assert params is static_processes.EEZ_LAND_UNION_PARAMS
        return union.copy()

    monkeypatch.setattr(static_processes, "load_marine_regions", _loader, raising=True)
    monkeypatch.setattr(
        static_processes,
        "read_json_from_gcs",
        _mock_read_json_from_gcs(mock_related_countries_map),
    )
    monkeypatch.setattr(static_processes, "clean_geometries", _mock_clean_geometries, raising=True)
    monkeypatch.setattr(static_processes, "upload_gdf", upload_gdf_mock, raising=True)

    resp = static_processes.process_eez_land_union(
        eez_land_union_params=static_processes.EEZ_LAND_UNION_PARAMS,
        gadm_eez_union_file_name="GADM_eez_union.geojson",
        related_countries_file_name=static_processes.RELATED_COUNTRIES_FILE_NAME,
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
        static_processes, "load_marine_regions", lambda params, bucket: union.copy(), raising=True
    )
    monkeypatch.setattr(
        static_processes,
        "read_json_from_gcs",
        _mock_read_json_from_gcs(mock_related_countries_map),
    )
    monkeypatch.setattr(static_processes, "clean_geometries", _mock_clean_geometries, raising=True)
    monkeypatch.setattr(static_processes, "upload_gdf", upload_gdf_mock, raising=True)

    static_processes.process_eez_land_union(
        gadm_eez_union_file_name="GADM_eez_union.geojson", tolerance=None, bucket="b", verbose=False
    )

    df = calls[0]["df"]
    nic_geom = df.loc[df["location"] == "NIC", "geometry"].iloc[0]
    # The COL enclave (centre) must remain OUTSIDE NIC's geometry - holes are kept.
    assert not nic_geom.contains(Point(0, 0))


# ---------------------------------------------------------------------------
# Tests for download_marine_habitats
# ---------------------------------------------------------------------------

FAKE_HABITAT_PARAMS = {
    "coldwatercorals": {
        "url": "https://example.test/corals.zip",
        "file_name": "habitats/corals.zip",
        "archive_file_name": "archive/habitats/corals_v1.zip",
    },
    "saltmarshes": {
        "url": "https://example.test/saltmarshes.zip",
        "file_name": "habitats/saltmarshes.zip",
        "archive_file_name": "archive/habitats/saltmarshes_v1.zip",
    },
    "seagrasses": {
        "url": "https://example.test/seagrasses.zip",
        "file_name": "habitats/seagrasses.zip",
        "archive_file_name": "archive/habitats/seagrasses_v1.zip",
    },
}


@pytest.fixture
def download_recorder(monkeypatch):
    """Record download_and_duplicate_zipfile calls instead of downloading files."""
    calls = []

    def _record(url, bucket, blob_name, archive_blob_name, chunk_size=None, verbose=True):
        calls.append(
            {
                "url": url,
                "bucket": bucket,
                "blob_name": blob_name,
                "archive_blob_name": archive_blob_name,
                "chunk_size": chunk_size,
            }
        )

    monkeypatch.setattr(static_processes, "download_and_duplicate_zipfile", _record, raising=True)
    return calls


def download(habitats, recorder_bucket="test-bucket"):
    static_processes.download_marine_habitats(
        habitats=habitats,
        marine_habitat_params=FAKE_HABITAT_PARAMS,
        bucket=recorder_bucket,
        verbose=False,
    )


def test_none_downloads_every_habitat(download_recorder):
    """Passing no habitat downloads all of them."""
    download(None)

    assert [call["blob_name"] for call in download_recorder] == [
        "habitats/corals.zip",
        "habitats/saltmarshes.zip",
        "habitats/seagrasses.zip",
    ]


def test_a_single_name_downloads_only_that_habitat(download_recorder):
    """Passing one habitat downloads just that one."""
    download("saltmarshes")

    assert len(download_recorder) == 1
    call = download_recorder[0]
    assert call["url"] == "https://example.test/saltmarshes.zip"
    assert call["blob_name"] == "habitats/saltmarshes.zip"
    assert call["archive_blob_name"] == "archive/habitats/saltmarshes_v1.zip"
    assert call["bucket"] == "test-bucket"


def test_a_list_downloads_those_habitats_in_order(download_recorder):
    """Passing multiple habitats downloads them in order."""
    download(["seagrasses", "coldwatercorals"])

    assert [call["blob_name"] for call in download_recorder] == [
        "habitats/seagrasses.zip",
        "habitats/corals.zip",
    ]


@pytest.mark.parametrize(
    "habitats",
    [
        "nonexistent",
        ["nonexistent"],
        ["coldwatercorals", "nonexistent"],
        [None],
        [1],
        [None, "nonexistent", 1],
    ],
    ids=[
        "unknown_str",
        "unknown_in_list",
        "mixed_with_valid",
        "none_entry",
        "int_entry",
        "mixed_types",
    ],
)
def test_unknown_habitats_raise_before_downloading_anything(download_recorder, habitats):
    """ValueError is raised if any habitat is unknown, and nothing is downloaded."""
    with pytest.raises(ValueError, match="unknown marine habitat"):
        download(habitats)

    assert download_recorder == [], "nothing should be downloaded when the request is invalid"


# ---------------------------------------------------------------------------
# Tests for process_mangroves
# ---------------------------------------------------------------------------


@pytest.fixture
def mangrove_extent():
    """The mangrove extent as read from the .gpkg.gz, geometry column only.

    Global Mangrove Watch polygons never overlap each other.
    """
    return gpd.GeoDataFrame(
        geometry=[
            box(0.5, 0.5, 1.5, 1.5),  # wholly inside AAA
            box(1.8, 0.5, 2.2, 1.5),  # straddles the AAA/BBB boundary
            box(10.0, 10.0, 10.5, 10.5),  # only the IHO sea area holds this one
        ],
        crs="EPSG:4326",
    )


@pytest.fixture
def mangrove_regions():
    """The land/EEZ union and IHO sea areas process_mangroves dissolves by.

    AAA and BBB are adjacent; the IHO sea area sits away from both.
    """
    gadm_eez_union = gpd.GeoDataFrame(
        {"location": ["AAA", "BBB"], "geometry": [box(0, 0, 2, 2), box(2, 0, 4, 2)]},
        crs="EPSG:4326",
    )
    iho = gpd.GeoDataFrame({"MRGID": [999], "geometry": [box(9, 9, 11, 11)]}, crs="EPSG:4326")
    return gadm_eez_union, iho


@pytest.fixture
def mangrove_recorders(monkeypatch, mangrove_extent, mangrove_regions):
    """Wire process_mangroves up to in-memory inputs and record what it writes."""
    gadm_eez_union, iho = mangrove_regions
    uploads = []
    saved_json = []

    def _read_gpkg(bucket, blob_name, layer=None, columns=None, verbose=True):
        return mangrove_extent.copy()

    def _read_json_df(bucket, blob_name, verbose=True):
        return gadm_eez_union.copy()

    def _read_parquet(bucket, blob_name, verbose=True):
        return iho.copy()

    def _save_json_to_gcs(bucket, data, blob_name, project=None, verbose=True):
        saved_json.append({"bucket": bucket, "data": data, "blob_name": blob_name})

    def _upload_gdf(bucket, df, destination_blob, project_id=None, verbose=True, timeout=600):
        uploads.append({"bucket": bucket, "df": df, "destination_blob": destination_blob})

    monkeypatch.setattr(static_processes, "read_gzipped_gpkg_from_gcs", _read_gpkg, raising=True)
    monkeypatch.setattr(static_processes, "read_json_df", _read_json_df, raising=True)
    monkeypatch.setattr(static_processes, "read_parquet_from_gcs", _read_parquet, raising=True)
    monkeypatch.setattr(static_processes, "save_json_to_gcs", _save_json_to_gcs, raising=True)
    monkeypatch.setattr(static_processes, "upload_gdf", _upload_gdf, raising=True)

    return uploads, saved_json


def test_process_mangroves_dissolves_by_location(mangrove_recorders):
    """One row per location holding mangroves, IHO sea areas included."""
    uploads, _ = mangrove_recorders

    static_processes.process_mangroves(
        mangroves_file_name="habitats/mangroves.gpkg.gz",
        gadm_eez_union_file_name="GADM_eez_union.geojson",
        iho_file_name="static/iho.parquet",
        by_location_file_pattern="static/{habitat}_by_location.parquet",
        global_area_file_pattern="intermediates/global_{habitat}_area.json",
        bucket="test-bucket",
        project="test-project",
        verbose=False,
        n_jobs=1,
    )

    assert len(uploads) == 1
    out = uploads[0]
    assert out["destination_blob"] == "static/mangroves_by_location.parquet"

    df = out["df"]
    assert isinstance(df, gpd.GeoDataFrame)
    assert set(df["location"]) == {"AAA", "BBB", "999"}
    # The schema every habitat's by-location layer shares
    assert list(df.columns) == [
        "location",
        "n_habitat_polygons",
        "bbox",
        "area_km2",
        "geometry",
        "habitat",
    ]
    assert set(df["habitat"]) == {"mangroves"}
    assert len(df) == 3
