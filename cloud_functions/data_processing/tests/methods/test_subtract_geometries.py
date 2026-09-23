import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import MultiPolygon, box

import src.methods.subtract_geometries as subtract
from src.core.commons import add_tolerance_suffix
from src.core.params import ARCHIVE_CONSERVATION_BUILDER_HABITAT_DATA_PATTERN


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


@pytest.fixture
def mock_habitat_gdf():
    """One patch wholly inside AUS, one straddling its eastern edge, none near NZL."""
    return gpd.GeoDataFrame(
        {"geometry": [box(0, 0, 1, 2), box(1.5, 0, 3, 1)]},
        crs="EPSG:4326",
    )


@pytest.fixture
def mock_terrestrial_pa_gdf():
    """A terrestrial PA well away from the habitat, so it changes no area on its own."""
    return gpd.GeoDataFrame(
        {
            "ISO3": ["AUS"],
            "STATUS": ["Designated"],
            "DESIG_ENG": ["National Park"],
            "PA_DEF": [1],
            "geometry": [box(50, 50, 51, 51)],
        },
        crs="EPSG:4326",
    )


@pytest.fixture
def mock_pa_with_seas_gdf(mock_pa_gdf, mock_terrestrial_pa_gdf):
    """Both estates in one frame, as a buffered generate_iho_pa_intersections run saves
    them: every PA labelled with the environment it was joined from."""
    return pd.concat(
        [
            mock_pa_gdf.assign(environment="marine"),
            mock_terrestrial_pa_gdf.assign(environment="terrestrial"),
        ],
        ignore_index=True,
    )


@pytest.fixture
def habitat_job_mocks(monkeypatch, mock_location_gdf, mock_pa_with_seas_gdf, mock_habitat_gdf):
    """Serve the three reads the habitat job makes and capture what it uploads.

    The job takes a habitat key and reads its own by-location geometries, so the
    habitat frame arrives through read_parquet_from_gcs rather than being passed in.
    """
    parquet_reads = {
        "static/mangroves_by_location.parquet": mock_habitat_gdf,
        "locations_0.001.parquet": mock_location_gdf,
        "pas_0.001.parquet": mock_pa_with_seas_gdf,
    }
    uploads = {}

    monkeypatch.setattr(
        subtract,
        "read_parquet_from_gcs",
        lambda bucket_name, filename, verbose=True: parquet_reads[filename].copy(),
    )
    monkeypatch.setattr(
        subtract,
        "upload_gdf",
        lambda bucket_name, gdf, destination_blob_name, **_: uploads.__setitem__(
            destination_blob_name, gdf.copy()
        ),
    )

    return uploads


def _run_habitat_job():
    subtract.generate_habitat_minus_pa(
        habitat="mangroves",
        total_area_file="locations.parquet",
        pa_file="pas.parquet",
        tolerance=0.001,
        bucket="mock-bucket",
        verbose=False,
    )


def test_habitat_is_clipped_to_the_country_and_has_pas_subtracted(habitat_job_mocks):
    _run_habitat_job()

    result = habitat_job_mocks["conservation_builder/mangroves_minus_pa.parquet"].set_index(
        "location"
    )

    # box(0,0,1,2) contributes 2.0; box(1.5,0,3,1) is clipped at the AUS edge x=2 down
    # to 0.5; the AUS PA box(0,0,1,1) then removes 1.0 of the total.
    assert result.loc["AUS"].geometry.area == pytest.approx(1.5)


def test_output_blobs_are_named_from_the_habitat_key(habitat_job_mocks):
    """The job derives both blob names from the habitat rather than taking them as
    arguments, so a typo'd key silently writes to the wrong place."""
    _run_habitat_job()

    assert set(habitat_job_mocks) == {
        "conservation_builder/mangroves_minus_pa.parquet",
        ARCHIVE_CONSERVATION_BUILDER_HABITAT_DATA_PATTERN.format(habitat="mangroves"),
    }


def test_countries_holding_no_habitat_are_dropped(habitat_job_mocks):
    _run_habitat_job()

    # NZL's box(10,0,12,2) holds none of the habitat, so it gets no row at all
    # rather than a row with empty geometry.
    assert list(
        habitat_job_mocks["conservation_builder/mangroves_minus_pa.parquet"]["location"]
    ) == ["AUS"]


def test_each_input_is_read_once_through_the_parquet_reader(
    monkeypatch, mock_location_gdf, mock_pa_with_seas_gdf, mock_habitat_gdf
):
    """Both estates now arrive in the one file a buffered run writes, so the habitat,
    the locations and the protected areas are all parquets and none is read twice."""
    frames = {
        "static/mangroves_by_location.parquet": mock_habitat_gdf,
        "locations_0.001.parquet": mock_location_gdf,
        "pas_0.001.parquet": mock_pa_with_seas_gdf,
    }
    reads = []

    def reader(name):
        def read(bucket_name, filename, verbose=True):
            reads.append((name, filename))
            return frames[filename].copy()

        return read

    monkeypatch.setattr(subtract, "read_json_df", reader("read_json_df"))
    monkeypatch.setattr(subtract, "read_parquet_from_gcs", reader("read_parquet_from_gcs"))
    monkeypatch.setattr(subtract, "upload_gdf", lambda **kwargs: None)

    _run_habitat_job()

    assert reads == [
        ("read_parquet_from_gcs", "static/mangroves_by_location.parquet"),
        ("read_parquet_from_gcs", "locations_0.001.parquet"),
        ("read_parquet_from_gcs", "pas_0.001.parquet"),
    ]


