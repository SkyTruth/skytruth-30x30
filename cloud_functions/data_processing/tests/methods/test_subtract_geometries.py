import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin
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


RASTER_HABITATS = ("other-corals", "climate-resilient-corals")


@pytest.fixture
def mock_raster(tmp_path):
    """A 40x40 EPSG:3857 raster of 1 km pixels, nodata 255.

    Two 100-pixel blocks, one per class, plus a stray class-1 pixel outside the
    country below so the country clip has something to exclude.
    """
    path = tmp_path / "corals.tif"
    data = np.full((40, 40), 255, dtype="uint8")
    data[5:15, 5:15] = 1
    data[20:30, 20:30] = 0
    data[32, 32] = 1

    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=40,
        width=40,
        count=1,
        dtype="uint8",
        crs="EPSG:3857",
        transform=from_origin(0, 1_000_000, 1000.0, 1000.0),
        nodata=255,
    ) as dst:
        dst.write(data, 1)

    return str(path)


def _country(code, geom_3857):
    return gpd.GeoDataFrame({"location": [code]}, geometry=[geom_3857], crs="EPSG:3857").to_crs(
        "EPSG:4326"
    )


@pytest.fixture
def mock_raster_country():
    """Covers both class blocks but stops short of the stray pixel at [32, 32]."""
    return _country("AAA", box(0, 1_000_000 - 32_000, 32_000, 1_000_000))


@pytest.fixture
def mock_raster_pa():
    """Covers the left half of the class-1 block: 50 of its 100 pixels."""
    return gpd.GeoDataFrame(
        geometry=[box(0, 1_000_000 - 15_000, 10_000, 1_000_000 - 5_000)], crs="EPSG:3857"
    ).to_crs("EPSG:4326")


@pytest.fixture
def no_pas():
    return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")


def _areas_by_habitat(result):
    """Planar km2 per habitat in the raster's own CRS, where a pixel is exactly 1."""
    projected = result.to_crs("EPSG:3857")
    return dict(zip(result["habitat"], projected.area / 1e6, strict=True))


def test_raster_classes_come_back_as_one_row_each(mock_raster, mock_raster_country, no_pas):
    result = subtract.process_country_raster_habitat(
        mock_raster_country, no_pas, mock_raster, dict(enumerate(RASTER_HABITATS))
    )

    # The stray pixel at [32, 32] lies outside the country, so class 1 keeps 100 of
    # its 101 pixels; without the country clip it would come back as 101.
    assert _areas_by_habitat(result) == pytest.approx(
        {"other-corals": 100.0, "climate-resilient-corals": 100.0}
    )


def test_protected_pixels_are_removed_from_their_own_class(
    mock_raster, mock_raster_country, mock_raster_pa
):
    result = subtract.process_country_raster_habitat(
        mock_raster_country, mock_raster_pa, mock_raster, dict(enumerate(RASTER_HABITATS))
    )

    # The PA covers half the class-1 block and none of the class-0 block.
    assert _areas_by_habitat(result) == pytest.approx(
        {"other-corals": 100.0, "climate-resilient-corals": 50.0}
    )


def test_output_is_reprojected_to_4326(mock_raster, mock_raster_country, no_pas):
    """update_cb declares Geometry(MultiPolygon, 4326) and the analysis SQL transforms
    from longlat, so returning the raster's own CRS would load without error and then
    compute nonsense areas."""
    result = subtract.process_country_raster_habitat(
        mock_raster_country, no_pas, mock_raster, dict(enumerate(RASTER_HABITATS))
    )

    assert result.crs == "EPSG:4326"


def test_geometries_are_valid_multipolygons(mock_raster, mock_raster_country, no_pas):
    """The parts are assembled without a union, so nothing repairs them on the way out;
    update_cb coerces to MultiPolygon and then runs ST_Subdivide, which needs valid
    input."""
    result = subtract.process_country_raster_habitat(
        mock_raster_country, no_pas, mock_raster, dict(enumerate(RASTER_HABITATS))
    )

    assert list(result.geom_type.unique()) == ["MultiPolygon"]
    assert result.geometry.is_valid.all()


def test_country_inside_the_raster_holding_no_habitat_is_empty(mock_raster, no_pas):
    """Distinct from falling outside the raster: this country is within bounds but every
    pixel under it is nodata."""
    barren = _country("CCC", box(35_000, 1_000_000 - 40_000, 39_000, 1_000_000 - 36_000))

    result = subtract.process_country_raster_habitat(
        barren, no_pas, mock_raster, dict(enumerate(RASTER_HABITATS))
    )

    assert result.empty


def test_country_outside_the_raster_is_empty(mock_raster, no_pas):
    far = _country("BBB", box(5_000_000, 5_000_000, 5_010_000, 5_010_000))

    result = subtract.process_country_raster_habitat(
        far, no_pas, mock_raster, dict(enumerate(RASTER_HABITATS))
    )

    assert result.empty


