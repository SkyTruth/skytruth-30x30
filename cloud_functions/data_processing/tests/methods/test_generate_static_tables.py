import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, Polygon

import src.methods.generate_static_tables as gen_static_tbl


# Fixtures to stub in data
@pytest.fixture
def crs():
    return "EPSG:4326"


@pytest.fixture
def mock_eez_gdf(crs):
    """
    Minimal EEZ-like frame
    """
    return gpd.GeoDataFrame(
        {
            "location": ["USA", "MEX", "ABNJ"],
            "AREA_KM2": ["1000.4", "499.6", "123.1"],  # strings on purpose
            "has_shared_marine_area": [True, None, False],
            "geometry": [
                Point(-100, 35).buffer(3.0),
                Point(-102, 18).buffer(2.0),
                Polygon([(-10, -10), (-10, 10), (10, 10), (10, -10)]),
            ],
        },
        crs=crs,
    )


@pytest.fixture
def mock_gadm_gdf(crs):
    """
    Minimal terrestrial frame
    """
    return gpd.GeoDataFrame(
        {
            "location": ["USA", "MEX"],
            "COUNTRY": ["United States", "Mexico"],
            "geometry": [
                Point(-100, 40).buffer(2.0),
                Point(-102, 22).buffer(1.5),
            ],
        },
        crs=crs,
    )


@pytest.fixture
def mock_related_countries_map():
    """
    Minimal related_countries mock
    """
    return {
        "USA*": ["USA", "PRI"],
        "MEX*": ["MEX"],
        "USA": ["USA"],
    }


@pytest.fixture
def mock_regions_map():
    """
    Minimal regions map mock
    """
    return {
        "NA": ["USA", "MEX"],  # North America region
    }


@pytest.fixture
def mock_translations_df():
    """Minimal translations table to be merged at the end."""
    return pd.DataFrame(
        {
            "code": ["USA", "MEX", "ABNJ", "NA", "USA*", "MEX*"],
            "name": [
                "United States",
                "Mexico",
                "High Seas",
                "North America",
                "United States*",
                "Mexico*",
            ],
            "name_es": [
                "Estados Unidos",
                "México",
                "Alta mar",
                "Norteamérica",
                "Estados Unidos*",
                "México*",
            ],
            "name_fr": [
                "États-Unis",
                "Mexique",
                "Haute mer",
                "Amérique du Nord",
                "États-Unis*",
                "Mexique*",
            ],
            "name_pt": [
                "Estados Unidos",
                "México",
                "Alto-mar",
                "América do Norte",
                "Estados Unidos*",
                "México*",
            ],
        }
    )


@pytest.fixture
def upload_recorder():
    """
    Record uploads so tests can assert the target blob name and the resulting dataframe shape.
    """
    calls = []

    def _upload_dataframe(*, bucket_name, df, destination_blob_name, **_):
        assert isinstance(df, (pd.DataFrame, gpd.GeoDataFrame))
        calls.append(
            {
                "bucket_name": bucket_name,
                "destination_blob_name": destination_blob_name,
                "df": df.copy(),
            }
        )

    return calls, _upload_dataframe


# Mocks to patch in for functions and pas the fixtures
def _mock_read_json_df(mock_eez_gdf, mock_gadm_gdf, eez_suffix, gadm_suffix):
    """
    Return the right GeoDataFrame based on the filename the function asks for.
    We detect which one by the suffix (tolerance is part of the suffix).
    """

    def _read_json_df(*, bucket_name, filename, verbose=True):
        if filename.endswith(eez_suffix):
            return mock_eez_gdf.copy()
        if filename.endswith(gadm_suffix):
            return mock_gadm_gdf.copy()
        raise AssertionError(f"Unexpected filename: {filename}")

    return _read_json_df


def _mock_read_json_from_gcs(mock_related_countries_map, mock_regions_map):
    def _reader(*, bucket_name, filename, verbose=True):
        if filename == gen_static_tbl.RELATED_COUNTRIES_FILE_NAME:
            return mock_related_countries_map
        if filename == gen_static_tbl.REGIONS_FILE_NAME:
            return mock_regions_map
        raise AssertionError(f"Unexpected JSON filename: {filename}")

    return _reader


def _mock_read_dataframe(mock_translations_df):
    def _reader(*, bucket_name, filename, verbose=True):
        assert filename == gen_static_tbl.LOCATIONS_TRANSLATED_FILE_NAME
        return mock_translations_df.copy()

    return _reader


def test__as_list_happy_cases():
    assert gen_static_tbl._as_list([1, 2]) == [1, 2]
    assert gen_static_tbl._as_list(None) == []
    assert gen_static_tbl._as_list(float("nan")) == []
    assert gen_static_tbl._as_list("USA") == ["USA"]


def test__add_default_types():
    assert gen_static_tbl._add_default_types({"location": "USA"}) == "country"
    assert gen_static_tbl._add_default_types({"location": "ABNJ"}) == "highseas"


def test__add_translations_adds_names_and_keeps_code_column(mock_translations_df):
    out = gen_static_tbl._add_translations(
        gpd.GeoDataFrame({"GID_0": ["USA", "MEX"]}), mock_translations_df
    )

    assert "code" in out.columns
    assert {"name", "name_es", "name_fr", "name_pt"}.issubset(out.columns)
    assert set(out["code"]) == {"USA", "MEX"}


