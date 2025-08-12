# tests/test_process_gadm_geoms.py
import gc

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import Point

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
            "ISO_TER1": ["AAA", None],
            "ISO_SOV1": ["AAA", "BBB"],
            "ISO_TER2": [None, None],
            "ISO_SOV2": ["CCC", None],
            "ISO_TER3": [None, None],
            "ISO_SOV3": [None, None],
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


def test_pick_eez_parents_basic():
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
    parents = _pick_eez_parents(row)
    # MYT should be chosen (deduped), no None, order not guaranteed
    assert set(parents) == {"MYT"}


def test_process_eez_by_sov_happy_path(mock_eez, mock_high_seas):
    # Precompute parents like process_eez_geoms would
    eez = mock_eez.copy()
    eez["parents"] = eez.apply(_pick_eez_parents, axis=1)
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
    # Parents (AAA, CCC) + ABNJ should exist
    assert {"AAA", "CCC", "ABNJ"}.issubset(set(out["location"]))

    np.testing.assert_array_equal(out["location"].unique(), out["location"])

    shared_area = out[out["location"] == "AAA"]
    assert shared_area.loc[0, "AREA_KM2"] == 10  # sum of shared area locations
    assert shared_area.loc[0, "has_shared_marine_area"]


def test_proccess_eez_multiple_sovs_happy_path(mock_eez, mock_high_seas, mock_eez_translations):
    eez = mock_eez.copy()
    eez["parents"] = eez.apply(_pick_eez_parents, axis=1)

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
        "geometry",
        "AREA_KM2",
        "POL_TYPE",
        "MRGID",
        "name",
        "name_es",
        "name_fr",
        "name_pt",
    }
    assert expect_cols.issubset(out.columns)
    # First EEZ should have two parents -> ISO_SOV1 & ISO_SOV2 not None
    row = out[out["MRGID"] == 101].iloc[0]
    assert row["ISO_SOV1"] is not None
    assert row["ISO_SOV2"] is not None


def test_process_eez_geoms_happy_path(
    monkeypatch, uploads_recorder, mock_eez, mock_high_seas, mock_eez_translations
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
    monkeypatch.setattr(static_processes, "clean_geometries", _mock_clean_geometries, raising=True)
    monkeypatch.setattr(static_processes, "upload_gdf", upload_gdf_mock, raising=True)
    monkeypatch.setattr(static_processes, "TOLERANCES", [None, 0.1, 0.3], raising=True)
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
    monkeypatch, uploads_recorder, mock_eez, mock_high_seas, mock_eez_translations
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


def test_process_eez_geoms_missing_columns(monkeypatch, uploads_recorder, mock_eez_translations):
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
    monkeypatch.setattr(static_processes, "clean_geometries", lambda g: g, raising=True)
    monkeypatch.setattr(static_processes, "upload_gdf", upload_gdf_mock, raising=True)

    with pytest.raises(AttributeError):
        static_processes.process_eez_geoms(verbose=False)

    assert calls == []
