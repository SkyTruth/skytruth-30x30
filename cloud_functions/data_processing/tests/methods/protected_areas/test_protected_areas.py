from copy import deepcopy

import pandas as pd
import pytest

from src.methods.protected_areas.protected_areas import make_pa_updates


@pytest.fixture
def base_entry():
    """Baseline protected area entry for current_db."""
    return {
        "documentId": "doc-1",
        "name": "Bättelweid, Magerwiese",
        "area": 0.0130905404,
        "wdpaid": 555770001,
        "wdpa_p_id": "555770001",
        "zone_id": None,
        "designation": "National",
        "mpaa_establishment_stage": "",
        "location": "MEX",
        "mpaa_protection_level": "",
        "bbox": [8.47, 47.35, 8.47, 47.35],
        "year": 2023,
        "protection_status": "pa",
        "environment": "terrestrial",
        "data_source": "Protected Planet",
        "iucn_category": "Not Assigned",
        "coverage": 0.0,
        "parent": None,
        "children": None,
    }


@pytest.fixture
def parent():
    """Baseline parent PA"""
    return {
        "documentId": "doc-2",
        "name": "Balam Kin (A)",
        "area": 100,
        "wdpaid": 555783753,
        "wdpa_p_id": "555783753_A",
        "zone_id": None,
        "designation": "National",
        "location": "MEX",
        "environment": "terrestrial",
        "data_source": "Protected Planet",
        "protection_status": "pa",
        "year": 2023,
        "iucn_category": "VI",
        "coverage": 0.06,
        "parent": None,
        "children": [
            {
                "wdpaid": 555783753,
                "wdpa_p_id": "555783753_B",
                "zone_id": None,
                "environment": "terrestrial",
                "location": "MEX",
                "documentId": "doc-3",
            }
        ],
        "bbox": [-90.1, 18.8, -89.5, 19.2],
        "mpaa_establishment_stage": "",
        "mpaa_protection_level": "",
    }


@pytest.fixture
def child():
    """Baselione child PA"""
    return {
        "documentId": "doc-3",
        "name": "Balam Kin (B)",
        "area": 80,
        "wdpaid": 555783753,
        "wdpa_p_id": "555783753_B",
        "zone_id": None,
        "designation": "National",
        "location": "MEX",
        "environment": "terrestrial",
        "data_source": "Protected Planet",
        "protection_status": "pa",
        "year": 2023,
        "iucn_category": "Ia",
        "coverage": 0.04,
        "parent": {
            "wdpaid": 555783753,
            "wdpa_p_id": "555783753_A",
            "zone_id": None,
            "environment": "terrestrial",
            "location": "MEX",
            "documentId": "doc-2",
        },
        "children": None,
        "bbox": [-90.1, 18.8, -89.5, 19.2],
        "mpaa_establishment_stage": "",
        "mpaa_protection_level": "",
    }


def make_df(entries):
    """Helper to create a DataFrame from a list of dict entries."""
    return pd.DataFrame(entries)


def test_detect_new_entry(base_entry):
    """Detects when a new record (not in current_db) is present in updated_pas."""
    current_db = make_df([base_entry])

    new_entry = deepcopy(base_entry)
    new_entry["wdpaid"] = 999
    new_entry["wdpa_p_id"] = "999"
    new_entry.pop("documentId", None)  # updated_pas should not have documentId

    updated_pas = make_df([{k: v for k, v in base_entry.items() if k != "documentId"}, new_entry])

    result = make_pa_updates(current_db, updated_pas, verbose=False)[0]

    assert len(result["deleted"]) == 0
    assert len(result["changed"]) == 0
    assert len(result["new"]) == 1

    assert result["new"][0].get("documentId") is None
    assert result["new"][0]["wdpaid"] == 999


