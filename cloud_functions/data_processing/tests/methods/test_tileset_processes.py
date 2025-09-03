import json
import tempfile
import types
from unittest.mock import MagicMock

import pytest
from shapely.geometry import mapping, shape

import src.methods.tileset_processes as tileset_processes
from src.methods.tileset_processes import (
    _check_map_box_credentials,
    create_and_update_eez_tileset,
    create_and_update_marine_regions_tileset,
)


@pytest.fixture
def mock_regions():
    """
    Mock Region mapping
    """
    return {"NA": ["USA", "MEX"]}


@pytest.fixture
def mock_to_file():
    def _to_file(self, path, driver=None, **_kwargs):
        fc = {"type": "FeatureCollection", "features": []}
        for _, row in self.iterrows():
            props = row.drop(labels="geometry").to_dict()
            geom = mapping(row.geometry)
            fc["features"].append({"type": "Feature", "properties": props, "geometry": geom})
        with open(path, "w", encoding="utf-8") as f:
            json.dump(fc, f)

    return _to_file


@pytest.fixture
def mock_collaborators(monkeypatch, mock_locs_translations_df, mock_regions):
    mockReadJsonDf = MagicMock(name="mockReadJsonDf")
    mockReadDataframe = MagicMock(name="mockReadDataframe", return_value=mock_locs_translations_df)
    mockReadJsonFromGCS = MagicMock(name="mockReadJsonFromGCS", return_value=mock_regions)
    mockGenerateMbtiles = MagicMock(name="mockGenerateMbtiles")
    mockUploadFileToGcs = MagicMock(name="mockUploadFileToGcs")
    mockUploadToMapbox = MagicMock(name="mockUploadToMapbox")
    mockLogger = MagicMock(name="mockLogger")

    monkeypatch.setattr(tileset_processes, "read_json_df", mockReadJsonDf, raising=True)
    monkeypatch.setattr(tileset_processes, "read_dataframe", mockReadDataframe, raising=True)
    monkeypatch.setattr(tileset_processes, "read_json_from_gcs", mockReadJsonFromGCS, raising=True)
    monkeypatch.setattr(tileset_processes, "generate_mbtiles", mockGenerateMbtiles, raising=True)
    monkeypatch.setattr(tileset_processes, "upload_file_to_gcs", mockUploadFileToGcs, raising=True)
    monkeypatch.setattr(tileset_processes, "upload_to_mapbox", mockUploadToMapbox, raising=True)
    monkeypatch.setattr(tileset_processes, "logger", mockLogger, raising=True)

    return {
        "mockReadJsonDf": mockReadJsonDf,
        "mockReadDataframe": mockReadDataframe,
        "mockReadJsonFromGCS": mockReadJsonFromGCS,
        "mockGenerateMbtiles": mockGenerateMbtiles,
        "mockUploadFileToGcs": mockUploadFileToGcs,
        "mockUploadToMapbox": mockUploadToMapbox,
        "mockLogger": mockLogger,
    }


@pytest.fixture
def mock_tempdir(monkeypatch, tmp_path):
    """
    Replace TemporaryDirectory with one backed by pytest's tmp_path so the
    directory persists after the function returns (no cleanup).
    """

    class mockTempDir:
        def __init__(self, base):
            self._base = base

        def __enter__(self):
            return str(self._base)

        def __exit__(self, exc_type, exc, tb):
            # Do NOT delete; leave artifacts for assertions.
            return False

    monkeypatch.setattr(
        tempfile,
        "TemporaryDirectory",
        lambda: mockTempDir(tmp_path),
        raising=True,
    )


@pytest.fixture
def mock_mapbox_creds(monkeypatch):
    """Ensure MAPBOX_USER and MAPBOX_TOKEN are populated."""
    monkeypatch.setattr(tileset_processes, "MAPBOX_USER", "mock_user", raising=True)
    monkeypatch.setattr(tileset_processes, "MAPBOX_TOKEN", "mock_token", raising=True)


