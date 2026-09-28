import geopandas as gpd
import pytest
from shapely.geometry import MultiPolygon, box

import src.methods.subtract_geometries as subtract
from src.core.commons import add_tolerance_suffix


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


@pytest.fixture
def mock_pa_gdf():
    return gpd.GeoDataFrame(
        {
            "ISO3": ["AUS"],
            "STATUS": ["Designated"],
            "DESIG_ENG": ["Marine Park"],
            "PA_DEF": [1],
            "geometry": [box(0, 0, 1, 1)],
        },
        crs="EPSG:4326",
    )


@pytest.mark.parametrize(
    ("pa_file", "expected_reader"),
    [("pas.parquet", "read_parquet_from_gcs"), ("pas.geojson", "read_json_df")],
)
def test_pa_file_is_read_by_its_format(
    monkeypatch, mock_location_gdf, mock_pa_gdf, pa_file, expected_reader
):
    """The marine job reads the PAs carrying their sea rows, which are saved as a
    parquet; the terrestrial job still reads a geojson."""
    pa_file_read = add_tolerance_suffix(pa_file, 0.001)
    frames = {"locations_0.001.geojson": mock_location_gdf, pa_file_read: mock_pa_gdf}
    reads = []

    def reader(name):
        def read(bucket_name, filename, verbose=True):
            reads.append((name, filename))
            return frames[filename].copy()

        return read

    monkeypatch.setattr(subtract, "read_json_df", reader("read_json_df"))
    monkeypatch.setattr(subtract, "read_parquet_from_gcs", reader("read_parquet_from_gcs"))
    monkeypatch.setattr(subtract, "upload_gdf", lambda **kwargs: None)

    subtract.generate_total_area_minus_pa(
        total_area_file="locations.geojson",
        pa_file=pa_file,
        out_file="out.parquet",
        archive_out_file="archive/out.parquet",
        tolerance=0.001,
        bucket="mock-bucket",
        verbose=False,
    )

    assert (expected_reader, pa_file_read) in reads


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