def test_detect_deleted_entry(base_entry):
    """Detects when a record in current_db is missing from updated_pas."""
    current_db = make_df([base_entry])

    updated_pas = pd.DataFrame(columns=[c for c in current_db.columns if c != "documentId"])

    result = make_pa_updates(current_db, updated_pas, verbose=False)[0]

    assert result["deleted"] == ["doc-1"]
    assert len(result["deleted"]) == 1
    assert len(result["new"]) == 0
    assert len(result["changed"]) == 0


def test_detect_changed_string(base_entry):
    """Detects when a string field (e.g. designation) changes."""
    current_db = make_df([base_entry])
    updated_entry = deepcopy(base_entry)
    updated_entry["designation"] = "International"
    updated_entry.pop("documentId", None)

    updated_pas = make_df([updated_entry])

    result = make_pa_updates(current_db, updated_pas, verbose=False)[0]

    assert len(result["changed"]) == 1
    assert len(result["deleted"]) == 0
    assert len(result["new"]) == 0

    assert result["changed"][0]["designation"] == "International"
    assert result["changed"][0]["documentId"] == base_entry.get("documentId")


def test_detect_changed_area_large(base_entry):
    """
    Happy path test when the area value changes by more than 1% is dected and rounds to 2 decimals.
    """
    current_db = make_df([base_entry])
    updated_entry = deepcopy(base_entry)

    updated_entry["area"] = base_entry["area"] * 1.2
    updated_entry.pop("documentId", None)

    updated_pas = make_df([updated_entry])

    result = make_pa_updates(current_db, updated_pas, verbose=False)[0]

    assert len(result["changed"]) == 1
    assert len(result["deleted"]) == 0
    assert len(result["new"]) == 0

    assert result["changed"][0]["area"] == round(updated_entry["area"], 2)
    assert result["changed"][0]["documentId"] == base_entry.get("documentId")


def test_ignore_small_area_change(base_entry):
    """Ignores area changes smaller than or equal to 1%."""
    current_db = make_df([base_entry])
    updated_entry = deepcopy(base_entry)

    # Using slightly under limit to prevent false failures with floating point percision rounding
    updated_entry["area"] = base_entry["area"] * 1.009
    updated_entry.pop("documentId", None)
    updated_pas = make_df([updated_entry])

    result = make_pa_updates(current_db, updated_pas, verbose=False)[0]

    assert len(result["changed"]) == 0
    assert len(result["deleted"]) == 0
    assert len(result["new"]) == 0


def test_detect_changed_parent(base_entry):
    """Detects when the parent field changes from None to a dict."""
    current_db = make_df([base_entry])
    updated_entry = deepcopy(base_entry)
    updated_entry["parent"] = {
        "wdpaid": base_entry["wdpaid"],
        "wdpa_p_id": base_entry["wdpa_p_id"] + "_A",
        "zone_id": None,
        "environment": base_entry["environment"],
        "location": base_entry["location"],
        "documentId": None,
    }
    updated_entry.pop("documentId", None)

    updated_pas = make_df([updated_entry])
    result = make_pa_updates(current_db, updated_pas, verbose=False)[0]

    assert len(result["changed"]) == 1
    assert len(result["new"]) == 0
    assert len(result["deleted"]) == 0

    assert isinstance(result["changed"][0]["parent"], dict)
    assert result["changed"][0]["parent"] == updated_entry["parent"]


def test_detect_changed_children(base_entry):
    """Detects when the children field changes from None to a list of dicts."""
    current_db = make_df([base_entry])
    updated_entry = deepcopy(base_entry)
    updated_entry["children"] = [
        {
            "wdpaid": base_entry["wdpaid"],
            "wdpa_p_id": base_entry["wdpa_p_id"] + "_B",
            "zone_id": None,
            "environment": base_entry["environment"],
            "location": base_entry["location"],
            "documentId": None,
        }
    ]
    updated_entry.pop("documentId", None)

    updated_pas = make_df([updated_entry])

    result = make_pa_updates(current_db, updated_pas, verbose=False)[0]

    assert len(result["changed"]) == 1
    assert len(result["new"]) == 0
    assert len(result["deleted"]) == 0

    assert isinstance(result["changed"][0]["children"], list)
    assert result["changed"][0]["children"] == updated_entry["children"]


