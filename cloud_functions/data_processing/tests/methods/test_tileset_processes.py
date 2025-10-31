import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

import src.methods.tileset_processes as tp


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
            # Uses EEZ_TOLERANCE constant; we will monkeypatch it to 5 in test.
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
            "_5.geojson",  # uses EEZ_TOLERANCE for suffix as well
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
            "_7.geojson",  # will monkeypatch COUNTRIES_TOLERANCE=7
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
            "_7.geojson",  # reuses COUNTRIES_TOLERANCE
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
            },
            "pas.id.geojson",
            "_3.2.geojson",
            tp.protected_area_process,
        ),
    ],
)
def test_wrappers_call_pipeline_with_expected_config(
    which, kwargs, expected_local_geojson, expected_source_suffix, expected_process, monkeypatch
):
    """
    Ensure each wrapper function forwards a TilesetConfig with the expected
    derived fields and the correct process function to run_tileset_pipeline.
    """

    calls = {}

    def mock_run_tileset_pipeline(cfg, *, process):
        # capture cfg & process for assertions
        calls["cfg"] = cfg
        calls["process"] = process
        print(cfg)
        # return a simple shape the wrappers would propagate
        return {"tileset_id": cfg.tileset_id, "gcs_blob": cfg.tileset_blob_name}

    # Monkeypatch constants used by wrappers that don't receive them as params
    monkeypatch.setattr(tp, "EEZ_TOLERANCE", 5, raising=True)
    monkeypatch.setattr(tp, "COUNTRIES_TOLERANCE", 7, raising=True)
    monkeypatch.setattr(tp, "run_tileset_pipeline", mock_run_tileset_pipeline, raising=True)

    # Invoke the appropriate wrapper
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
    else:
        raise AssertionError("Unknown case")

    cfg = calls["cfg"]
    proc = calls["process"]

    assert proc is expected_process, "Expected the correct process hook to be passed"
    assert cfg.local_geojson_name == expected_local_geojson
    assert cfg.source_file.endswith(expected_source_suffix), (
        "Source file suffix should include tolerance"
    )
    assert cfg.tileset_blob_name == kwargs["tileset_file"]
    assert cfg.bucket == kwargs["bucket"]


def test_eez_process_drops_expected_columns(mock_gdf):
    gdf = mock_gdf.copy()

    # add columns that should be dropped if present
    gdf["MRGID"] = [1, 2, 3]
    gdf["AREA_KM2"] = [10.0, 20.0, 30.0]

    out = tp.eez_process(gdf, {"verbose": False})
    assert "MRGID" not in out.columns
    assert "AREA_KM2" not in out.columns

    assert {"location", "geometry"} <= set(out.columns)


def test_marine_regions_process(monkeypatch):
    """
    Asserts that:
      - region_id is computed from mapping
      - dissolve reduces to one row per region_id
      - known columns are dropped
      - translations are applied then 'code' dropped
    """
    # Input gdf with locations mapping to two regions
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
        tp,
        "read_json_from_gcs",
        lambda bucket, path, verbose=False: {"NA": ["USA", "CAM"], "AF": ["ANG"]},
        raising=True,
    )

    monkeypatch.setattr(
        tp, "read_dataframe", lambda bucket, path, verbose=False: pd.DataFrame(), raising=True
    )
    monkeypatch.setattr(tp, "add_translations", mock_add_translations, raising=True)

    result = tp.marine_regions_process(
        gdf,
        {"verbose": False, "bucket": "b", "translation_file": "t.csv", "regions_file": "r.json"},
    )

    # Should have one row per region_id
    assert set(result["region_id"]) == {"NA", "AF"}
    for col in ["MRGID", "AREA_KM2", "has_shared_marine_area", "index", "code", "location"]:
        assert col not in result.columns

    assert "geometry" in result.columns


def test_countries_process(monkeypatch):
    """
    Asserts:
      - ISO_SOV1..3 are created from related_countries mapping
      - translations applied then 'code' dropped
      - string dtype in ISO_SOV* columns with <NA> for missing
    """
    gdf = gpd.GeoDataFrame(
        {"location": ["GBR", "USA", "GGY", "FOO"]},
        geometry=[Point(0, 0), Point(1, 1), Point(2, 2), Point(1, 2)],
        crs="EPSG:4326",
    )

    related = {"GBR*": ["GBR", "FOO"], "USA*": ["USA", "FOO"], "GGY": ["GGY"]}
    monkeypatch.setattr(
        tp, "read_json_from_gcs", lambda bucket, path, verbose=False: related, raising=True
    )

    monkeypatch.setattr(
        tp, "read_dataframe", lambda bucket, path, verbose=False: pd.DataFrame(), raising=True
    )
    monkeypatch.setattr(tp, "add_translations", mock_add_translations, raising=True)

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

    # Values per our mapping
    row_gbr = result.loc[result["location"] == "GBR"].iloc[0]
    assert row_gbr["ISO_SOV1"] == "GBR*"
    assert pd.isna(row_gbr["ISO_SOV2"])
    assert pd.isna(row_gbr["ISO_SOV3"])

    row_usa = result.loc[result["location"] == "USA"].iloc[0]
    assert row_usa["ISO_SOV1"] == "USA*"
    assert pd.isna(row_usa["ISO_SOV2"])
    assert pd.isna(row_usa["ISO_SOV3"])

    row_foo = result.loc[result["location"] == "FOO"].iloc[0]
    assert row_foo["ISO_SOV1"] in ["GBR*", "USA*"]
    assert row_foo["ISO_SOV2"] in ["GBR*", "USA*"]
    assert pd.isna(row_foo["ISO_SOV3"])

    row_ggy = result.loc[result["location"] == "GGY"].iloc[0]
    assert pd.isna(row_ggy["ISO_SOV1"])

    assert "code" not in result.columns
    assert "geometry" in result.columns


def test_terrestrial_regions_process(monkeypatch):
    """
    Asserts:
      - region_id from mapping
      - dissolve reduces rows to unique region_id
      - 'location' dropped
      - translations applied then 'code' dropped
    """
    gdf = gpd.GeoDataFrame(
        {"location": ["A", "B", "A"]},
        geometry=[Point(0, 0), Point(1, 1), Point(0, 2)],
        crs="EPSG:4326",
    )

    monkeypatch.setattr(
        tp,
        "read_json_from_gcs",
        lambda bucket, path, verbose=False: {"R1": ["A"], "R2": ["B"]},
        raising=True,
    )

    monkeypatch.setattr(
        tp, "read_dataframe", lambda bucket, path, verbose=False: pd.DataFrame(), raising=True
    )
    monkeypatch.setattr(tp, "add_translations", mock_add_translations, raising=True)

    result = tp.terrestrial_regions_process(
        gdf.copy(),
        {"verbose": False, "bucket": "b", "regions_file": "r.json", "translation_file": "t.csv"},
    )

    assert set(result["region_id"]) == {"R1", "R2"}
    assert "location" not in result.columns
    assert "code" not in result.columns
    assert "geometry" in result.columns


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
