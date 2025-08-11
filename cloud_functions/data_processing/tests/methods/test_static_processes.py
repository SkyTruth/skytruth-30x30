# tests/test_process_gadm_geoms.py
import gc

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

from src.methods import static_processes
from src.methods.static_processes import process_gadm_geoms


@pytest.fixture
def sample_layers():
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
def related_countries_map():
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


def _mock_read_json_from_gcs(related_map):
    def _reader(bucket, blob_name, verbose=True):
        return related_map

    return _reader


def _run_process(monkeypatch, sample_layers, related_countries_map, uploads_recorder, tolerances):
    countries, sub_countries = sample_layers
    calls, upload_gdf_mock = uploads_recorder

    # Patch dependencies referenced inside the function under test
    # monkeypatch.setenv("GEOPANDAS_IGNORE_SHAPELY2_WARNINGS", "1")  # noisy in CI sometimes

    # import builtins
    # Ensure pandas/geopandas available inside module if it resolves them at global scope
    # (Usually not needed if tests run in same interpreter, but harmless)
    # monkeypatch.setattr(static_processes, "pd", pd)
    # monkeypatch.setitem(globals(), "gpd", gpd)
    # monkeypatch.setitem(globals(), "gc", gc)

    monkeypatch.setattr(
        static_processes,
        "read_zipped_gpkg_from_gcs",
        _mock_read_zipped_gpkg_from_gcs_success(countries, sub_countries),
    )
    monkeypatch.setattr(
        static_processes,
        "read_json_from_gcs",
        _mock_read_json_from_gcs(related_countries_map),
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


def test_process_gadm_geoms_happy_path(
    monkeypatch, sample_layers, related_countries_map, uploads_recorder
):
    tolerances = [None, 0.25]

    calls = _run_process(
        monkeypatch, sample_layers, related_countries_map, uploads_recorder, tolerances
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
    monkeypatch, sample_layers, related_countries_map, uploads_recorder
):
    """
    Check that simplifying (non-None tolerance) changes serialized size for at least one upload.
    We don't assert a specific geometry size—just that something differs vs. None.
    """
    calls = _run_process(
        monkeypatch, sample_layers, related_countries_map, uploads_recorder, [None, 0.5]
    )

    # Ensure we indeed produced two different payload sizes or at least different byte strings.
    sizes = [c["payload_len"] for c in calls]

    assert len(sizes) == 2
    assert all(s > 0 for s in sizes)
    assert sizes[1] < sizes[0]


def test_process_gadm_geoms_raises_on_reader_failure(
    monkeypatch, uploads_recorder, related_countries_map
):
    """
    If the GPKG reader fails, the function should bubble the exception and not attempt uploads.
    """
    calls, upload_gdf_mock = uploads_recorder

    def failing_reader(bucket, zip_name, layers):
        raise RuntimeError("failed to read gpkg")

    monkeypatch.setattr(static_processes, "read_zipped_gpkg_from_gcs", failing_reader)
    monkeypatch.setattr(
        static_processes, "read_json_from_gcs", _mock_read_json_from_gcs(related_countries_map)
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
    monkeypatch, related_countries_map, uploads_recorder, sample_layers
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
    # sub_countries = gpd.GeoDataFrame(
    #     {
    #         "GID_1": ["CHN.HKG"],
    #         "GID_0": ["CHN"],
    #         "COUNTRY": ["Hong Kong"],
    #         "geometry": [Point(114.15, 22.29).buffer(0.05)],
    #     },
    #     crs=crs,
    # )
    _, sub_countries = sample_layers
    calls, upload_gdf_mock = uploads_recorder

    # def reader(bucket, zip_name, layers):
    #     return bad_countries.copy(), sub_countries.copy()

    monkeypatch.setattr(
        static_processes,
        "read_zipped_gpkg_from_gcs",
        _mock_read_zipped_gpkg_from_gcs_success(bad_countries, sub_countries),
    )
    monkeypatch.setattr(
        static_processes, "read_json_from_gcs", _mock_read_json_from_gcs(related_countries_map)
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
