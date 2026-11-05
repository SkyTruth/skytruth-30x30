import geopandas as gpd
import pytest
from shapely.geometry import box

import src.methods.static_processes.near_shore_iho as near_shore_iho


class _FakeCatalogRef:
    cache_path = "unused.fgb"


class _FakeCatalog:
    @staticmethod
    def load():
        return _FakeCatalog()

    def fetch(self, *args, **kwargs):
        return _FakeCatalogRef()


@pytest.fixture
def near_shore_mocks(monkeypatch):
    """Stub out the shared-datasets fetch and the minutes-long buffering pass."""
    near_shore = gpd.GeoDataFrame(
        {"MRGID": [1, 2], "geometry": [box(0, 0, 1, 1), box(5, 5, 6, 6)]}, crs="EPSG:4326"
    )
    buffered_iho = gpd.GeoDataFrame(
        {"location": ["1", "2"], "geometry": [box(0, 0, 1, 1), box(5, 5, 6, 6)]}, crs="EPSG:4326"
    )
    gadm_eez_union = gpd.GeoDataFrame(
        {"location": ["AAA", "BBB"], "geometry": [box(0, 0, 2, 2), box(8, 8, 9, 9)]},
        crs="EPSG:4326",
    )
    high_seas = gpd.GeoDataFrame(
        {"location": ["ABNJ"], "geometry": [box(20, 20, 22, 22)]}, crs="EPSG:4326"
    )

    reads = []
    uploads = []

    def mock_read_json_df(bucket, filename, verbose=True):
        reads.append(filename)
        return gadm_eez_union.copy()

    def mock_upload_gdf(bucket, df, destination_blob, **_):
        uploads.append({"df": df.copy(), "destination_blob": destination_blob})

    monkeypatch.setattr(near_shore_iho, "Catalog", _FakeCatalog, raising=True)
    monkeypatch.setattr(near_shore_iho.gpd, "read_file", lambda *a, **k: near_shore.copy())
    monkeypatch.setattr(
        near_shore_iho, "process_buffered_iho", lambda *a, **k: near_shore.copy(), raising=True
    )
    monkeypatch.setattr(
        near_shore_iho, "load_iho_regions", lambda buffer=False: buffered_iho.copy(), raising=True
    )
    monkeypatch.setattr(
        near_shore_iho, "load_high_seas", lambda bucket=None: high_seas.copy(), raising=True
    )
    monkeypatch.setattr(near_shore_iho, "read_json_df", mock_read_json_df, raising=True)
    monkeypatch.setattr(near_shore_iho, "upload_gdf", mock_upload_gdf, raising=True)

    return reads, uploads


def test_process_near_shore_iho_writes_the_buffered_marine_locations(near_shore_mocks):
    reads, uploads = near_shore_mocks

    near_shore_iho.process_near_shore_iho(
        near_shore_iho_file_name="iho_near_shore.parquet",
        gadm_eez_union_file_name="GADM_eez_union.geojson",
        buffered_marine_locations_file_name="buffered_marine_locations.parquet",
        tolerance=0.7,
        bucket="test-bucket",
        verbose=False,
    )

    # The near-shore layer is saved first, because the combined layer reads it back
    # through load_iho_regions(buffer=True).
    assert [upload["destination_blob"] for upload in uploads] == [
        "iho_near_shore.parquet",
        "buffered_marine_locations_0.7.parquet",
    ]

    # The union is read at the same tolerance the combined layer is written at.
    assert reads == ["GADM_eez_union_0.7.geojson"]

    # All three parts are present: ISO3 codes from the land/EEZ union, MRGID strings
    # from the near-shore sea areas, and ABNJ from the high seas.
    locations = set(uploads[1]["df"]["location"])
    assert locations == {"AAA", "BBB", "1", "2", "ABNJ"}
