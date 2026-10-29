import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import MultiPolygon, Point, Polygon, box

import src.methods.tileset_processes as tp
import src.methods.tileset_processes.vector_tileset_processes as vtp
from src.core.retry_params import METHOD_RETRY_CONFIGS, ScheduleRetry


@pytest.fixture
def mock_gdf():
    """A tiny valid GeoDataFrame with a 'location' column."""
    return gpd.GeoDataFrame(
        {"location": ["AAA", "BBB", "AAA"]},
        geometry=[Point(0, 0), Point(1, 1), Point(2, 2)],
        crs="EPSG:4326",
    )


def mock_add_translations(df, translations_df, key_col, code_col):
    df = df.copy()
    df["code"] = "USA"
    df["name_es"] = "nombre"
    return df


@pytest.mark.parametrize(
    "which, kwargs, expected_local_geojson, expected_source_suffix, expected_process",
    [
        (
            "eez",
            {
                "bucket": "bkt",
                "source_file": "eez_source.geojson",
                "tileset_file": "out.mbtiles",
                "tileset_id": "eez.id",
                "display_name": "EEZ",
                "tolerance": 5,
            },
            "eez.geojson",
            "_5.geojson",
            tp.eez_process,
        ),
        (
            "marine",
            {
                "bucket": "bkt",
                "source_file": "eez_source.geojson",
                "tileset_file": "mr.mbtiles",
                "tileset_id": "mr.id",
                "display_name": "Marine Regions",
                "tolerance": 5,
            },
            "marine_regions.geojson",
            "_5.geojson",
            tp.marine_regions_process,
        ),
        (
            "countries",
            {
                "bucket": "bkt",
                "source_file": "countries.geojson",
                "tileset_file": "cty.mbtiles",
                "tileset_id": "cty.id",
                "display_name": "Countries",
                "tolerance": 5,
            },
            "countries.geojson",
            "_5.geojson",
            tp.countries_process,
        ),
        (
            "terrestrial",
            {
                "bucket": "bkt",
                "source_file": "gadm.geojson",
                "tileset_file": "terr.mbtiles",
                "tileset_id": "terr.id",
                "display_name": "Terrestrial Regions",
                "tolerance": 5,
            },
            "terrestrial_regions.geojson",
            "_5.geojson",
            tp.terrestrial_regions_process,
        ),
    ],
)
def test_wrappers_call_pipeline_with_expected_config(
    which, kwargs, expected_local_geojson, expected_source_suffix, expected_process, monkeypatch
):
    calls = {}

    def mock_run_vector_tileset_pipeline(cfg, *, process):
        calls["cfg"] = cfg
        calls["process"] = process
        return {"tileset_id": cfg.tileset_id, "gcs_blob": cfg.tileset_blob_name}

    monkeypatch.setattr(
        vtp, "run_vector_tileset_pipeline", mock_run_vector_tileset_pipeline, raising=True
    )

    if which == "eez":
        tp.create_and_update_eez_tileset(**kwargs)
    elif which == "marine":
        tp.create_and_update_marine_regions_tileset(**kwargs)
    elif which == "countries":
        tp.create_and_update_country_tileset(**kwargs)
    elif which == "terrestrial":
        tp.create_and_update_terrestrial_regions_tileset(**kwargs)
    else:
        raise AssertionError("Unknown case")

    cfg = calls["cfg"]
    proc = calls["process"]

    assert proc is expected_process
    assert cfg.local_geojson_name == expected_local_geojson
    assert cfg.source_file.endswith(expected_source_suffix)
    assert cfg.tileset_blob_name == kwargs["tileset_file"]
    assert cfg.bucket == kwargs["bucket"]


PMTILES_KWARGS = {
    "source_bucket": "data-bkt",
    "output_bucket": "pmtiles-bkt",
    "output_blob": "layer.pmtiles",
    "archive_bucket": "archive-bkt",
    "archive_blob": "maps/layer/layer_Oct2026.pmtiles",
    "layer_name": "layer",
    "display_name": "Layer",
}