def test_happy_path_no_change(parent, child):
    """
    Happy path test for PAs with shared parent and children relationships and no changes
    """

    current_db = make_df([parent, child])
    updated_pas = make_df(
        [
            {k: v for k, v in parent.items() if k != "documentId"},
            {k: v for k, v in child.items() if k != "documentId"},
        ]
    )

    result = make_pa_updates(current_db, updated_pas, verbose=False)[0]
    assert result["new"] == []
    assert result["deleted"] == []
    assert result["changed"] == []


def test_no_changes(base_entry):
    """Ensures no false positives when current_db and updated_pas match exactly."""
    current_db = make_df([base_entry])
    updated_entry = deepcopy(base_entry)
    updated_entry.pop("documentId", None)
    updated_pas = make_df([updated_entry])

    result = make_pa_updates(current_db, updated_pas, verbose=False)[0]
    assert result["new"] == []
    assert result["changed"] == []
    assert result["deleted"] == []


def test_new_entry_has_no_document_id(base_entry):
    """Ensure that new entries do not have a 'documentId' key in db_changes."""
    current_db = make_df([base_entry])

    new_entry = deepcopy(base_entry)
    new_entry["wdpaid"] = 999
    new_entry["wdpa_p_id"] = "999"
    new_entry.pop("documentId", None)

    updated_pas = make_df([{k: v for k, v in base_entry.items() if k != "documentId"}, new_entry])

    result = make_pa_updates(current_db, updated_pas, verbose=False)[0]
    new_record = result["new"][0]
    assert "documentId" not in new_record

    assert len(result["changed"]) == 0
    assert len(result["deleted"]) == 0


def test_existing_entry_keeps_document_id(base_entry):
    """Ensure that unchanged or changed entries keep their documentId from current_db."""
    current_db = make_df([base_entry])
    updated_entry = deepcopy(base_entry)
    updated_entry["designation"] = "International"
    updated_entry.pop("documentId", None)

    updated_pas = make_df([updated_entry])
    result = make_pa_updates(current_db, updated_pas, verbose=False)[0]
    changed_record = result["changed"][0]
    assert changed_record["documentId"] == base_entry["documentId"]


def test_new_child_has_no_document_id(base_entry):
    """Ensure that a brand new child entry has documentId=None (explicitly present)."""
    current_db = make_df([base_entry])
    updated_entry = deepcopy(base_entry)
    updated_entry["children"] = [
        {
            "wdpaid": base_entry["wdpaid"],
            "wdpa_p_id": base_entry["wdpa_p_id"] + "_B",
            "zone_id": None,
            "environment": "terrestrial",
            "location": base_entry["location"],
            "documentId": None,
        }
    ]
    updated_entry.pop("documentId", None)

    updated_pas = make_df([updated_entry])
    result = make_pa_updates(current_db, updated_pas, verbose=False)[0]
    changed_record = result["changed"][0]

    assert len(result["changed"]) == 1
    assert len(result["new"]) == 0
    assert len(result["deleted"]) == 0

    assert changed_record["children"][0]["documentId"] is None
    assert changed_record["children"] == updated_entry["children"]


def test_multiple_children(base_entry, parent, child):
    """test the case where a PA has multiple children and a subset change"""
    updated_parent = deepcopy(parent)
    updated_parent.pop("documentId", None)
    updated_parent["children"][0].pop("documentId", None)

    updated_child = deepcopy(child)
    updated_child.pop("documentId", None)

    parent["children"].append(base_entry)
    current_db = make_df([parent, child])

    updated_pas = make_df([updated_parent, updated_child])
    result = make_pa_updates(current_db, updated_pas, verbose=False)[0]

    print("Result", result)

    assert len(result["changed"]) == 1
    assert len(result["new"]) == 0
    assert len(result["deleted"]) == 0

    assert len(result["changed"][0]["children"]) == 1
    assert result["changed"][0]["children"][0]["documentId"] == child["documentId"]


