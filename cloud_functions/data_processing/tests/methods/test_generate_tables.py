import pandas as pd
import pytest
from copy import deepcopy

from src.methods.generate_tables import database_updates


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
        "location": "CHE",
        "mpaa_protection_level": "",
        "bbox": "(8.47, 47.35, 8.47, 47.35)",
        "year": 2023,
        "protection_status": "pa",
        "environment": "terrestrial",
        "data_source": "Protected Planet",
        "iucn_category": "Not Assigned",
        "coverage": 0.0,
        "parent": None,
        "children": None,
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

    result = database_updates(current_db, updated_pas, verbose=False)
    assert len(result["new"]) == 1
    assert result["new"][0]["wdpaid"] == 999


def test_detect_deleted_entry(base_entry):
    """Detects when a record in current_db is missing from updated_pas."""
    current_db = make_df([base_entry])

    updated_pas = pd.DataFrame(columns=[c for c in current_db.columns if c != "id"])

    result = database_updates(current_db, updated_pas, verbose=False)
    assert result["deleted"] == [1]


def test_detect_changed_string(base_entry):
    """Detects when a string field (e.g. designation) changes."""
    current_db = make_df([base_entry])
    updated_entry = deepcopy(base_entry)
    updated_entry["designation"] = "International"
    updated_entry.pop("id", None)

    updated_pas = make_df([updated_entry])

    result = database_updates(current_db, updated_pas, verbose=False)
    assert len(result["changed"]) == 1
    assert result["changed"][0]["designation"] == "International"


def test_detect_changed_area_large(base_entry):
    """Detects when the area value changes by more than 1%."""
    current_db = make_df([base_entry])
    updated_entry = deepcopy(base_entry)
    updated_entry["area"] = base_entry["area"] * 1.2
    updated_entry.pop("id", None)

    updated_pas = make_df([updated_entry])

    result = database_updates(current_db, updated_pas, verbose=False)
    assert len(result["changed"]) == 1
    assert pytest.approx(result["changed"][0]["area"], rel=1e-9) == updated_entry["area"]


def test_ignore_small_area_change(base_entry):
    """Ignores area changes smaller than or equal to 1%."""
    current_db = make_df([base_entry])
    updated_entry = deepcopy(base_entry)
    updated_entry["area"] = base_entry["area"] * 1.001
    updated_entry.pop("id", None)

    updated_pas = make_df([updated_entry])

    result = database_updates(current_db, updated_pas, verbose=False)
    assert len(result["changed"]) == 0


def test_detect_changed_parent(base_entry):
    """Detects when the parent field changes from None to a dict."""
    current_db = make_df([base_entry])
    updated_entry = deepcopy(base_entry)
    updated_entry["parent"] = {
        "wdpaid": base_entry["wdpaid"],
        "wdpa_p_id": base_entry["wdpa_p_id"] + "_A",
        "zone_id": None,
        "environment": base_entry["environment"],
        "id": None,
    }
    updated_entry.pop("id", None)

    updated_pas = make_df([updated_entry])

    result = database_updates(current_db, updated_pas, verbose=False)
    assert len(result["changed"]) == 1
    assert isinstance(result["changed"][0]["parent"], dict)


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
            "id": None,
        }
    ]
    updated_entry.pop("id", None)

    updated_pas = make_df([updated_entry])

    result = database_updates(current_db, updated_pas, verbose=False)
    assert len(result["changed"]) == 1
    assert isinstance(result["changed"][0]["children"], list)


