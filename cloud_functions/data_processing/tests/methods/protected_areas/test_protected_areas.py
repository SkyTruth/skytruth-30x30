from copy import deepcopy

import pandas as pd
import pytest

from src.methods.protected_areas.protected_areas import make_pa_updates


@pytest.fixture
def base_entry():
    """Baseline protected area entry for current_db."""
    return {
        "id": 1,
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
        "id": 2,
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
                "id": 3,
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
        "id": 3,
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
            "id": 2,
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
    new_entry.pop("id", None)  # updated_pas should not have id

    updated_pas = make_df([{k: v for k, v in base_entry.items() if k != "id"}, new_entry])

    result = make_pa_updates(current_db, updated_pas, verbose=False)[0]

    assert len(result["deleted"]) == 0
    assert len(result["changed"]) == 0
    assert len(result["new"]) == 1

    assert result["new"][0].get("id") is None
    assert result["new"][0]["wdpaid"] == 999


def test_detect_deleted_entry(base_entry):
    """Detects when a record in current_db is missing from updated_pas."""
    current_db = make_df([base_entry])

    updated_pas = pd.DataFrame(columns=[c for c in current_db.columns if c != "id"])

    result = make_pa_updates(current_db, updated_pas, verbose=False)[0]

    assert result["deleted"] == [1]
    assert len(result["deleted"]) == 1
    assert len(result["new"]) == 0
    assert len(result["changed"]) == 0


def test_detect_changed_string(base_entry):
    """Detects when a string field (e.g. designation) changes."""
    current_db = make_df([base_entry])
    updated_entry = deepcopy(base_entry)
    updated_entry["designation"] = "International"
    updated_entry.pop("id", None)

    updated_pas = make_df([updated_entry])

    result = make_pa_updates(current_db, updated_pas, verbose=False)[0]

    assert len(result["changed"]) == 1
    assert len(result["deleted"]) == 0
    assert len(result["new"]) == 0

    assert result["changed"][0]["designation"] == "International"
    assert result["changed"][0]["id"] == base_entry.get("id")


def test_detect_changed_area_large(base_entry):
    """
    Happy path test when the area value changes by more than 1% is dected and rounds to 2 decimals.
    """
    current_db = make_df([base_entry])
    updated_entry = deepcopy(base_entry)

    updated_entry["area"] = base_entry["area"] * 1.2
    updated_entry.pop("id", None)

    updated_pas = make_df([updated_entry])

    result = make_pa_updates(current_db, updated_pas, verbose=False)[0]

    assert len(result["changed"]) == 1
    assert len(result["deleted"]) == 0
    assert len(result["new"]) == 0

    assert result["changed"][0]["area"] == round(updated_entry["area"], 2)
    assert result["changed"][0]["id"] == base_entry.get("id")


def test_ignore_small_area_change(base_entry):
    """Ignores area changes smaller than or equal to 1%."""
    current_db = make_df([base_entry])
    updated_entry = deepcopy(base_entry)

    # Using slightly under limit to prevent false failures with floating point percision rounding
    updated_entry["area"] = base_entry["area"] * 1.009
    updated_entry.pop("id", None)
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
        "id": None,
    }
    updated_entry.pop("id", None)

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
            "id": None,
        }
    ]
    updated_entry.pop("id", None)

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
            {k: v for k, v in parent.items() if k != "id"},
            {k: v for k, v in child.items() if k != "id"},
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
    updated_entry.pop("id", None)
    updated_pas = make_df([updated_entry])

    result = make_pa_updates(current_db, updated_pas, verbose=False)[0]
    assert result["new"] == []
    assert result["changed"] == []
    assert result["deleted"] == []


def test_new_entry_has_no_id(base_entry):
    """Ensure that new entries do not have an 'id' key in db_changes."""
    current_db = make_df([base_entry])

    new_entry = deepcopy(base_entry)
    new_entry["wdpaid"] = 999
    new_entry["wdpa_p_id"] = "999"
    new_entry.pop("id", None)

    updated_pas = make_df([{k: v for k, v in base_entry.items() if k != "id"}, new_entry])

    result = make_pa_updates(current_db, updated_pas, verbose=False)[0]
    new_record = result["new"][0]
    assert "id" not in new_record

    assert len(result["changed"]) == 0
    assert len(result["deleted"]) == 0


def test_existing_entry_keeps_id(base_entry):
    """Ensure that unchanged or changed entries keep their id from current_db."""
    current_db = make_df([base_entry])
    updated_entry = deepcopy(base_entry)
    updated_entry["designation"] = "International"
    updated_entry.pop("id", None)

    updated_pas = make_df([updated_entry])
    result = make_pa_updates(current_db, updated_pas, verbose=False)[0]
    changed_record = result["changed"][0]
    assert changed_record["id"] == base_entry["id"]