@pytest.mark.parametrize(
    "create_tileset, kwargs, expected_source_file, expected_process, expected_read_source",
    [
        (
            tp.create_and_update_protected_area_tileset,
            {
                **PMTILES_KWARGS,
                "source_file": "pas.geojson",
                "tolerance": 3.2,
                "method": "update_marine_protected_areas_tileset",
            },
            "pas_3.2.geojson",
            tp.protected_area_process,
            None,
        ),
        (
            tp.create_and_update_mpatlas_tileset,
            {**PMTILES_KWARGS, "source_file": "mpa.geojson"},
            "mpa.geojson",
            tp.mpatlas_process,
            vtp.read_mpatlas_from_gcs,
        ),
    ],
)
def test_pmtiles_wrappers_call_pipeline_with_expected_config(
    create_tileset,
    kwargs,
    expected_source_file,
    expected_process,
    expected_read_source,
    monkeypatch,
):
    calls = {}

    def mock_run_vector_pmtiles_pipeline(config, *, process, read_source=None):
        calls["config"] = config
        calls["process"] = process
        calls["read_source"] = read_source

    monkeypatch.setattr(
        vtp, "run_vector_pmtiles_pipeline", mock_run_vector_pmtiles_pipeline, raising=True
    )

    create_tileset(**kwargs)

    config = calls["config"]
    assert calls["process"] is expected_process
    assert calls["read_source"] is expected_read_source
    assert config.source_bucket == "data-bkt"
    assert config.source_file == expected_source_file
    assert config.output_bucket == "pmtiles-bkt"
    assert config.output_blob == "layer.pmtiles"
    assert config.archive_bucket == "archive-bkt"
    assert config.archive_blob == "maps/layer/layer_Oct2026.pmtiles"
    assert config.layer_name == "layer"


def test_mpatlas_process():
    gdf = gpd.GeoDataFrame(
        {
            "designation": ["MPA", "MPA", "MPA", "MPA"],
            "establishment_stage": [
                "actively managed",
                "implemented",
                "designated",
                "proposed/committed",
            ],
            "country": ["ABNJ", "ABNJ", "ABNJ", "ABNJ"],
            "zone_id": ["1", "2", "3", "4"],
            "protection_mpaguide_level": ["high", "full", "low", "high"],
            "name": ["A", "B", "C", "D"],
            "wdpa_id": ["1", "2", "3", "4"],
            "wdpa_pid": ["1", "2_A", "3", "4"],
            "year": ["2017", "2018", "2019", "2020"],
        },
        geometry=gpd.GeoSeries.from_wkt(
            ["POINT (0 0)", "POINT (1 1)", "POINT (2 2)", "POINT (3 3)"]
        ),
        crs="EPSG:4326",
    )

    out = tp.mpatlas_process(gdf.copy(), {"verbose": False})
    expected = {
        "designatio",
        "establishm",
        "location_i",
        "zone_id",
        "name",
        "protection",
        "protecti_1",
        "wdpa_id",
        "wdpa_pid",
        "year",
        "geometry",
    }

    assert out.iloc[0]["protecti_1"] == "fully or highly"
    assert out.iloc[1]["protecti_1"] == "fully or highly"
    assert out.iloc[2]["protecti_1"] == "less or unknown"
    assert out.iloc[3]["protecti_1"] == "fully or highly"
    # Protection levels pass through as delivered by the API
    assert out.iloc[0]["protection"] == "high"
    assert out.iloc[1]["protection"] == "full"
    assert out.iloc[2]["protection"] == "low"
    assert out.iloc[3]["protection"] == "high"
    assert set(out.columns) == expected


def test_eez_process_drops_expected_columns(mock_gdf):
    gdf = mock_gdf.copy()
    gdf["MRGID"] = [1, 2, 3]
    gdf["AREA_KM2"] = [10.0, 20.0, 30.0]

    out = tp.eez_process(gdf, {"verbose": False})
    assert "MRGID" not in out.columns
    assert "AREA_KM2" not in out.columns
    assert {"location", "geometry"} <= set(out.columns)


def test_marine_regions_process(monkeypatch):
    gdf = gpd.GeoDataFrame(
        {
            "location": ["CAN", "USA", "ANG"],
            "MRGID": [1, 2, 3],
            "AREA_KM2": [1.0, 2.0, 3.0],
            "has_shared_marine_area": [False, False, True],
            "index": [0, 1, 2],
        },
        geometry=[Point(0, 0), Point(0, 1), Point(1, 1)],
        crs="EPSG:4326",
    )

    monkeypatch.setattr(
        vtp,
        "read_json_from_gcs",
        lambda bucket, path, verbose=False: {"NA": ["USA", "CAM"], "AF": ["ANG"]},
        raising=True,
    )
    monkeypatch.setattr(
        vtp, "read_dataframe", lambda bucket, path, verbose=False: pd.DataFrame(), raising=True
    )
    monkeypatch.setattr(vtp, "add_translations", mock_add_translations, raising=True)

    result = tp.marine_regions_process(
        gdf,
        {"verbose": False, "bucket": "b", "translation_file": "t.csv", "regions_file": "r.json"},
    )

    assert set(result["region_id"]) == {"NA", "AF"}
    for col in ["MRGID", "AREA_KM2", "has_shared_marine_area", "index", "code", "location"]:
        assert col not in result.columns
    assert "geometry" in result.columns


