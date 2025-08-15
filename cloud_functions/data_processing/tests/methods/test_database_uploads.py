import pandas as pd

import src.methods.database_uploads as db_uploads


def test_parse_list_or_na_empty_string():
    assert pd.isna(db_uploads._parse_list_or_na(""))


def test_parse_list_or_na_nan():
    assert pd.isna(db_uploads._parse_list_or_na(float("nan")))


def test_parse_list_or_na_stringified_list():
    assert db_uploads._parse_list_or_na("['A', 'B']") == ["A", "B"]


def test_parse_list_or_na_scalar_string_wrapped():
    # Not a list literal -> wrapped in a list
    assert db_uploads._parse_list_or_na('"ABC"') == ["ABC"]


def test_parse_list_or_na_malformed_returns_na():
    # Something not parseable as a Python literal should return NA
    assert pd.isna(db_uploads._parse_list_or_na("[unquoted, broken]"))


def test_extract_non_na_values_drops_nulls_keeps_lists():
    df = pd.DataFrame(
        {
            "code": [1, 2],
            "name": ["ok", None],
            "area": [pd.NA, 5],
            "groups": [["A", "B"], pd.NA],
        }
    )

    cleaned = db_uploads._extract_non_na_values(df)

    assert cleaned[0] == {"code": 1, "name": "ok", "groups": ["A", "B"]}
    assert cleaned[1] == {"code": 2, "area": 5}


def test_upload_locations_happy_path(monkeypatch):
    """
    - read_dataframe should be called with list-field converters
    - converters turn stringified lists into real lists and empty values into NA
    - payload passed to Strapi.upsert_locations has NA keys removed but list-typed values preserved
    """
    raw = pd.DataFrame(
        {
            "code": ["USA", "MEX", "ABNJ"],
            "name": ["United States", "Mexico", "High Seas"],
            # list-typed fields in CSV come back as strings (or blanks)
            "groups": ["['G1','G2']", "", "['OCE']"],
            "members": ["", "['M1']", "[]"],
            "terrestrial_bounds": ["[1.1, 2.2, 3.3, 4.4]", "", ""],
            "marine_bounds": ["", "", "[0.0, 0.0, 10.0, 10.0]"],
            "has_shared_marine_area": [True, pd.NA, False],
            "total_marine_area": [pd.NA, 1234, None],
        }
    )

    captured_kwargs = {}

    def _mock_read_dataframe(*, bucket_name, filename, **kwargs):
        captured_kwargs["bucket_name"] = bucket_name
        captured_kwargs["filename"] = filename
        captured_kwargs["converters"] = kwargs.get("converters")
        captured_kwargs["dtype"] = kwargs.get("dtype")

        converters = kwargs.get("converters")
        # apply the provided converters column-wise
        df = raw.copy()
        if converters:
            for col, fn in converters.items():
                if col in df.columns:
                    df[col] = df[col].map(fn)
        return df

    # Fake Strapi client that records what gets upserted
    class MockStrapi:
        def __init__(self):
            self.last_payload = None
            self.last_opts = None

        def upsert_locations(self, payload, options=None):
            self.last_payload = payload
            self.last_opts = options
            return {"ok": True, "len": len(payload)}

    mock_client = MockStrapi()

    monkeypatch.setattr(db_uploads, "read_dataframe", _mock_read_dataframe, raising=True)
    monkeypatch.setattr(db_uploads, "Strapi", lambda: mock_client, raising=True)

    options = {"snack": "cheese"}

    result = db_uploads.upload_locations(
        bucket="test-bucket", filename="locations.csv", request={"options": options}, verbose=False
    )

    assert captured_kwargs["bucket_name"] == "test-bucket"
    assert captured_kwargs["filename"] == "locations.csv"
    assert captured_kwargs["dtype"] == {"total_marine_area": "Int64"}

    # The function should request converters for these fields:
    for expected in ["groups", "members", "terrestrial_bounds", "marine_bounds"]:
        assert expected in captured_kwargs["converters"]

    assert result == {"ok": True, "len": 3}
    payload = mock_client.last_payload
    options = mock_client.last_opts
    assert isinstance(payload, list) and len(payload) == 3
    assert options == {"snack": "cheese"}

    # Row 0: lists parsed; NA keys removed
    row0 = payload[0]
    assert row0["code"] == "USA"
    assert row0["name"] == "United States"
    assert row0["groups"] == ["G1", "G2"]  # parsed list retained
    assert "members" not in row0  # empty -> NA -> dropped
    assert "marine_bounds" not in row0  # empty -> NA -> dropped
    assert row0["terrestrial_bounds"] == [1.1, 2.2, 3.3, 4.4]
    assert row0["has_shared_marine_area"] is True
    assert "total_marine_area" not in row0  # NA dropped

    # Row 1: groups NA dropped; members parsed and kept; total_marine_area kept
    row1 = payload[1]
    assert row1["code"] == "MEX"
    assert row1["members"] == ["M1"]
    assert "groups" not in row1
    assert row1["total_marine_area"] == 1234
    assert "has_shared_marine_area" not in row1

    # Row 2: both lists parsed/kept where provided
    row2 = payload[2]
    assert row2["code"] == "ABNJ"
    assert row2["groups"] == ["OCE"]
    assert row2["marine_bounds"] == [0.0, 0.0, 10.0, 10.0]
    assert row2["members"] == []