def test_a_fully_protected_class_gets_no_row(mock_raster, mock_raster_country):
    """A class with nothing left after the PAs come off is dropped rather than written
    with an empty geometry, which could never satisfy ST_Intersects anyway."""
    covers_everything = gpd.GeoDataFrame(
        geometry=[box(0, 1_000_000 - 40_000, 40_000, 1_000_000)], crs="EPSG:3857"
    ).to_crs("EPSG:4326")

    result = subtract.process_country_raster_habitat(
        mock_raster_country, covers_everything, mock_raster, dict(enumerate(RASTER_HABITATS))
    )

    assert result.empty


def test_empty_results_carry_the_output_columns(mock_raster, no_pas):
    """generate_raster_habitat_minus_pa concats these and filters on .empty, so an empty
    return still has to look like the populated one."""
    far = _country("BBB", box(5_000_000, 5_000_000, 5_010_000, 5_010_000))

    result = subtract.process_country_raster_habitat(
        far, no_pas, mock_raster, dict(enumerate(RASTER_HABITATS))
    )

    assert list(result.columns) == ["location", "habitat", "geometry"]
    assert result.crs == "EPSG:4326"


@pytest.fixture
def raster_job_mocks(monkeypatch, tmp_path, mock_raster, mock_raster_country, mock_raster_pa):
    """Serve the job's two parquet reads and capture its uploads.

    The job downloads the raster to basename(habitat_file_name) in the working
    directory, so the test runs from the directory mock_raster already wrote it to.
    """
    monkeypatch.chdir(tmp_path)

    locations = pd.concat(
        [mock_raster_country, _country("BBB", box(5_000_000, 5_000_000, 5_010_000, 5_010_000))],
        ignore_index=True,
    )
    pas = mock_raster_pa.assign(ISO3="AAA", STATUS="Designated", DESIG_ENG="Marine Park", PA_DEF=1)
    parquet_reads = {
        "locations_0.001.parquet": gpd.GeoDataFrame(locations, crs="EPSG:4326"),
        "pas_0.001.parquet": pas,
    }
    uploads = {}

    monkeypatch.setattr(subtract, "download_file_from_gcs", lambda *args, **kwargs: None)
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


def _run_raster_habitat_job(habitats=RASTER_HABITATS):
    subtract.generate_raster_habitat_minus_pa(
        habitat_file_name="raw/corals.tif",
        habitats=habitats,
        total_area_file="locations.parquet",
        pa_file="pas.parquet",
        tolerance=0.001,
        bucket="mock-bucket",
        n_jobs=1,
        verbose=False,
    )


def test_each_class_is_written_to_its_own_pair_of_blobs(raster_job_mocks):
    """update_cb keeps only location and the geometry, so two classes sharing one table
    would be indistinguishable once loaded."""
    _run_raster_habitat_job()

    assert set(raster_job_mocks) == {
        "conservation_builder/other-corals_minus_pa.parquet",
        "conservation_builder/climate-resilient-corals_minus_pa.parquet",
        ARCHIVE_CONSERVATION_BUILDER_HABITAT_DATA_PATTERN.format(habitat="other-corals"),
        ARCHIVE_CONSERVATION_BUILDER_HABITAT_DATA_PATTERN.format(
            habitat="climate-resilient-corals"
        ),
    }


def test_habitat_names_map_to_pixel_values_by_position(raster_job_mocks):
    """habitats carries the raster's encoding in its order, so swapping the two names
    swaps which pixels each file gets. Nothing downstream could detect that, since both
    files stay well-formed."""
    _run_raster_habitat_job(habitats=("climate-resilient-corals", "other-corals"))

    swapped = raster_job_mocks["conservation_builder/climate-resilient-corals_minus_pa.parquet"]

    # Value 0 is the unprotected 100-pixel block; under the swapped names it lands in
    # the climate-resilient file rather than the 50 pixels that class really has.
    assert float((swapped.to_crs("EPSG:3857").area / 1e6).sum()) == pytest.approx(100.0)


def test_countries_holding_no_raster_habitat_are_dropped(raster_job_mocks):
    _run_raster_habitat_job()

    for blob in raster_job_mocks.values():
        assert list(blob["location"]) == ["AAA"]


def test_a_class_with_no_rows_anywhere_still_writes_its_blobs(raster_job_mocks, monkeypatch):
    """The uploads are driven by the habitat names, not by what survived, so a class the
    run found nothing for still gets a file rather than leaving a stale one in place."""
    monkeypatch.setattr(
        subtract,
        "process_country_raster_habitat",
        lambda *args, **kwargs: gpd.GeoDataFrame(
            {"location": [], "habitat": []}, geometry=[], crs="EPSG:4326"
        ),
    )

    _run_raster_habitat_job()

    assert len(raster_job_mocks) == 4
    for blob in raster_job_mocks.values():
        assert blob.empty
        assert list(blob.columns) == ["location", "habitat", "geometry"]
