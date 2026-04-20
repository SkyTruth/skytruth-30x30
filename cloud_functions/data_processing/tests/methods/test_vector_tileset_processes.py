import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

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
            },
            "countries.geojson",
            "_7.geojson",
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
            },
            "terrestrial_regions.geojson",
            "_7.geojson",
            tp.terrestrial_regions_process,
        ),
        (
            "protected",
            {
                "bucket": "bkt",
                "source_file": "pas.geojson",
                "tileset_file": "pas.mbtiles",
                "tileset_id": "pas.id",
                "display_name": "Protected Areas",
                "tolerance": 3.2,
                "method": "update_marine_protected_areas_tileset",
            },
            "pas.id.geojson",
            "_3.2.geojson",
            tp.protected_area_process,
        ),
        (
            "mpatlas",
            {
                "bucket": "bkt",
                "source_file": "mpa.geojson",
                "tileset_file": "mpa.mbtiles",
                "tileset_id": "mpa.id",
                "display_name": "MPAtlas",
            },
            "mpa.id.geojson",
            ".geojson",
            tp.mpatlas_process,
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

    monkeypatch.setattr(vtp, "EEZ_TOLERANCE", 5, raising=True)
    monkeypatch.setattr(vtp, "COUNTRIES_TOLERANCE", 7, raising=True)
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
    elif which == "protected":
        tp.create_and_update_protected_area_tileset(**kwargs)
    elif which == "mpatlas":
        tp.create_and_update_mpatlas_tileset(**kwargs)
    else:
        raise AssertionError("Unknown case")

    cfg = calls["cfg"]
    proc = calls["process"]

    assert proc is expected_process
    assert cfg.local_geojson_name == expected_local_geojson
    assert cfg.source_file.endswith(expected_source_suffix)
    assert cfg.tileset_blob_name == kwargs["tileset_file"]
    assert cfg.bucket == kwargs["bucket"]


def test_mpatlas_process():
    gdf = gpd.GeoDataFrame(
        {
            "designation": ["MPA", "MPA", "MPA"],
            "establishment_stage": ["implemented", "implemented", "implemented"],
            "country": ["ABNJ", "ABNJ", "ABNJ"],
            "zone_id": ["1", "2", "3"],
            "protection_mpaguide_level": ["high", "full", "low"],
            "name": ["A", "B", "C"],
            "wdpa_id": ["1", "2", "3"],
            "year": ["2017", "2018", "2019"],
        },
        geometry=gpd.GeoSeries.from_wkt(["POINT (0 0)", "POINT (1 1)", "POINT (2 2)"]),
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
        "year",
        "geometry",
    }

    assert out.iloc[0]["protecti_1"] == "fully or highly"
    assert out.iloc[1]["protecti_1"] == "fully or highly"
    assert out.iloc[2]["protecti_1"] == "less or unknown"
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
    def mock_run_vector_tileset_pipeline(cfg, *, process):
        raise RuntimeError("auth error")

    monkeypatch.setattr(
        vtp, "run_vector_tileset_pipeline", mock_run_vector_tileset_pipeline, raising=True
    )

    with pytest.raises(ScheduleRetry) as exc_info:
        tp.create_and_update_protected_area_tileset(
            bucket="bkt",
            source_file="pas.geojson",
            tileset_file="pas.mbtiles",
            tileset_id="pas.id",
            display_name="Protected Areas",
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
            "EXTRA1": [999],
            "EXTRA2": ["dropme"],
        },
        geometry=[Point(0, 0)],
        crs="EPSG:4326",
    )

    out = tp.protected_area_process(gdf.copy(), {"verbose": False})
    expected = {"GIS_AREA", "NAME", "PA_DEF", "ISO3", "WDPAID", "geometry"}
    assert set(out.columns) == expected
