import struct

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

import src.methods.subtract_geometries.io as subtract_io
import src.methods.subtract_geometries.raster_habitat as raster_habitat
from src.core.params import (
    ARCHIVE_CONSERVATION_BUILDER_HABITAT_DATA_PATTERN,
    ARCHIVE_CONSERVATION_BUILDER_HABITAT_TILES_DIR_PATTERN,
)

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
    result = raster_habitat.process_country_raster_habitat(
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
    result = raster_habitat.process_country_raster_habitat(
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
    result = raster_habitat.process_country_raster_habitat(
        mock_raster_country, no_pas, mock_raster, dict(enumerate(RASTER_HABITATS))
    )

    assert result.crs == "EPSG:4326"


def test_geometries_are_valid_multipolygons(mock_raster, mock_raster_country, no_pas):
    """The parts are assembled without a union, so nothing repairs them on the way out;
    update_cb coerces to MultiPolygon and then runs ST_Subdivide, which needs valid
    input."""
    result = raster_habitat.process_country_raster_habitat(
        mock_raster_country, no_pas, mock_raster, dict(enumerate(RASTER_HABITATS))
    )

    assert list(result.geom_type.unique()) == ["MultiPolygon"]
    assert result.geometry.is_valid.all()


def test_country_inside_the_raster_holding_no_habitat_is_empty(mock_raster, no_pas):
    """Distinct from falling outside the raster: this country is within bounds but every
    pixel under it is nodata."""
    barren = _country("CCC", box(35_000, 1_000_000 - 40_000, 39_000, 1_000_000 - 36_000))

    result = raster_habitat.process_country_raster_habitat(
        barren, no_pas, mock_raster, dict(enumerate(RASTER_HABITATS))
    )

    assert result.empty


def test_country_outside_the_raster_is_empty(mock_raster, no_pas):
    far = _country("BBB", box(5_000_000, 5_000_000, 5_010_000, 5_010_000))

    result = raster_habitat.process_country_raster_habitat(
        far, no_pas, mock_raster, dict(enumerate(RASTER_HABITATS))
    )

    assert result.empty


def test_a_fully_protected_class_gets_no_row(mock_raster, mock_raster_country):
    """A class with nothing left after the PAs come off is dropped rather than written
    with an empty geometry, which could never satisfy ST_Intersects anyway."""
    covers_everything = gpd.GeoDataFrame(
        geometry=[box(0, 1_000_000 - 40_000, 40_000, 1_000_000)], crs="EPSG:3857"
    ).to_crs("EPSG:4326")

    result = raster_habitat.process_country_raster_habitat(
        mock_raster_country, covers_everything, mock_raster, dict(enumerate(RASTER_HABITATS))
    )

    assert result.empty


def test_empty_results_carry_the_output_columns(mock_raster, no_pas):
    """generate_raster_habitat_minus_pa concats these and filters on .empty, so an empty
    return still has to look like the populated one."""
    far = _country("BBB", box(5_000_000, 5_000_000, 5_010_000, 5_010_000))

    result = raster_habitat.process_country_raster_habitat(
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

    monkeypatch.setattr(raster_habitat, "download_file_from_gcs", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        raster_habitat,
        "read_parquet_from_gcs",
        lambda bucket_name, filename, verbose=True: parquet_reads[filename].copy(),
    )
    monkeypatch.setattr(
        subtract_io,
        "upload_gdf",
        lambda bucket_name, gdf, destination_blob_name, **_: uploads.__setitem__(
            destination_blob_name, gdf.copy()
        ),
    )

    return uploads


def _run_raster_habitat_job(habitats=RASTER_HABITATS):
    raster_habitat.generate_raster_habitat_minus_pa(
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
        raster_habitat,
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


# --- raster tiles -------------------------------------------------------------------

TILE_PX = 16
CHUNK_PX = 32
WKB_HEADER = "<BHHddddddiHH"


def _decode_tile(wkb):
    """Reads back the header fields and pixels of one PostGIS raster WKB tile."""
    fields = struct.unpack_from(WKB_HEADER, wkb)
    flags, nodata = struct.unpack_from("<BB", wkb, struct.calcsize(WKB_HEADER))
    width, height = fields[-2], fields[-1]
    pixels = np.frombuffer(wkb, dtype="uint8", offset=struct.calcsize(WKB_HEADER) + 2)
    return fields, flags, nodata, pixels.reshape(height, width)


def _tiles(country, pas, raster):
    return raster_habitat.process_location_raster_tiles(
        country, pas, raster, tile_size_pixels=TILE_PX, chunk_size_pixels=CHUNK_PX
    )


def _pixel_counts(tiles):
    values = np.concatenate([_decode_tile(wkb)[3].ravel() for wkb in tiles["rast"]])
    return dict(zip(*np.unique(values, return_counts=True), strict=True))


def test_tile_wkb_follows_the_postgis_raster_layout():
    pixels = np.arange(6, dtype="uint8").reshape(2, 3)
    transform = from_origin(10.0, 20.0, 0.5, 0.25)

    fields, flags, nodata, decoded = _decode_tile(
        raster_habitat.raster_tile_wkb(pixels, transform, 4326, 0)
    )

    assert fields == (1, 0, 1, 0.5, -0.25, 10.0, 20.0, 0.0, 0.0, 4326, 3, 2)
    assert flags == raster_habitat.PT_8BUI | raster_habitat.BAND_HAS_NODATA
    assert nodata == 0
    np.testing.assert_array_equal(decoded, pixels)


def test_protected_and_outside_pixels_become_nodata(
    mock_raster, mock_raster_country, mock_raster_pa
):
    """Class 1 keeps the 50 unprotected pixels of its block and loses the stray pixel
    outside the country; class 0 keeps all 100."""
    counts = _pixel_counts(_tiles(mock_raster_country, mock_raster_pa, mock_raster))

    assert counts[1] == 50
    assert counts[0] == 100


def test_tiles_holding_only_nodata_are_dropped(mock_raster, mock_raster_country, no_pas):
    """Of the four 16-pixel tiles over the country, only the two holding a class block
    have any habitat."""
    tiles = _tiles(mock_raster_country, no_pas, mock_raster)

    assert len(tiles) == 2


def test_tile_footprints_match_their_georeference(mock_raster, mock_raster_country, no_pas):
    tiles = _tiles(mock_raster_country, no_pas, mock_raster)

    for wkb, footprint in zip(tiles["rast"], tiles.geometry, strict=True):
        (_, _, _, scale_x, scale_y, ul_x, ul_y, _, _, srid, width, height), *_ = _decode_tile(wkb)
        assert srid == 3857
        assert footprint.bounds == pytest.approx(
            (ul_x, ul_y + scale_y * height, ul_x + scale_x * width, ul_y)
        )


def test_a_location_outside_the_raster_has_no_tiles(mock_raster, no_pas):
    far = _country("BBB", box(5_000_000, 5_000_000, 5_010_000, 5_010_000))

    tiles = _tiles(far, no_pas, mock_raster)

    assert tiles.empty
    assert list(tiles.columns) == ["location", "rast", "geometry"]


@pytest.fixture
def tiles_job_mocks(raster_job_mocks, monkeypatch):
    """raster_job_mocks, with the locations and PAs served through read_geo_df and the
    stale-file cleanup captured instead of run."""
    reads = {
        "locations_0.001.parquet": raster_habitat.read_parquet_from_gcs(
            "mock-bucket", "locations_0.001.parquet"
        ),
        "pas_0.001.parquet": raster_habitat.read_parquet_from_gcs(
            "mock-bucket", "pas_0.001.parquet"
        ),
    }
    monkeypatch.setattr(
        raster_habitat,
        "read_geo_df",
        lambda bucket_name, filename, verbose=True: reads[filename].copy(),
    )
    cleanups = []
    monkeypatch.setattr(
        raster_habitat,
        "delete_stale_blobs",
        lambda bucket_name, prefix, current, **_: cleanups.append((prefix, current)),
    )
    return raster_job_mocks, cleanups


def _run_tiles_job():
    return raster_habitat.generate_raster_habitat_tiles(
        habitat="terrestrial-habitats",
        raster_file_name="raw/corals.tif",
        total_area_file="locations.parquet",
        pa_file="pas.parquet",
        tolerance=0.001,
        bucket="mock-bucket",
        n_jobs=1,
        verbose=False,
    )


def test_each_location_with_habitat_gets_a_live_and_an_archive_file(tiles_job_mocks):
    """BBB lies outside the raster, so it gets no file."""
    uploads, _ = tiles_job_mocks

    _run_tiles_job()

    assert set(uploads) == {
        "conservation_builder/terrestrial-habitats_minus_pa_tiles/AAA.parquet",
        ARCHIVE_CONSERVATION_BUILDER_HABITAT_TILES_DIR_PATTERN.format(
            habitat="terrestrial-habitats"
        )
        + "/AAA.parquet",
    }


def test_stale_files_are_cleared_against_this_runs_files(tiles_job_mocks):
    """Anything else in the live folder, such as BBB's file from an earlier run, would
    otherwise still be loaded."""
    _, cleanups = tiles_job_mocks

    written = _run_tiles_job()

    assert cleanups == [("conservation_builder/terrestrial-habitats_minus_pa_tiles/", written)]
    assert written == {"conservation_builder/terrestrial-habitats_minus_pa_tiles/AAA.parquet"}