def test_pas_with_changed_deleted_new(base_entry, child, parent):
    """
    Happy path test for complex sample unchangewd, changed, new and deleted PAs'
    """
    second_entry = deepcopy(base_entry)
    second_entry["wdpaid"] = 2
    second_entry["documentId"] = "doc-200"

    third_entry = deepcopy(base_entry)
    third_entry["wdpaid"] = 3
    third_entry["documentId"] = "doc-300"

    fourth_entry = deepcopy(base_entry)
    fourth_entry["wdpaid"] = 4
    fourth_entry["documentId"] = "doc-400"

    unchanged_pa = deepcopy(base_entry)
    del unchanged_pa["documentId"]

    changed_pa = deepcopy(second_entry)
    del changed_pa["documentId"]
    changed_pa["area"] = second_entry["area"] * 2
    changed_pa["iucn_category"] = "II"

    # New PA with parent existing that has been updated
    new_pa = deepcopy(base_entry)
    del new_pa["documentId"]
    new_pa["wdpaid"] = 1000000000
    new_pa["parent"] = {
        "wdpaid": second_entry.get("wdpaid"),
        "wdpa_p_id": second_entry.get("wdpa_p_id"),
        "zone_id": second_entry.get("zone_id"),
        "environment": second_entry.get("environment"),
        "location": second_entry.get("location"),
    }

    second_entry["children"] = [
        {
            "wdpaid": new_pa.get("wdpaid"),
            "wdpa_p_id": new_pa.get("wdpa_p_id"),
            "zone_id": new_pa.get("zone_id"),
            "environment": new_pa.get("environment"),
            "location": new_pa.get("location"),
        }
    ]

    # Remove child parent link of existing PAs
    changed_parent = deepcopy(parent)
    changed_parent["children"] = None
    del changed_parent["documentId"]

    changed_child = deepcopy(child)
    changed_child["parent"] = None
    del changed_child["documentId"]

    current_db = make_df([base_entry, second_entry, third_entry, fourth_entry, parent, child])
    updated_pas = make_df([unchanged_pa, changed_pa, new_pa, changed_child, changed_parent])

    result = make_pa_updates(current_db, updated_pas, verbose=False)[0]
    new = result["new"]
    changed = result["changed"]
    deleted = result["deleted"]

    assert len(new) == 1  # new_pa
    assert len(changed) == 3  # changed_pa, changed_parent, changed_child
    assert len(deleted) == 2  # third_pa, fourth_pa

    new_entry = new[0]
    # New pa's parent should have a documentId equal to second_entry, other than that it
    # should be the same as new_pa's parent
    assert new_entry["parent"].get("documentId") == second_entry.get("documentId")
    del new_entry["parent"]["documentId"]
    assert new_entry["parent"] == new_pa["parent"]
    assert new_entry.get("documentId") is None

    # Verify that both expected deleted PA documentIds were identified.
    assert "doc-300" in deleted
    assert "doc-400" in deleted

    changed_string = deepcopy(changed_pa)
    changed_string["documentId"] = second_entry["documentId"]
    changed_string["area"] = round(changed_string["area"], 2)

    expected_changed_parent = deepcopy(changed_parent)
    expected_changed_parent["documentId"] = parent["documentId"]
    expected_changed_parent["area"] = round(expected_changed_parent["area"], 2)

    expected_changed_child = deepcopy(changed_child)
    expected_changed_child["documentId"] = child["documentId"]
    expected_changed_child["area"] = round(expected_changed_child["area"], 2)

    assert changed_string in changed
    assert expected_changed_child in changed
    assert expected_changed_parent in changed