def test_both_pa_estates_are_subtracted(
    monkeypatch, mock_location_gdf, mock_pa_gdf, mock_habitat_gdf
):
    """Coastal habitat sits in PAs that WDPA flags MARINE=0, so the buffered run carries
    both estates into the one file and both must come off the habitat."""
    overlapping_terrestrial_pa = gpd.GeoDataFrame(
        {
            "ISO3": ["AUS"],
            "STATUS": ["Designated"],
            "DESIG_ENG": ["National Park"],
            "PA_DEF": [1],
            "geometry": [box(0, 1, 1, 2)],
        },
        crs="EPSG:4326",
    )
    parquet_reads = {
        "static/mangroves_by_location.parquet": mock_habitat_gdf,
        "locations_0.001.parquet": mock_location_gdf,
        "pas_0.001.parquet": pd.concat(
            [
                mock_pa_gdf.assign(environment="marine"),
                overlapping_terrestrial_pa.assign(environment="terrestrial"),
            ],
            ignore_index=True,
        ),
    }
    monkeypatch.setattr(
        subtract,
        "read_parquet_from_gcs",
        lambda bucket_name, filename, verbose=True: parquet_reads[filename].copy(),
    )

    uploads = {}

    def mock_upload_gdf(bucket_name, gdf, destination_blob_name, **_):
        uploads[destination_blob_name] = gdf.copy()

    monkeypatch.setattr(subtract, "upload_gdf", mock_upload_gdf)

    _run_habitat_job()

    result = uploads["conservation_builder/mangroves_minus_pa.parquet"].set_index("location")

    # AUS holds 2.5 of clipped habitat; the marine PA removes 1.0 of it and the
    # terrestrial PA a further 1.0, so subtracting only one estate would leave 1.5.
    assert result.loc["AUS"].geometry.area == pytest.approx(0.5)


def test_pas_keyed_to_a_sea_area_are_subtracted_from_it(monkeypatch, mock_habitat_gdf):
    """A near-shore sea area is a location like any country, keyed on its MRGID. Only
    the rows a buffered run keys to that sea can be subtracted from it: a PA's own ISO3
    is a country code and never matches one."""
    locations = gpd.GeoDataFrame(
        {"location": ["AUS", "4278"], "geometry": [box(0, 0, 2, 2), box(0, 0, 2, 2)]},
        crs="EPSG:4326",
    )
    pas = gpd.GeoDataFrame(
        {
            "ISO3": ["4278"],
            "STATUS": ["Designated"],
            "DESIG_ENG": ["Marine Park"],
            "PA_DEF": [1],
            "environment": ["marine"],
            "geometry": [box(0, 0, 1, 1)],
        },
        crs="EPSG:4326",
    )
    parquet_reads = {
        "static/mangroves_by_location.parquet": mock_habitat_gdf,
        "locations_0.001.parquet": locations,
        "pas_0.001.parquet": pas,
    }
    monkeypatch.setattr(
        subtract,
        "read_parquet_from_gcs",
        lambda bucket_name, filename, verbose=True: parquet_reads[filename].copy(),
    )

    uploads = {}

    def mock_upload_gdf(bucket_name, gdf, destination_blob_name, **_):
        uploads[destination_blob_name] = gdf.copy()

    monkeypatch.setattr(subtract, "upload_gdf", mock_upload_gdf)

    _run_habitat_job()

    result = uploads["conservation_builder/mangroves_minus_pa.parquet"].set_index("location")

    # Both locations cover the same 2.5 of habitat; the PA comes off the sea alone.
    assert result.loc["4278"].geometry.area == pytest.approx(1.5)
    assert result.loc["AUS"].geometry.area == pytest.approx(2.5)


def test_every_input_is_read_from_the_given_bucket(
    monkeypatch, mock_location_gdf, mock_pa_with_seas_gdf, mock_habitat_gdf
):
    """Every read has to honour the bucket argument, or an override sends some inputs
    to one bucket and the rest to whichever the BUCKET constant points at."""
    parquet_reads = {
        "static/mangroves_by_location.parquet": mock_habitat_gdf,
        "locations_0.001.parquet": mock_location_gdf,
        "pas_0.001.parquet": mock_pa_with_seas_gdf,
    }
    buckets = []

    def recording_reader(frames):
        def read(bucket_name, filename, verbose=True):
            buckets.append(bucket_name)
            return frames[filename].copy()

        return read

    monkeypatch.setattr(subtract, "read_parquet_from_gcs", recording_reader(parquet_reads))
    monkeypatch.setattr(subtract, "upload_gdf", lambda **kwargs: None)

    _run_habitat_job()

    assert buckets == ["mock-bucket"] * 3