def test__add_groups_creates_group_rows_and_updates_member_lists(crs):
    base = gpd.GeoDataFrame(
        {
            "GID_0": ["ABC", "DEF", "HIG"],
            "geometry": [Point(0, 0).buffer(1), Point(2, 0).buffer(1), Point(4, 0).buffer(1)],
        },
        crs=crs,
    )
    groups = {"AF": ["ABC", "DEF"], "SA": ["HIG"]}

    out = gen_static_tbl._add_groups(base, groups, "region")

    assert {"AF", "SA"}.issubset(set(out["GID_0"]))

    row_af = out[out["GID_0"] == "AF"].iloc[0]
    assert row_af["type"] == "region"
    assert row_af["members"] == ["ABC", "DEF"]
    assert row_af.geometry is not None

    # Member rows received 'groups' lists with the region code
    assert out.loc[out["GID_0"] == "ABC", "groups"].iloc[0] == ["AF"]
    assert out.loc[out["GID_0"] == "HIG", "groups"].iloc[0] == ["SA"]


def test_generate_locations_table_happy(
    monkeypatch,
    mock_eez_gdf,
    mock_gadm_gdf,
    mock_related_countries_map,
    mock_regions_map,
    mock_translations_df,
    upload_recorder,
):
    calls, upload_mock = upload_recorder

    # Fix tolerances so the code resolves eez/gadm filenames deterministically
    monkeypatch.setattr(gen_static_tbl, "marine_tolerance", 0.1, raising=True)
    monkeypatch.setattr(gen_static_tbl, "terrestrial_tolerance", 0.2, raising=True)

    # The filenames the function will compute internally
    eez_suffix = gen_static_tbl.EEZ_FILE_NAME.replace(".geojson", "_0.1.geojson")
    gadm_suffix = gen_static_tbl.GADM_FILE_NAME.replace(".geojson", "_0.2.geojson")

    # Patch I/O internal bu imported helpers
    monkeypatch.setattr(
        gen_static_tbl,
        "read_json_df",
        _mock_read_json_df(mock_eez_gdf, mock_gadm_gdf, eez_suffix, gadm_suffix),
        raising=True,
    )
    monkeypatch.setattr(
        gen_static_tbl,
        "read_json_from_gcs",
        _mock_read_json_from_gcs(mock_related_countries_map, mock_regions_map),
        raising=True,
    )
    monkeypatch.setattr(
        gen_static_tbl, "read_dataframe", _mock_read_dataframe(mock_translations_df), raising=True
    )
    monkeypatch.setattr(gen_static_tbl, "upload_dataframe", upload_mock, raising=True)

    # Patch the helpers that do work with geometries to keep it fast and deterministic
    monkeypatch.setattr(
        gen_static_tbl, "get_area_km2", lambda geom: 123.4, raising=True
    )  # -> rounds to 123
    monkeypatch.setattr(
        gen_static_tbl, "round_to_list", lambda s: [round(x, 5) for x in s], raising=True
    )

    gen_static_tbl.generate_locations_table(
        output_file_name="locations.csv",
        bucket="test-bucket",
        verbose=False,
    )

    assert len(calls) == 1
    uploaded = calls[0]
    assert uploaded["bucket_name"] == "test-bucket"
    assert uploaded["destination_blob_name"] == "locations.csv"

    df = uploaded["df"]

    assert {"code", "name", "name_es", "name_fr", "name_pt"}.issubset(df.columns)
    assert {
        "marine_bounds",
        "terrestrial_bounds",
        "total_marine_area",
        "total_terrestrial_area",
        "has_shared_marine_area",
    }.issubset(df.columns)

    # Totals were rounded and cast to nullable integers
    assert str(df["total_terrestrial_area"].dtype) == "Int64"
    assert str(df["total_marine_area"].dtype) == "Int64"

    # Required fields that are present in eez and not gadm so could get lost after merger
    assert df["total_marine_area"].isna().sum() == 0
    assert df["has_shared_marine_area"].isna().sum() == 0

    # make sure regions and soverign roll ups made it in
    assert any(code in set(df["code"].astype(str)) for code in ["NA", "USA*", "MEX*"])


def test_generate_locations_table_read_failure(
    monkeypatch,
    mock_gadm_gdf,
    mock_related_countries_map,
    mock_regions_map,
    mock_translations_df,
    upload_recorder,
):
    calls, upload_mock = upload_recorder

    monkeypatch.setattr(gen_static_tbl, "marine_tolerance", 0.1, raising=True)
    monkeypatch.setattr(gen_static_tbl, "terrestrial_tolerance", 0.2, raising=True)

    eez_suffix = gen_static_tbl.EEZ_FILE_NAME.replace(".geojson", "_0.1.geojson")

    # Fail when attempting to load the EEZ file
    def failing_read_json_df(*, bucket_name, filename, verbose=True):
        if filename.endswith(eez_suffix):
            raise RuntimeError("EEZ load failed")
        return mock_gadm_gdf.copy()

    monkeypatch.setattr(gen_static_tbl, "read_json_df", failing_read_json_df, raising=True)
    monkeypatch.setattr(
        gen_static_tbl,
        "read_json_from_gcs",
        _mock_read_json_from_gcs(mock_related_countries_map, mock_regions_map),
        raising=True,
    )
    monkeypatch.setattr(
        gen_static_tbl, "read_dataframe", _mock_read_dataframe(mock_translations_df), raising=True
    )
    monkeypatch.setattr(gen_static_tbl, "upload_dataframe", upload_mock, raising=True)
    monkeypatch.setattr(gen_static_tbl, "get_area_km2", lambda geom: 1.0, raising=True)
    monkeypatch.setattr(gen_static_tbl, "round_to_list", lambda s: list(s), raising=True)

    with pytest.raises(RuntimeError, match="EEZ load failed"):
        gen_static_tbl.generate_locations_table(bucket="test-bucket", verbose=False)

    assert calls == []