# ---------------------------------------------------------------------------
# generate_protected_areas_table — MPAtlas meta -> Strapi-facing PA rows
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_mpatlas_meta_df():
    """intermediates/mpa_meta.csv shape (internal names, post-v4-normalization)."""
    return pd.DataFrame(
        {
            "name": ["Cairns Section", "Shared Waters Zone", "Pending Zone"],
            "calculated_area_km2": [10.0, 20.0, 5.0],
            "designated_date": ["1981-01", "1990", None],
            "wdpa_id": [555624, 100001, 100002],
            "wdpa_pid": ["555624_1", "100001_A", "100002_A"],
            "zone_id": [4821, 4822, 4823],
            "designation": ["Marine Park", "Marine Reserve", "Sanctuary"],
            "establishment_stage": ["implemented", "actively managed", "designated"],
            "country": ["AUS", "AUS,NZL", "MEX"],
            "protection_mpaguide_level": ["high", "full", "unknown"],
            "bbox": ["(0.0, 0.0, 1.0, 1.0)"] * 3,
        }
    )


@pytest.fixture
def mock_wdpa_meta_df():
    return pd.DataFrame(
        {
            "NAME": ["GBR WDPA"],
            "calculated_area_km2": [50.0],
            "STATUS": ["Designated"],
            "PA_DEF": [1],
            "STATUS_YR": [1981],
            "WDPAID": [555624],
            "WDPA_PID": ["555624_1"],
            "DESIG_TYPE": ["National"],
            "ISO3": ["AUS"],
            "IUCN_CAT": ["II"],
            "MARINE": [1],
            "bbox": ["(0.0, 0.0, 1.0, 1.0)"],
        }
    )


def test_generate_protected_areas_table_mpa_rows(
    monkeypatch, mock_mpatlas_meta_df, mock_wdpa_meta_df
):
    import geopandas as gpd
    from shapely.geometry import box

    import src.methods.protected_areas.protected_areas as pa_module

    meta_reads = {
        "mpa_meta.csv": mock_mpatlas_meta_df,
        "wdpa_meta.csv": mock_wdpa_meta_df,
    }
    monkeypatch.setattr(
        pa_module, "read_dataframe", lambda bucket, filename: meta_reads[filename].copy()
    )

    # eez lookup requires ABNJ and CHN entries to exist
    mock_eez = pd.DataFrame(
        {
            "location": ["AUS", "NZL", "MEX", "ABNJ", "CHN"],
            "AREA_KM2": [1000.0] * 5,
        }
    )
    mock_gadm = gpd.GeoDataFrame(
        {"location": ["AUS"], "geometry": [box(0, 0, 1, 1)]}, crs="EPSG:4326"
    )

    # filenames arrive with a tolerance suffix (e.g. eez_0.001.geojson)
    def mock_read_json_df(bucket, filename):
        return (mock_eez if filename.startswith("eez") else mock_gadm).copy()

    monkeypatch.setattr(pa_module, "read_json_df", mock_read_json_df)

    result = pa_module.generate_protected_areas_table(
        wdpa_file_name="wdpa_meta.csv",
        mpatlas_file_name="mpa_meta.csv",
        eez_file_name="eez.geojson",
        gadm_file_name="gadm.geojson",
        verbose=False,
    )

    mpa_rows = result[result["data_source"] == "mpatlas"]

    row = mpa_rows[mpa_rows["zone_id"] == 4821].iloc[0]
    assert row["name"] == "Cairns Section"
    assert row["wdpaid"] == 555624
    assert row["wdpa_p_id"] == "555624_1"
    assert row["designation"] == "Marine Park"
    assert row["mpaa_establishment_stage"] == "implemented"
    assert row["mpaa_protection_level"] == "high"
    assert row["year"] == 1981
    assert row["location"] == "AUS"
    assert row["environment"] == "marine"
    assert row["protection_status"] == "pa"

    # multi-country zone becomes one row per country
    assert set(mpa_rows[mpa_rows["zone_id"] == 4822]["location"]) == {"AUS", "NZL"}
    assert (
        mpa_rows[mpa_rows["zone_id"] == 4822]["mpaa_establishment_stage"] == "actively-managed"
    ).all()

    # zones without a designated date are excluded
    assert 4823 not in set(mpa_rows["zone_id"])