def test_missing_mapbox_creds_raises_value_error(monkeypatch, mock_collaborators):
    monkeypatch.setattr(tileset_processes, "MAPBOX_USER", "", raising=True)
    monkeypatch.setattr(tileset_processes, "MAPBOX_TOKEN", None, raising=True)

    with pytest.raises(ValueError) as mockErr:
        _check_map_box_credentials()
    assert "MAPBOX_USERNAME and MAPBOX_TOKEN environment variables must be set" in str(
        mockErr.value
    )


def test_create_and_update_eez_tileset_happy_path(
    mock_collaborators, mock_mapbox_creds, mock_tempdir, mock_to_file, mock_eez_by_sov_gdf
):
    mock_eez_by_sov_gdf.to_file = types.MethodType(mock_to_file, mock_eez_by_sov_gdf)
    mock_collaborators["mockReadJsonDf"].return_value = mock_eez_by_sov_gdf
    create_and_update_eez_tileset(verbose=True)

    # Find the geojson path from what generate_mbtiles consumed
    mockGenerateMbtiles = mock_collaborators["mockGenerateMbtiles"]
    assert mockGenerateMbtiles.call_count == 1
    gen_kwargs = mockGenerateMbtiles.call_args.kwargs
    geojson_path = gen_kwargs["input_file"]
    tileset_mbtiles_path = gen_kwargs["output_file"]

    # Assert the written GeoJSON exists and has the expected outcome
    with open(geojson_path, encoding="utf-8") as f:
        mock_geojson = json.load(f)

    assert mock_geojson.get("type") == "FeatureCollection"
    assert "features" in mock_geojson and len(mock_geojson["features"]) == 1

    mock_feature = mock_geojson["features"][0]
    props = mock_feature["properties"]

    # AREA_KM2 dropped, MRGRID preserved (note: function drops MRGID, not MRGRID)
    assert "AREA_KM2" not in props
    assert "MRGID" not in props

    # Key attributes persisted
    assert props.get("name") == "mock_eez"
    assert props.get("name_es") == "mock_eez_es"
    assert props.get("name_fr") == "mock_eez_fr"
    assert props.get("name_pt") == "mock_eez_pt"
    assert props.get("ISO_TER1") == "USA"
    assert props.get("ISO_TER2") == "MEX"
    assert props.get("ISO_TER3") == "ABNJ"
    assert props.get("ISO_SOV1") == "USA*"
    assert props.get("ISO_SOV2") is None
    assert props.get("ISO_SOV3") is None

    # Geometry valid polygon
    geom = shape(mock_feature["geometry"])
    assert geom.geom_type == "Polygon"
    assert not geom.is_empty

    # The produced mbtiles path should flow to both uploads
    mockUploadFileToGcs = mock_collaborators["mockUploadFileToGcs"]
    assert mockUploadFileToGcs.call_count == 1
    assert mockUploadFileToGcs.call_args.kwargs["file_name"] == tileset_mbtiles_path

    mockUploadToMapbox = mock_collaborators["mockUploadToMapbox"]
    assert mockUploadToMapbox.call_count == 1

    mb = mockUploadToMapbox.call_args.kwargs
    assert mb["source"] == tileset_mbtiles_path
    assert mb["tileset_id"] == tileset_processes.EEZ_TILESET_ID
    assert mb["display_name"] == tileset_processes.EEZ_TILESET_NAME
    assert mb["username"] == "mock_user"
    assert mb["token"] == "mock_token"


def test_eez_error_is_logged_and_reraised(
    mock_collaborators,
    mock_mapbox_creds,
    mock_tempdir,
):
    mock_collaborators["mockGenerateMbtiles"].side_effect = RuntimeError("mock generation failure")

    with pytest.raises(RuntimeError) as mockErr:
        create_and_update_eez_tileset(verbose=False)
    assert "mock generation failure" in str(mockErr.value)

    # Ensure we logged the error with the expected message content
    mock_logger = mock_collaborators["mockLogger"]
    assert mock_logger.error.call_count == 1

    logged_arg = mock_logger.error.call_args.args[0]
    assert isinstance(logged_arg, dict)
    assert logged_arg.get("message") == "Error creating and updating EEZ tileset"
    assert "mock generation failure" in logged_arg.get("error", "")


