import geopandas as gpd
import pytest
from shapely.geometry import box

import src.methods.static_processes.marine_habitat_geoms as marine_habitat_geoms
import src.methods.static_processes.marine_habitat_sources as marine_habitat_sources


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
            box(20.5, 20.5, 21.0, 21.0),  # only the high seas hold this one
        ],
        crs="EPSG:4326",
    )


@pytest.fixture
def mangrove_regions():
    """The buffered marine locations process_marine_habitat_geoms dissolves by: the
    land/EEZ union, the near-shore IHO sea areas, and the high seas, in one layer.

    AAA and BBB are adjacent; the IHO sea area and the high seas sit away from both and
    from each other.
    """
    return gpd.GeoDataFrame(
        {
            "location": ["AAA", "BBB", "999", "ABNJ"],
            "geometry": [
                box(0, 0, 2, 2),
                box(2, 0, 4, 2),
                box(9, 9, 11, 11),
                box(20, 20, 22, 22),
            ],
        },
        crs="EPSG:4326",
    )


@pytest.fixture
def mangrove_recorders(monkeypatch, mangrove_extent, mangrove_regions):
    """Wire process_marine_habitat_geoms up to in-memory inputs and record what it writes."""
    uploads = []
    saved_json = []

    def _read_gpkg(bucket, blob_name, layer=None, columns=None, verbose=True):
        return mangrove_extent.copy()

    def _read_parquet(bucket, blob_name, verbose=True):
        return mangrove_regions.copy()

    def _save_json_to_gcs(bucket, data, blob_name, project=None, verbose=True):
        saved_json.append({"bucket": bucket, "data": data, "blob_name": blob_name})

    def _upload_gdf(bucket, df, destination_blob, project_id=None, verbose=True, timeout=600):
        uploads.append({"bucket": bucket, "df": df, "destination_blob": destination_blob})

    # The habitat source is read by _load_habitat_geometry, which lives in
    # marine_habitat_sources; everything else is read and written here.
    monkeypatch.setattr(
        marine_habitat_sources, "read_gzipped_gpkg_from_gcs", _read_gpkg, raising=True
    )
    monkeypatch.setattr(marine_habitat_geoms, "read_parquet_from_gcs", _read_parquet, raising=True)
    monkeypatch.setattr(marine_habitat_geoms, "save_json_to_gcs", _save_json_to_gcs, raising=True)
    monkeypatch.setattr(marine_habitat_geoms, "upload_gdf", _upload_gdf, raising=True)

    return uploads, saved_json


def test_process_marine_habitat_geoms_dissolves_mangroves_by_location(mangrove_recorders):
    """One row per location holding mangroves, IHO sea areas and the high seas included."""
    uploads, _ = mangrove_recorders

    marine_habitat_geoms.process_marine_habitat_geoms(
        habitats="mangroves",
        marine_locations_file_name="buffered_marine_locations.parquet",
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
    assert set(df["location"]) == {"AAA", "BBB", "999", "ABNJ"}
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
    assert len(df) == 4
