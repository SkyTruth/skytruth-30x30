import json
import tempfile
import types
from unittest.mock import MagicMock

import geopandas as gpd
import pytest
from shapely.geometry import Polygon, mapping, shape

import src.methods.tileset_processes as tileset_processes
from src.methods.tileset_processes import create_and_update_eez_tileset


@pytest.fixture
def mock_eez_gdf():
    """
    Minimal EEZ-like frame
    """
    return gpd.GeoDataFrame(
        {
            "name": ["mock_eez"],
            "name_es": ["mock_eez_es"],
            "name_fr": ["mock_eez_fr"],
            "name_pt": ["mock_eez_pt"],
            "ISO_SOV1": ["USA"],
            "ISO_SOV2": ["MEX"],
            "ISO_SOV3": ["ABNJ"],
            "MRGID": [1234],
            "AREA_KM2": ["1000.4"],  # strings on purpose
            "geometry": [Polygon([(-10, -10), (-10, 10), (10, 10), (10, -10)])],
        },
        crs="EPSG:4326",
    )


@pytest.fixture
def mock_gdp_read_file_and_writers(monkeypatch, mock_eez_gdf):
    """
    Make geopandas.read_file return our EEZ frame, ensure .geometry.make_valid()
    exists, and replace .to_file on THIS frame with a pure-JSON writer so we
    don't require Fiona in test envs.
    """

    def _make_valid(self):
        return self

    # attach to this instance's GeoSeries only
    mock_eez_gdf.geometry.make_valid = types.MethodType(_make_valid, mock_eez_gdf.geometry)

    # 2) lightweight to_file for this instance: write real GeoJSON
    def _to_file(self, path, driver=None, **_kwargs):
        fc = {"type": "FeatureCollection", "features": []}
        for _, row in self.iterrows():
            props = row.drop(labels="geometry").to_dict()
            geom = mapping(row.geometry)
            fc["features"].append({"type": "Feature", "properties": props, "geometry": geom})
        with open(path, "w", encoding="utf-8") as f:
            json.dump(fc, f)

    mock_eez_gdf.to_file = types.MethodType(_to_file, mock_eez_gdf)

    # 3) return this instance from gdp.read_file
    monkeypatch.setattr(
        tileset_processes.gdp,
        "read_file",
        lambda *_a, **_k: mock_eez_gdf,
        raising=False,
    )


@pytest.fixture
def mock_collaborators(monkeypatch, mock_eez_gdf):
    mockReadJsonDf = MagicMock(name="mockReadJsonDf", return_value=mock_eez_gdf)
    mockGenerateMbtiles = MagicMock(name="mockGenerateMbtiles")
    mockUploadFileToGcs = MagicMock(name="mockUploadFileToGcs")
    mockUploadToMapbox = MagicMock(name="mockUploadToMapbox")
    mockLogger = MagicMock(name="mockLogger")

    monkeypatch.setattr(tileset_processes, "read_json_df", mockReadJsonDf, raising=True)
    monkeypatch.setattr(tileset_processes, "generate_mbtiles", mockGenerateMbtiles, raising=True)
    monkeypatch.setattr(tileset_processes, "upload_file_to_gcs", mockUploadFileToGcs, raising=True)
    monkeypatch.setattr(tileset_processes, "upload_to_mapbox", mockUploadToMapbox, raising=True)
    monkeypatch.setattr(tileset_processes, "logger", mockLogger, raising=True)

    return {
        "mockReadJsonDf": mockReadJsonDf,
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
        create_and_update_eez_tileset(verbose=True)
    assert "MAPBOX_USERNAME and MAPBOX_TOKEN environment variables must be set" in str(
        mockErr.value
    )

    # Ensure nothing else ran
    assert not mock_collaborators["mockGenerateMbtiles"].called
    assert not mock_collaborators["mockUploadToMapbox"].called
    assert not mock_collaborators["mockUploadFileToGcs"].called


def test_create_and_update_eez_tileset_happy_path(
    mock_collaborators,
    mock_mapbox_creds,
    mock_tempdir,
    mock_gdp_read_file_and_writers,
):
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
    assert props.get("ISO_SOV1") == "USA"
    assert props.get("ISO_SOV2") == "MEX"
    assert props.get("ISO_SOV3") == "ABNJ"

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


def test_error_is_logged_and_reraised(
    mock_collaborators, mock_mapbox_creds, mock_tempdir, mock_gdp_read_file_and_writers
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