def test_create_and_update_marine_regions_tileset_happy_path(
    mock_collaborators, mock_mapbox_creds, mock_tempdir, mock_to_file, mock_eez_by_loc_gdf
):
    mock_eez_by_loc_gdf.to_file = types.MethodType(mock_to_file, mock_eez_by_loc_gdf)
    mock_collaborators["mockReadJsonDf"].return_value = mock_eez_by_loc_gdf
    create_and_update_marine_regions_tileset(verbose=True)

    # Find the geojson path from what generate_mbtiles consumed
    mockGenerateMbtiles = mock_collaborators["mockGenerateMbtiles"]
    assert mockGenerateMbtiles.call_count == 1
    gen_kwargs = mockGenerateMbtiles.call_args.kwargs
    geojson_path = gen_kwargs["input_file"]
    tileset_mbtiles_path = gen_kwargs["output_file"]

    # Assert the written GeoJSON exists and has the expected outcome
    with open(geojson_path, encoding="utf-8") as f:
        mock_geojson = json.load(f)

    assert mock_geojson.get("type") == "FeatureCollection"
    assert "features" in mock_geojson and len(mock_geojson["features"]) == 1

    mock_feature = mock_geojson["features"][0]
    props = mock_feature["properties"]

    # AREA_KM2 dropped, MRGRID preserved (note: function drops MRGID, not MRGRID)
    assert "AREA_KM2" not in props
    assert "MRGID" not in props
    assert "location" not in props

    # Key attributes persisted
    assert props.get("name") == "North America"
    assert props.get("name_es") == "Norteamérica"
    assert props.get("name_fr") == "Amérique du Nord"
    assert props.get("name_pt") == "América do Norte"
    assert props.get("region_id") == "NA"

    # Geometry valid polygon
    geom = shape(mock_feature["geometry"])
    assert geom.geom_type == "MultiPolygon"  # Multi because of dissolve
    assert not geom.is_empty

    # The produced mbtiles path should flow to both uploads
    mockUploadFileToGcs = mock_collaborators["mockUploadFileToGcs"]
    assert mockUploadFileToGcs.call_count == 1
    assert mockUploadFileToGcs.call_args.kwargs["file_name"] == tileset_mbtiles_path

    mockUploadToMapbox = mock_collaborators["mockUploadToMapbox"]
    assert mockUploadToMapbox.call_count == 1

    mb = mockUploadToMapbox.call_args.kwargs
    assert mb["source"] == tileset_mbtiles_path
    assert mb["tileset_id"] == tileset_processes.MARINE_REGIONS_TILESET_ID
    assert mb["display_name"] == tileset_processes.MARINE_REGIONS_TILESET_NAME
    assert mb["username"] == "mock_user"
    assert mb["token"] == "mock_token"


def test_marine_regions_error_is_logged_and_reraised(
    mock_collaborators, mock_mapbox_creds, mock_tempdir, mock_to_file, mock_eez_by_loc_gdf
):
    mock_eez_by_loc_gdf.to_file = types.MethodType(mock_to_file, mock_eez_by_loc_gdf)
    mock_collaborators["mockReadJsonDf"].return_value = mock_eez_by_loc_gdf

    mock_collaborators["mockGenerateMbtiles"].side_effect = RuntimeError("mock generation failure")

    with pytest.raises(RuntimeError) as mockErr:
        create_and_update_eez_tileset(verbose=False)
    assert "mock generation failure" in str(mockErr.value)

    # Ensure we logged the error with the expected message content
    mock_logger = mock_collaborators["mockLogger"]
    assert mock_logger.error.call_count == 1

    logged_arg = mock_logger.error.call_args.args[0]
    assert isinstance(logged_arg, dict)
    assert logged_arg.get("message") == "Error creating and updating EEZ tileset"
    assert "mock generation failure" in logged_arg.get("error", "")