def test_new_child_has_no_id(base_entry):
    """Ensure that a brand new child entry has id=None (explicitly present)."""
    current_db = make_df([base_entry])
    updated_entry = deepcopy(base_entry)
    updated_entry["children"] = [
        {
            "wdpaid": base_entry["wdpaid"],
            "wdpa_p_id": base_entry["wdpa_p_id"] + "_B",
            "zone_id": None,
            "environment": "terrestrial",
            "location": base_entry["location"],
            "id": None,
        }
    ]
    updated_entry.pop("id", None)

    updated_pas = make_df([updated_entry])
    result = make_pa_updates(current_db, updated_pas, verbose=False)[0]
    changed_record = result["changed"][0]

    assert len(result["changed"]) == 1
    assert len(result["new"]) == 0
    assert len(result["deleted"]) == 0

    assert changed_record["children"][0]["id"] is None
    assert changed_record["children"] == updated_entry["children"]


def test_multiple_children(base_entry, parent, child):
    """test the case where a PA has multiple children and a subset change"""
    updated_parent = deepcopy(parent)
    updated_parent.pop("id", None)
    updated_parent["children"][0].pop("id", None)

    updated_child = deepcopy(child)
    updated_child.pop("id", None)

    parent["children"].append(base_entry)
    current_db = make_df([parent, child])

    updated_pas = make_df([updated_parent, updated_child])
    result = make_pa_updates(current_db, updated_pas, verbose=False)[0]

    print("Result", result)

    assert len(result["changed"]) == 1
    assert len(result["new"]) == 0
    assert len(result["deleted"]) == 0

    assert len(result["changed"][0]["children"]) == 1
    assert result["changed"][0]["children"][0]["id"] == child["id"]


def test_pas_with_changed_deleted_new(base_entry, child, parent):
    """
    Happy path test for complex sample unchangewd, changed, new and deleted PAs'
    """
    second_entry = deepcopy(base_entry)
    second_entry["wdpaid"] = 2
    second_entry["id"] = 200

    third_entry = deepcopy(base_entry)
    third_entry["wdpaid"] = 3
    third_entry["id"] = 300

    fourth_entry = deepcopy(base_entry)
    fourth_entry["wdpaid"] = 4
    fourth_entry["id"] = 400

    unchanged_pa = deepcopy(base_entry)
    del unchanged_pa["id"]

    changed_pa = deepcopy(second_entry)
    del changed_pa["id"]
    changed_pa["area"] = second_entry["area"] * 2
    changed_pa["iucn_category"] = "II"

    changed_bbox = deepcopy(fourth_entry)
    del changed_bbox["id"]
    changed_bbox["bbox"][2] = 0

    # New PA with parent existing that has been updated
    new_pa = deepcopy(base_entry)
    del new_pa["id"]
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
    del changed_parent["id"]

    changed_child = deepcopy(child)
    changed_child["parent"] = None
    del changed_child["id"]

    current_db = make_df([base_entry, second_entry, third_entry, fourth_entry, parent, child])
    updated_pas = make_df(
        [unchanged_pa, changed_pa, changed_bbox, new_pa, changed_child, changed_parent]
    )

    result = make_pa_updates(current_db, updated_pas, verbose=False)[0]
    new = result["new"]
    changed = result["changed"]
    deleted = result["deleted"]

    assert len(new) == 1  # new_pa
    assert len(changed) == 4  # changed_pa, changed_bbox, changed_parent, changed_child
    assert len(deleted) == 1  # third_pa

    new_entry = new[0]
    # New pa's parent should have an id equal to second_entry, other than that it should
    # be the same as new_pa's parent
    assert new_entry["parent"].get("id") == second_entry.get("id")
    del new_entry["parent"]["id"]
    assert new_entry["parent"] == new_pa["parent"]
    assert new_entry.get("id") is None

    assert deleted[0] == 300

    changed_string = deepcopy(changed_pa)
    changed_string["id"] = second_entry["id"]
    changed_string["area"] = round(changed_string["area"], 2)

    changed_bounds = deepcopy(changed_bbox)
    changed_bounds["id"] = fourth_entry["id"]
    changed_bounds["area"] = round(changed_bounds["area"], 2)

    expected_changed_parent = deepcopy(changed_parent)
    expected_changed_parent["id"] = parent["id"]
    expected_changed_parent["area"] = round(expected_changed_parent["area"], 2)

    expected_changed_child = deepcopy(changed_child)
    expected_changed_child["id"] = child["id"]
    expected_changed_child["area"] = round(expected_changed_child["area"], 2)

    assert changed_string in changed
    assert changed_bounds in changed
    assert expected_changed_child in changed
    assert expected_changed_parent in changed