def test_countries_process(monkeypatch):
    gdf = gpd.GeoDataFrame(
        {"location": ["GBR", "USA", "GGY", "FOO"]},
        geometry=[Point(0, 0), Point(1, 1), Point(2, 2), Point(1, 2)],
        crs="EPSG:4326",
    )

    related = {"GBR*": ["GBR", "FOO"], "USA*": ["USA", "FOO"], "GGY": ["GGY"]}
    monkeypatch.setattr(
        vtp, "read_json_from_gcs", lambda bucket, path, verbose=False: related, raising=True
    )
    monkeypatch.setattr(
        vtp, "read_dataframe", lambda bucket, path, verbose=False: pd.DataFrame(), raising=True
    )
    monkeypatch.setattr(vtp, "add_translations", mock_add_translations, raising=True)

    result = tp.countries_process(
        gdf.copy(),
        {
            "verbose": False,
            "bucket": "b",
            "related_countries_file": "rc.json",
            "translation_file": "t.csv",
        },
    )

    for col in ["ISO_SOV1", "ISO_SOV2", "ISO_SOV3"]:
        assert col in result.columns
        assert pd.api.types.is_string_dtype(result[col])

    row_gbr = result.loc[result["location"] == "GBR"].iloc[0]
    assert row_gbr["ISO_SOV1"] == "GBR*"
    assert pd.isna(row_gbr["ISO_SOV2"])

    row_foo = result.loc[result["location"] == "FOO"].iloc[0]
    assert row_foo["ISO_SOV1"] in ["GBR*", "USA*"]
    assert row_foo["ISO_SOV2"] in ["GBR*", "USA*"]

    assert "code" not in result.columns
    assert "geometry" in result.columns


def test_terrestrial_regions_process(monkeypatch):
    gdf = gpd.GeoDataFrame(
        {"location": ["A", "B", "A"]},
        geometry=[Point(0, 0), Point(1, 1), Point(0, 2)],
        crs="EPSG:4326",
    )

    monkeypatch.setattr(
        vtp,
        "read_json_from_gcs",
        lambda bucket, path, verbose=False: {"R1": ["A"], "R2": ["B"]},
        raising=True,
    )
    monkeypatch.setattr(
        vtp, "read_dataframe", lambda bucket, path, verbose=False: pd.DataFrame(), raising=True
    )
    monkeypatch.setattr(vtp, "add_translations", mock_add_translations, raising=True)

    result = tp.terrestrial_regions_process(
        gdf.copy(),
        {"verbose": False, "bucket": "b", "regions_file": "r.json", "translation_file": "t.csv"},
    )

    assert set(result["region_id"]) == {"R1", "R2"}
    assert "location" not in result.columns
    assert "code" not in result.columns
    assert "geometry" in result.columns


@pytest.mark.parametrize(
    "method",
    [
        "update_marine_protected_areas_tileset",
        "update_terrestrial_protected_areas_tileset",
    ],
)
def test_protected_area_tileset_raises_schedule_retry_on_failure(method, monkeypatch):
    def mock_run_vector_pmtiles_pipeline(config, *, process):
        raise RuntimeError("upload error")

    monkeypatch.setattr(
        vtp, "run_vector_pmtiles_pipeline", mock_run_vector_pmtiles_pipeline, raising=True
    )

    with pytest.raises(ScheduleRetry) as exc_info:
        tp.create_and_update_protected_area_tileset(
            **PMTILES_KWARGS,
            source_file="pas.geojson",
            tolerance=3.2,
            method=method,
        )

    cfg = METHOD_RETRY_CONFIGS[method]
    assert exc_info.value.delay_seconds == cfg["delay_seconds"]
    assert exc_info.value.max_retries == cfg["max_retries"]


def test_protected_area_process():
    gdf = gpd.GeoDataFrame(
        {
            "GIS_AREA": [1.2],
            "NAME": ["Foo Park"],
            "PA_DEF": [1],
            "ISO3": ["AAA"],
            "WDPAID": [123],
            "WDPA_PID": ["123_A"],
            "EXTRA1": [999],
            "EXTRA2": ["dropme"],
        },
        geometry=[Point(0, 0)],
        crs="EPSG:4326",
    )

    out = tp.protected_area_process(gdf.copy(), {"verbose": False})
    expected = {"GIS_AREA", "NAME", "PA_DEF", "ISO3", "WDPAID", "WDPA_PID", "geometry"}
    assert set(out.columns) == expected