def test_parent_child_linkage_consistency():
    """Confirms that if a parent lists a child, the child lists that parent."""
    parent_entry = {
        "id": 1,
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
                "id": 2,
            }
        ],
        "bbox": "(-90.1,18.8,-89.5,19.2)",
        "mpaa_establishment_stage": "",
        "mpaa_protection_level": "",
    }

    child_entry = {
        "id": 2,
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
            "id": 1,
        },
        "children": None,
        "bbox": "(-90.1,18.8,-89.5,19.2)",
        "mpaa_establishment_stage": "",
        "mpaa_protection_level": "",
    }

    current_db = make_df([parent_entry, child_entry])
    updated_pas = make_df(
        [
            {k: v for k, v in parent_entry.items() if k != "id"},
            {k: v for k, v in child_entry.items() if k != "id"},
        ]
    )

    result = database_updates(current_db, updated_pas, verbose=False)
    assert result["new"] == []
    assert result["deleted"] == []
    assert result["changed"] == []


def test_no_changes(base_entry):
    """Ensures no false positives when current_db and updated_pas match exactly."""
    current_db = make_df([base_entry])
    updated_entry = deepcopy(base_entry)
    updated_entry.pop("id", None)
    updated_pas = make_df([updated_entry])

    result = database_updates(current_db, updated_pas, verbose=False)
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

    result = database_updates(current_db, updated_pas, verbose=False)
    new_record = result["new"][0]
    assert "id" not in new_record


def test_existing_entry_keeps_id(base_entry):
    """Ensure that unchanged or changed entries keep their id from current_db."""
    current_db = make_df([base_entry])
    updated_entry = deepcopy(base_entry)
    updated_entry["designation"] = "International"
    updated_entry.pop("id", None)

    updated_pas = make_df([updated_entry])
    result = database_updates(current_db, updated_pas, verbose=False)
    changed_record = result["changed"][0]
    assert changed_record["id"] == base_entry["id"]


def test_existing_child_keeps_id():
    """Ensure that an existing child keeps its original id."""
    parent = {
        "id": 1,
        "name": "Parent",
        "area": 100,
        "wdpaid": 123,
        "wdpa_p_id": "123_A",
        "zone_id": None,
        "designation": "National",
        "location": "MEX",
        "environment": "terrestrial",
        "data_source": "Protected Planet",
        "protection_status": "pa",
        "year": 2023,
        "iucn_category": "VI",
        "coverage": 0.1,
        "parent": None,
        "children": [
            {
                "wdpaid": 123,
                "wdpa_p_id": "123_B",
                "zone_id": None,
                "environment": "terrestrial",
                "id": 2,
            }
        ],
        "bbox": "(...)",
        "mpaa_establishment_stage": "",
        "mpaa_protection_level": "",
    }

    child = {
        "id": 2,
        "name": "Child",
        "area": 50,
        "wdpaid": 123,
        "wdpa_p_id": "123_B",
        "zone_id": None,
        "designation": "National",
        "location": "MEX",
        "environment": "terrestrial",
        "data_source": "Protected Planet",
        "protection_status": "pa",
        "year": 2023,
        "iucn_category": "Ia",
        "coverage": 0.05,
        "parent": {
            "wdpaid": 123,
            "wdpa_p_id": "123_A",
            "zone_id": None,
            "environment": "terrestrial",
            "id": 1,
        },
        "children": None,
        "bbox": "(...)",
        "mpaa_establishment_stage": "",
        "mpaa_protection_level": "",
    }

    current_db = make_df([parent, child])
    updated_pas = make_df(
        [
            {k: v for k, v in parent.items() if k != "id"},
            {k: v for k, v in child.items() if k != "id"},
        ]
    )

    result = database_updates(current_db, updated_pas, verbose=False)

    # No new or changed records expected
    assert result["new"] == []
    assert result["changed"] == []

    # After running, updated_pas["children"] should have id filled in
    updated_parent = updated_pas.loc[updated_pas["name"] == "Parent"].iloc[0].to_dict()
    assert updated_parent["children"][0]["id"] == 2


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
            "id": None,
        }
    ]
    updated_entry.pop("id", None)

    updated_pas = make_df([updated_entry])
    result = database_updates(current_db, updated_pas, verbose=False)
    changed_record = result["changed"][0]
    assert changed_record["children"][0]["id"] is None
