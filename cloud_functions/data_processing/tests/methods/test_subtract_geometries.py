import geopandas as gpd
import pytest
from shapely.geometry import MultiPolygon, box

import src.methods.subtract_geometries as subtract


@pytest.fixture
def mock_mpa_gdf():
    """One full-protection zone spanning two countries, one non-qualifying zone."""
    return gpd.GeoDataFrame(
        {
            "country": ["AUS,NZL", "AUS"],
            "protection_mpaguide_level": ["full", "less"],
            "geometry": [
                MultiPolygon([box(0, 0, 1, 1), box(10, 0, 11, 1)]),
                box(1, 1, 2, 2),
            ],
        },
        crs="EPSG:4326",
    )


@pytest.fixture
def mock_location_gdf():
    return gpd.GeoDataFrame(
        {
            "location": ["AUS", "NZL"],
            "geometry": [box(0, 0, 2, 2), box(10, 0, 12, 2)],
        },
        crs="EPSG:4326",
    )


def test_multi_country_zone_subtracted_from_all_its_locations(
    monkeypatch, mock_mpa_gdf, mock_location_gdf
):
    reads = {"raw/mpa.geojson": mock_mpa_gdf, "locations_0.001.geojson": mock_location_gdf}
    monkeypatch.setattr(
        subtract, "read_json_df", lambda bucket_name, filename, verbose: reads[filename].copy()
    )

    uploads = {}

    def mock_upload_gdf(bucket_name, gdf, destination_blob_name, **_):
        uploads[destination_blob_name] = gdf.copy()

    monkeypatch.setattr(subtract, "upload_gdf", mock_upload_gdf)

    subtract.generate_location_minus_fhp_mpa(
        mpa_file="raw/mpa.geojson",
        loc_file="locations.geojson",
        out_file="out.geojson",
        archive_out_file="archive/out.geojson",
        tolerance=0.001,
        bucket="mock-bucket",
        verbose=False,
    )

    result = uploads["out.geojson"].set_index("location")

    # The "AUS,NZL" full-protection zone must be removed from BOTH locations;
    # the "less" protected zone must not be subtracted at all.
    assert result.loc["AUS"].geometry.area == pytest.approx(3.0)
    assert result.loc["NZL"].geometry.area == pytest.approx(3.0)