HABITAT_PARAMS = {
    "mangroves": {"file_name": "habitats/mangroves.gpkg.gz", "source": "gpkg"},
    "seagrasses": {"file_name": "habitats/seagrasses.zip", "source": "wcmc"},
}


@pytest.mark.parametrize("habitat", ["mangroves", "seagrasses"])
def test_marine_habitat_tileset_reads_the_habitat_source(habitat, monkeypatch):
    calls = {}

    def mock_run_vector_pmtiles_pipeline(config, *, read_source):
        calls["config"] = config
        calls["gdf"] = read_source(config.source_bucket, config.source_file)

    def mock_load_habitat_geometry(name, params, bucket, fallback_area_km2, verbose):
        calls["load"] = (name, params, bucket, fallback_area_km2)
        return gpd.GeoDataFrame(geometry=[box(0, 0, 1, 1)], crs="EPSG:4326")

    monkeypatch.setattr(
        vtp, "run_vector_pmtiles_pipeline", mock_run_vector_pmtiles_pipeline, raising=True
    )
    monkeypatch.setattr(vtp, "_load_habitat_geometry", mock_load_habitat_geometry, raising=True)

    tp.create_and_update_marine_habitat_tileset(
        **PMTILES_KWARGS,
        habitat=habitat,
        method=f"update_{habitat}_tileset",
        habitat_params=HABITAT_PARAMS,
        fallback_area_km2=2.5,
    )

    config = calls["config"]
    assert calls["load"] == (habitat, HABITAT_PARAMS[habitat], "data-bkt", 2.5)
    assert calls["gdf"].geometry.iloc[0].equals(box(0, 0, 1, 1))
    assert config.source_file == HABITAT_PARAMS[habitat]["file_name"]
    assert config.output_bucket == "pmtiles-bkt"
    assert config.output_blob == "layer.pmtiles"
    assert config.archive_bucket == "archive-bkt"
    assert config.archive_blob == "maps/layer/layer_Oct2026.pmtiles"
    assert config.layer_name == "layer"


@pytest.mark.parametrize("method", ["update_mangroves_tileset", "update_seagrasses_tileset"])
def test_marine_habitat_tileset_raises_schedule_retry_on_failure(method, monkeypatch):
    def mock_run_vector_pmtiles_pipeline(config, *, read_source):
        raise RuntimeError("tippecanoe error")

    monkeypatch.setattr(
        vtp, "run_vector_pmtiles_pipeline", mock_run_vector_pmtiles_pipeline, raising=True
    )

    with pytest.raises(ScheduleRetry) as exc_info:
        tp.create_and_update_marine_habitat_tileset(
            **PMTILES_KWARGS,
            habitat="mangroves",
            method=method,
            habitat_params=HABITAT_PARAMS,
        )

    cfg = METHOD_RETRY_CONFIGS[method]
    assert exc_info.value.delay_seconds == cfg["delay_seconds"]
    assert exc_info.value.max_retries == cfg["max_retries"]


def test_marine_habitat_tileset_is_unknown_for_unconfigured_habitat():
    with pytest.raises(KeyError):
        tp.create_and_update_marine_habitat_tileset(
            **PMTILES_KWARGS,
            habitat="kelp",
            method="update_kelp_tileset",
            habitat_params=HABITAT_PARAMS,
        )


def read_marine_habitat(gdf, monkeypatch):
    monkeypatch.setattr(vtp, "_load_habitat_geometry", lambda *args: gdf, raising=True)
    return tp.read_marine_habitat(
        "bkt",
        "habitat.zip",
        habitat="seagrasses",
        params=HABITAT_PARAMS["seagrasses"],
        fallback_area_km2=1.0,
        verbose=False,
    )


def test_read_marine_habitat_simplifies_and_keeps_only_geometry(monkeypatch):
    bowtie = Polygon([(10, 10), (11, 11), (11, 10), (10, 11)])
    gdf = gpd.GeoDataFrame(
        {
            "source": ["polygon", "point"],
            "rep_area_km2": [1.0, 2.0],
        },
        geometry=[MultiPolygon([box(30, 30, 31, 31), box(32, 32, 33, 33)]), bowtie],
        crs="EPSG:4326",
    )

    out = read_marine_habitat(gdf, monkeypatch)

    assert set(out.columns) == {"geometry"}
    assert out.crs == "EPSG:4326"
    assert len(out) == 3
    assert out.geometry.is_valid.all()
