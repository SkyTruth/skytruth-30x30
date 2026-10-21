import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

import src.methods.generate_static_tables as gen_static_tbl


# Fixtures to stub in data
@pytest.fixture
def crs():
    return "EPSG:4326"


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
def mock_iho_seas_gdf(crs):
    """
    Minimal bodies of water frame
    """
    return gpd.GeoDataFrame(
        {
            "NAME": ["Gulf of Mexico", "Caribbean Sea"],
            "ID": ["26", "27"],
            "Longitude": ["-90.37958525236", "-74.67801130419"],
            "Latitude": ["24.94231562654", "15.31030445709"],
            "min_X": ["-98.05392181844", "-89.41292977359"],
            "min_Y": ["17.40680801848", "7.70979893208"],
            "max_X": ["-80.43304073784", "-59.42160093753"],
            "max_Y": ["31.46484375034", "22.70652472953"],
            "area": ["1566759", "2852792"],
            "MRGID": ["4288", "4287"],
            "geometry": [
                Point(-90.37958525236, 24.94231562654).buffer(2.0),
                Point(-74.67801130419, 15.31030445709).buffer(1.5),
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
def mock_national_targets_df():
    """
    Minimal national targets table keyed by location code. Values are strings and blanks are
    empty strings, matching how read_dataframe parses a CSV with keep_default_na=False.
    """
    return pd.DataFrame(
        {
            "Iso Code": ["USA", "MEX", "ZZZ", "FRA", "CAN"],
            "% Marine Target": ["30", "50", "30", "", "60"],
            "Marine By Year": ["2030", "2025", "2030", "", "2040"],
            "Marine Confidence": ["High", "High", "High", "High", "Low"],
            "% Terrestrial Target": ["30", "", "30", "30", "30"],
            "Terrestrial By Year": ["2030", "", "2030", "2030", "2030"],
            "Terrestrial Confidence": ["High", "High", "High", "High", "High"],
            "ORT Record": ["CBD NBSAP", "", "CBD NBSAP", "CBD NBSAP", "CBD NBSAP"],
        }
    )


@pytest.fixture
def mock_mpatlas_country_targets():
    """
    Minimal MPAtlas country-level API payload. Rows without a thirty_by_thirty_target are
    dropped, and MPAtlas publishes marine targets only.
    """
    return [
        {
            "id": "USA",
            "thirty_by_thirty_target": True,
            "national_target": 10,
            "fully_highly_target": None,
            "target_year": 2020,
            "pledge": "Ocean Panel",
        },
        {
            "id": "CAN",
            "thirty_by_thirty_target": True,
            "national_target": 30,
            "fully_highly_target": None,
            "target_year": 2030,
            "pledge": "Ocean Panel",
        },
        {
            "id": "JPN",
            "thirty_by_thirty_target": True,
            "national_target": 30,
            "fully_highly_target": None,
            "target_year": 2030,
            "pledge": "High Ambition Coalition",
        },
        {
            "id": "BRA",
            "thirty_by_thirty_target": None,
            "national_target": 25,
            "fully_highly_target": None,
            "target_year": 2030,
            "pledge": "Ocean Panel",
        },
    ]


@pytest.fixture
def mock_requests_get(monkeypatch, mock_mpatlas_country_targets):
    """Patch the MPAtlas API call so no test reaches the network."""

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return mock_mpatlas_country_targets

    monkeypatch.setattr(
        gen_static_tbl.requests, "get", lambda *args, **kwargs: _Response(), raising=True
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
def _mock_read_json_df(mock_eez_by_loc_gdf, mock_gadm_gdf, eez_suffix, gadm_suffix):
    """
    Return the right GeoDataFrame based on the filename the function asks for.
    We detect which one by the suffix (tolerance is part of the suffix).
    """

    def _read_json_df(*, bucket_name, filename, verbose=True):
        if filename.endswith(eez_suffix):
            return mock_eez_by_loc_gdf.copy()
        if filename.endswith(gadm_suffix):
            return mock_gadm_gdf.copy()
        raise AssertionError(f"Unexpected filename: {filename}")

    return _read_json_df


def _mock_load_iho_regions(mock_iho_seas_gdf):
    """
    Return the IHO Seas GeoDataFrame
    """

    def _load_iho_regions():
        return mock_iho_seas_gdf.copy()

    return _load_iho_regions


def _mock_read_json_from_gcs(mock_related_countries_map, mock_regions_map):
    def _reader(*, bucket_name, filename, verbose=True):
        if filename == gen_static_tbl.RELATED_COUNTRIES_FILE_NAME:
            return mock_related_countries_map
        if filename == gen_static_tbl.REGIONS_FILE_NAME:
            return mock_regions_map
        raise AssertionError(f"Unexpected JSON filename: {filename}")

    return _reader


def _mock_read_dataframe(mock_locs_translations_df, mock_national_targets_df):
    def _reader(*, bucket_name, filename, verbose=True):
        if filename == gen_static_tbl.LOCATIONS_TRANSLATED_FILE_NAME:
            return mock_locs_translations_df.copy()
        if filename == gen_static_tbl.NATIONAL_TARGETS_FILE_NAME:
            return mock_national_targets_df.copy()
        raise AssertionError(f"Unexpected CSV filename: {filename}")

    return _reader


def test__as_list_happy_cases():
    assert gen_static_tbl._as_list([1, 2]) == [1, 2]
    assert gen_static_tbl._as_list(None) == []
    assert gen_static_tbl._as_list(float("nan")) == []
    assert gen_static_tbl._as_list("USA") == ["USA"]


def test__add_default_types():
    assert gen_static_tbl._add_default_types({"location": "USA"}) == "country"
    assert gen_static_tbl._add_default_types({"location": "ABNJ"}) == "highseas"


def test__add_translations_adds_names_and_keeps_code_column(mock_locs_translations_df):
    out = gen_static_tbl._add_translations(
        gpd.GeoDataFrame({"GID_0": ["USA", "MEX"]}), mock_locs_translations_df
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


def test_process_national_targets_prefers_cbd_and_falls_back_to_mpatlas(
    monkeypatch, mock_locs_translations_df, mock_national_targets_df, mock_requests_get
):
    monkeypatch.setattr(
        gen_static_tbl,
        "read_dataframe",
        _mock_read_dataframe(mock_locs_translations_df, mock_national_targets_df),
        raising=True,
    )

    out = gen_static_tbl.process_national_targets(bucket="test-bucket", verbose=False).set_index(
        "code"
    )

    assert all(str(out[col].dtype) == "Int64" for col in out.columns if col.endswith("target"))
    assert all(str(out[col].dtype) == "Int64" for col in out.columns if col.endswith("year"))

    # CBD wins where it has a value, even though MPAtlas also publishes one for USA
    assert (out.loc["USA", "marine_target"], out.loc["USA", "marine_target_year"]) == (30, 2030)

    # MPAtlas fills locations the CBD file does not cover
    assert (out.loc["JPN", "marine_target"], out.loc["JPN", "marine_target_year"]) == (30, 2030)

    # A low confidence CBD marine target is discarded, so MPAtlas fills it instead
    assert (out.loc["CAN", "marine_target"], out.loc["CAN", "marine_target_year"]) == (30, 2030)

    # MPAtlas is marine only, so its locations have no terrestrial target
    assert pd.isna(out.loc["JPN", "terrestrial_target"])

    # Rows without a thirty_by_thirty_target are dropped from the MPAtlas side
    assert "BRA" not in out.index

    # Each resolved marine target names the dataset it came from
    assert out.loc["USA", "marine_target_source"] == "CBD"
    assert out.loc["JPN", "marine_target_source"] == "MPAtlas"
    assert out.loc["CAN", "marine_target_source"] == "MPAtlas"

    # The backing record is kept as text rather than coerced away with the numeric columns
    assert out.loc["USA", "pledge_or_ort_record"] == "CBD NBSAP"
    assert out.loc["JPN", "pledge_or_ort_record"] == "High Ambition Coalition"

    # A blank record in the CBD file falls back to MPAtlas like any other value
    assert pd.isna(out.loc["MEX", "pledge_or_ort_record"])

    # A location neither source gives a marine target to has a terrestrial target but no source
    assert pd.isna(out.loc["FRA", "marine_target"])
    assert pd.isna(out.loc["FRA", "marine_target_source"])
    assert out.loc["FRA", "terrestrial_target"] == 30


def test_generate_locations_table_happy(
    monkeypatch,
    mock_eez_by_loc_gdf,
    mock_gadm_gdf,
    mock_iho_seas_gdf,
    mock_related_countries_map,
    mock_regions_map,
    mock_locs_translations_df,
    mock_national_targets_df,
    mock_requests_get,
    upload_recorder,
):
    calls, upload_mock = upload_recorder

    # Fix the tolerance so the code resolves eez/gadm filenames deterministically
    tolerance = 0.1

    # The filenames the function will compute internally
    eez_suffix = gen_static_tbl.EEZ_FILE_NAME.replace(".geojson", "_0.1.geojson")
    gadm_suffix = gen_static_tbl.GADM_FILE_NAME.replace(".geojson", "_0.1.geojson")

    # Patch I/O internal bu imported helpers
    monkeypatch.setattr(
        gen_static_tbl,
        "read_json_df",
        _mock_read_json_df(mock_eez_by_loc_gdf, mock_gadm_gdf, eez_suffix, gadm_suffix),
        raising=True,
    )
    monkeypatch.setattr(
        gen_static_tbl,
        "load_iho_regions",
        _mock_load_iho_regions(mock_iho_seas_gdf),
        raising=True,
    )
    monkeypatch.setattr(
        gen_static_tbl,
        "read_json_from_gcs",
        _mock_read_json_from_gcs(mock_related_countries_map, mock_regions_map),
        raising=True,
    )
    monkeypatch.setattr(
        gen_static_tbl,
        "read_dataframe",
        _mock_read_dataframe(mock_locs_translations_df, mock_national_targets_df),
        raising=True,
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
        tolerance=tolerance,
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

    # Make sure Gulf of Mexico IHO Sea Area made it in
    assert (
        (df["name"] == "Gulf of Mexico")
        & (df["code"].astype(str) == "4288")
        & (df["type"] == "sea")
    ).any()

    # National targets merged on code and cast to nullable integers
    target_cols = [
        "marine_target",
        "marine_target_year",
        "terrestrial_target",
        "terrestrial_target_year",
    ]
    assert set(target_cols).issubset(df.columns)
    assert all(str(df[col].dtype) == "Int64" for col in target_cols)

    usa = df[df["code"] == "USA"].iloc[0]
    assert (usa["marine_target"], usa["marine_target_year"]) == (30, 2030)
    assert (usa["terrestrial_target"], usa["terrestrial_target_year"]) == (30, 2030)

    # Blank cells stay missing rather than becoming zeros
    mex = df[df["code"] == "MEX"].iloc[0]
    assert (mex["marine_target"], mex["marine_target_year"]) == (50, 2025)
    assert pd.isna(mex["terrestrial_target"])
    assert pd.isna(mex["terrestrial_target_year"])

    # Locations absent from the targets file are left unset
    assert pd.isna(df.loc[df["code"].astype(str) == "4288", "marine_target"].iloc[0])

    # A target for an unknown code does not add a location
    assert "ZZZ" not in set(df["code"].astype(str))

    # The source of each marine target travels with it into the locations table
    assert usa["marine_target_source"] == "CBD"
    assert pd.isna(df.loc[df["code"].astype(str) == "4288", "marine_target_source"].iloc[0])


def test_generate_locations_table_read_failure(
    monkeypatch,
    mock_gadm_gdf,
    mock_iho_seas_gdf,
    mock_related_countries_map,
    mock_regions_map,
    mock_locs_translations_df,
    mock_national_targets_df,
    mock_requests_get,
    upload_recorder,
):
    calls, upload_mock = upload_recorder

    tolerance = 0.1

    eez_suffix = gen_static_tbl.EEZ_FILE_NAME.replace(".geojson", "_0.1.geojson")

    # Fail when attempting to load the EEZ file
    def failing_read_json_df(*, bucket_name, filename, verbose=True):
        if filename.endswith(eez_suffix):
            raise RuntimeError("EEZ load failed")
        return mock_gadm_gdf.copy()

    monkeypatch.setattr(gen_static_tbl, "read_json_df", failing_read_json_df, raising=True)
    # Stubbed even though the EEZ read fails first, so a reordering can't reach the network.
    monkeypatch.setattr(
        gen_static_tbl,
        "load_iho_regions",
        _mock_load_iho_regions(mock_iho_seas_gdf),
        raising=True,
    )
    monkeypatch.setattr(
        gen_static_tbl,
        "read_json_from_gcs",
        _mock_read_json_from_gcs(mock_related_countries_map, mock_regions_map),
        raising=True,
    )
    monkeypatch.setattr(
        gen_static_tbl,
        "read_dataframe",
        _mock_read_dataframe(mock_locs_translations_df, mock_national_targets_df),
        raising=True,
    )
    monkeypatch.setattr(gen_static_tbl, "upload_dataframe", upload_mock, raising=True)
    monkeypatch.setattr(gen_static_tbl, "get_area_km2", lambda geom: 1.0, raising=True)
    monkeypatch.setattr(gen_static_tbl, "round_to_list", lambda s: list(s), raising=True)

    with pytest.raises(RuntimeError, match="EEZ load failed"):
        gen_static_tbl.generate_locations_table(
            bucket="test-bucket", tolerance=tolerance, verbose=False
        )

    assert calls == []
