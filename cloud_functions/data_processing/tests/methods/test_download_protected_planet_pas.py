import os
import shutil

import geopandas as gpd
import pytest
import shapely
from shapely.geometry import Point

from src.methods import download_and_process
from src.methods.download_and_process import download_and_process_protected_planet_pas

# Deliberately not the production values - distinct, coarse tolerances make the
# filename suffixes unambiguous and the simplification effect measurable.
TEST_TOLERANCES = (0.5, 0.001)

# download_and_process_protected_planet_pas hardcodes tmp_dir = "/tmp", so the
# parquet fixtures have to live where it will look for them.
PA_DIR = "/tmp/wdpa"


@pytest.fixture
def mock_wdpa_parquet():
    """Write a WDPA-shaped parquet into the directory the job unpacks into.

    Columns follow the current Protected Planet schema, i.e. the names
    `match_old_pa_naming_convantion` renames. REALM drives the
    terrestrial/marine split and SITE_TYPE drives PA_DEF, so the rows cover a
    terrestrial PA, a marine PA, a coastal PA, and the two MAB reserves that
    the OECM filter treats differently.
    """
    gdf = gpd.GeoDataFrame(
        {
            "SITE_ID": [1, 2, 3, 4, 5],
            "SITE_PID": ["1_A", "2_A", "3_A", "4_A", "5_A"],
            "NAME_ENG": ["Terr PA", "Marine PA", "Coastal PA", "MAB PA", "MAB OECM"],
            "NAME": ["terr", "marine", "coastal", "mab_pa", "mab_oecm"],
            "PRNT_ISO3": ["USA", "USA", "MEX", "USA", "USA"],
            "ISO3": ["USA", "USA", "MEX", "USA", "USA"],
            "SITE_TYPE": ["PA", "PA", "PA", "PA", "OECM"],
            "REALM": ["Terrestrial", "Marine", "Coastal", "Terrestrial", "Terrestrial"],
            "DESIG_ENG": [
                "National Park",
                "Marine Reserve",
                "Marine Park",
                "UNESCO-MAB Biosphere Reserve",
                "UNESCO-MAB Biosphere Reserve",
            ],
            "REP_AREA": [100.0, 200.0, 300.0, 400.0, 500.0],
            "GIS_AREA": [101.0, 201.0, 301.0, 401.0, 501.0],
            "geometry": [
                Point(-100, 35).buffer(1.0),
                Point(-90, 25).buffer(1.0),
                Point(-102, 18).buffer(1.0),
                Point(-95, 40).buffer(1.0),
                Point(-97, 42).buffer(1.0),
            ],
        },
        crs="EPSG:4326",
    )

    shutil.rmtree(PA_DIR, ignore_errors=True)
    os.makedirs(PA_DIR, exist_ok=True)
    gdf.to_parquet(os.path.join(PA_DIR, "WDPA_polygons.parquet"))

    yield gdf

    shutil.rmtree(PA_DIR, ignore_errors=True)


class _SerialParallel:
    """joblib.Parallel stand-in that runs jobs in-process.

    Keeps the real `delayed`, which yields (func, args, kwargs) tuples, so the
    production call site is unchanged - this only removes the loky pool.
    """

    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, jobs):
        return [func(*args, **kwargs) for func, args, kwargs in jobs]


@pytest.fixture
def pa_job_recorder(monkeypatch):
    """Stub out network and GCS, recording every upload the job performs."""
    calls = {"downloads": [], "gdf": [], "dataframe": [], "duplicates": [], "files": []}

    def _download_file_with_progress(url, filename, verbose=True):
        calls["downloads"].append(url)
        return True

    def _upload_gdf(bucket, gdf, destination_blob_name, **kwargs):
        assert isinstance(gdf, gpd.GeoDataFrame)
        calls["gdf"].append({"blob": destination_blob_name, "gdf": gdf.copy()})

    def _upload_dataframe(bucket, df, destination_blob_name, **kwargs):
        calls["dataframe"].append({"blob": destination_blob_name, "df": df.copy()})

    def _duplicate_blob(bucket, source, destination, **kwargs):
        calls["duplicates"].append((source, destination))

    def _upload_file_to_gcs(bucket, file_name, blob_name, **kwargs):
        calls["files"].append(blob_name)

    monkeypatch.setattr(
        download_and_process, "download_file_with_progress", _download_file_with_progress
    )
    monkeypatch.setattr(download_and_process, "upload_gdf", _upload_gdf)
    monkeypatch.setattr(download_and_process, "upload_dataframe", _upload_dataframe)
    monkeypatch.setattr(download_and_process, "duplicate_blob", _duplicate_blob)
    monkeypatch.setattr(download_and_process, "upload_file_to_gcs", _upload_file_to_gcs)
    # No-op so the fixture parquets in PA_DIR survive the (real) unpack step,
    # which then finds no *.zip and does nothing.
    monkeypatch.setattr(download_and_process, "unzip_file", lambda *a, **k: None)
    monkeypatch.setattr(download_and_process, "Parallel", _SerialParallel)
    monkeypatch.setattr(download_and_process, "show_container_mem", lambda *a, **k: None)

    return calls


