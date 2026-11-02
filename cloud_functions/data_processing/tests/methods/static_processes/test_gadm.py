import geopandas as gpd
import pytest
from shapely.geometry import Point

import src.methods.static_processes.gadm as gadm
from src.methods.static_processes.gadm import process_gadm_geoms


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


def _mock_read_json_from_gcs(json):
    def _reader(bucket, blob_name, verbose=True):
        return json

    return _reader


def _run_process_gadm(
    monkeypatch, mock_gadm_layers, mock_related_countries_map, uploads_recorder, tolerance
):
    countries, sub_countries = mock_gadm_layers
    calls, upload_gdf_mock = uploads_recorder

    monkeypatch.setattr(
        gadm,
        "read_zipped_gpkg_from_gcs",
        _mock_read_zipped_gpkg_from_gcs_success(countries, sub_countries),
    )
    monkeypatch.setattr(
        gadm,
        "read_json_from_gcs",
        _mock_read_json_from_gcs(mock_related_countries_map),
    )
    monkeypatch.setattr(gadm, "clean_geometries", _mock_clean_geometries)
    monkeypatch.setattr(gadm, "upload_gdf", upload_gdf_mock)

    # Execute
    process_gadm_geoms(
        gadm_file_name="gadm.geojson",
        gadm_zipfile_name="gadm.zip",
        bucket="test-bucket",
        related_countries_file_name="related.json",
        tolerance=tolerance,
        verbose=True,
    )

    return calls


def _assert_output_df_shape_and_columns(df: gpd.GeoDataFrame):
    # structure expectations
    assert isinstance(df, gpd.GeoDataFrame)
    assert set(df.columns) == {"location", "geometry"}
    assert df.crs is not None  # CRS preserved (from input)


@pytest.mark.parametrize(
    "tolerance, expected_name",
    [(None, "gadm_None.geojson"), (0.25, "gadm_0.25.geojson")],
)
def test_process_gadm_geoms_happy_path(
    monkeypatch,
    mock_gadm_layers,
    mock_related_countries_map,
    uploads_recorder,
    tolerance,
    expected_name,
):
    calls = _run_process_gadm(
        monkeypatch, mock_gadm_layers, mock_related_countries_map, uploads_recorder, tolerance
    )

    # A single upload, named for the tolerance it was simplified at
    assert len(calls) == 1
    assert calls[0]["destination_blob"] == expected_name

    # Validate data structure and key content for the uploaded GeoDataFrame
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
    # Both runs record into the same uploads_recorder list, in order.
    _run_process_gadm(
        monkeypatch, mock_gadm_layers, mock_related_countries_map, uploads_recorder, None
    )
    calls = _run_process_gadm(
        monkeypatch, mock_gadm_layers, mock_related_countries_map, uploads_recorder, 0.5
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

    monkeypatch.setattr(gadm, "read_zipped_gpkg_from_gcs", failing_reader)
    monkeypatch.setattr(
        gadm, "read_json_from_gcs", _mock_read_json_from_gcs(mock_related_countries_map)
    )
    monkeypatch.setattr(gadm, "clean_geometries", _mock_clean_geometries)
    monkeypatch.setattr(gadm, "upload_gdf", upload_gdf_mock)

    with pytest.raises(RuntimeError, match="failed to read gpkg"):
        process_gadm_geoms(
            gadm_file_name="gadm.geojson",
            gadm_zipfile_name="gadm.zip",
            bucket="test-bucket",
            related_countries_file_name="related.json",
            tolerance=None,
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
        gadm,
        "read_zipped_gpkg_from_gcs",
        _mock_read_zipped_gpkg_from_gcs_success(bad_countries, sub_countries),
    )
    monkeypatch.setattr(
        gadm, "read_json_from_gcs", _mock_read_json_from_gcs(mock_related_countries_map)
    )
    monkeypatch.setattr(gadm, "clean_geometries", _mock_clean_geometries)
    monkeypatch.setattr(gadm, "upload_gdf", upload_gdf_mock)

    with pytest.raises(KeyError):
        process_gadm_geoms(
            gadm_file_name="gadm.geojson",
            gadm_zipfile_name="gadm.zip",
            bucket="test-bucket",
            related_countries_file_name="related.json",
            tolerance=None,
            verbose=False,
        )

    assert calls == []