def _run_job(tolerances=TEST_TOLERANCES):
    download_and_process_protected_planet_pas(
        terrestrial_pa_file_name="pas/terrestrial.geojson",
        marine_pa_file_name="pas/marine.geojson",
        meta_file_name="pas/meta.csv",
        archive_wdpa_file_name="archive/wdpa.zip",
        tolerances=tolerances,
        bucket="test-bucket",
        batch_size=2,
        n_jobs=1,
        verbose=False,
    )


def test_one_download_produces_every_tolerance(mock_wdpa_parquet, pa_job_recorder):
    """A single download yields a terrestrial and marine file per tolerance."""
    _run_job()

    assert len(pa_job_recorder["downloads"]) == 1

    assert {call["blob"] for call in pa_job_recorder["gdf"]} == {
        "pas/terrestrial_0.5.geojson",
        "pas/marine_0.5.geojson",
        "pas/terrestrial_0.001.geojson",
        "pas/marine_0.001.geojson",
    }


def test_later_tolerances_still_see_the_unpacked_parquets(mock_wdpa_parquet, pa_job_recorder):
    """The last tolerance pass must not read an emptied pa_dir.

    This is the regression the loop introduced: pa_dir used to be deleted right
    after the single simplify pass, which would starve every pass after the
    first.
    """
    _run_job()

    by_blob = {call["blob"]: call["gdf"] for call in pa_job_recorder["gdf"]}
    last = by_blob["pas/terrestrial_0.001.geojson"]

    assert not last.empty
    assert set(last["ISO3"]) == {"USA"}


def test_pa_dir_is_removed_once_all_tolerances_are_done(mock_wdpa_parquet, pa_job_recorder):
    _run_job()

    assert not os.path.exists(PA_DIR)


def test_metadata_is_uploaded_exactly_once(mock_wdpa_parquet, pa_job_recorder):
    """Metadata is tolerance-independent, so it is written on the first pass only."""
    _run_job()

    assert len(pa_job_recorder["dataframe"]) == 1

    meta = pa_job_recorder["dataframe"][0]
    assert meta["blob"] == "pas/meta.csv"
    assert "geometry" not in meta["df"].columns
    # Written before the MAB filter, so every source row is represented
    assert len(meta["df"]) == len(mock_wdpa_parquet)


def test_coarser_tolerance_simplifies_more(mock_wdpa_parquet, pa_job_recorder):
    """Each pass really does simplify at its own tolerance."""
    _run_job()

    by_blob = {call["blob"]: call["gdf"] for call in pa_job_recorder["gdf"]}

    def vertices(blob):
        return int(shapely.get_num_coordinates(by_blob[blob].geometry.values).sum())

    assert vertices("pas/marine_0.5.geojson") < vertices("pas/marine_0.001.geojson")


def test_realm_split_and_mab_filter(mock_wdpa_parquet, pa_job_recorder):
    """REALM drives the split; non-OECM MAB reserves are dropped from both files."""
    _run_job()

    by_blob = {call["blob"]: call["gdf"] for call in pa_job_recorder["gdf"]}

    terrestrial = by_blob["pas/terrestrial_0.5.geojson"]
    marine = by_blob["pas/marine_0.5.geojson"]

    # Terrestrial keeps the plain PA and the MAB OECM, but not the MAB PA
    assert set(terrestrial["WDPAID"]) == {1, 5}
    # Marine and Coastal both land in the marine file
    assert set(marine["WDPAID"]) == {2, 3}


def test_each_output_is_archived(mock_wdpa_parquet, pa_job_recorder):
    _run_job()

    assert set(pa_job_recorder["duplicates"]) == {
        ("pas/terrestrial_0.5.geojson", "archive/pas/terrestrial_0.5.geojson"),
        ("pas/marine_0.5.geojson", "archive/pas/marine_0.5.geojson"),
        ("pas/terrestrial_0.001.geojson", "archive/pas/terrestrial_0.001.geojson"),
        ("pas/marine_0.001.geojson", "archive/pas/marine_0.001.geojson"),
    }


def test_single_tolerance_runs_clean(mock_wdpa_parquet, pa_job_recorder):
    """The loop must not depend on there being more than one tolerance."""
    _run_job(tolerances=(0.5,))

    assert {call["blob"] for call in pa_job_recorder["gdf"]} == {
        "pas/terrestrial_0.5.geojson",
        "pas/marine_0.5.geojson",
    }
    assert len(pa_job_recorder["dataframe"]) == 1
    assert not os.path.exists(PA_DIR)
