# test_relation_diff_index.py
import pandas as pd
from pandas.testing import assert_series_equal

from src.methods.protected_areas.pa_processors import relation_diff_index


def test_no_parents_no_change():
    """Test that parent = None is detected as no change"""
    parent_left = pd.DataFrame({"rel": [None]})
    parent_right = pd.DataFrame({"rel": [None]})
    mask = relation_diff_index(parent_left, parent_right, "rel")
    assert_series_equal(mask, pd.Series([False]))


def test_new_parent_exisitng_pa():
    """Test that adding an existing PA as a parent is detected"""
    parent_left = pd.DataFrame({"rel": [None]})
    parent_right = pd.DataFrame({"rel": [{"id": 1}]})
    mask = relation_diff_index(parent_left, parent_right, "rel")
    assert_series_equal(mask, pd.Series([True]))


def test_changing_parent_from_knonw_to_new_pa():
    """Test updating the parent from a known PA to a net-new PA"""
    parent_left = pd.DataFrame({"rel": [{"id": None}]})
    parent_right = pd.DataFrame({"rel": [{"id": 5}]})
    mask = relation_diff_index(parent_left, parent_right, "rel")
    assert_series_equal(mask, pd.Series([True]))


def test_multiple_pas_one_new_parent():
    """
    Test scenario with multiple PA's where one is assigned a parent of a known PA
    """
    parent_left = pd.DataFrame({"rel": [{"id": 10}, {"id": 7}]})
    parent_right = pd.DataFrame({"rel": [{"id": 11}, {"id": 7}]})
    mask = relation_diff_index(parent_left, parent_right, "rel")
    assert_series_equal(mask, pd.Series([True, False]))


def test_children_different_lengths():
    """Test changing the total number of children is detected as a change"""
    children_left = pd.DataFrame({"rel": [[{"id": 1}, {"id": 2}]]})
    children_right = pd.DataFrame({"rel": [[{"id": 1}]]})
    mask = relation_diff_index(children_left, children_right, "rel")
    assert_series_equal(mask, pd.Series([True]))


def test_adding_net_new_child():
    """Test adding a net-new PA as a child is dtected as a change"""
    children_left = pd.DataFrame({"rel": [[{"id": 1}, {"id": None}]]})
    children_right = pd.DataFrame({"rel": [[{"id": 1}, {"id": 2}]]})
    mask = relation_diff_index(children_left, children_right, "rel")
    assert_series_equal(mask, pd.Series([True]))


def test_multiple_pas_one_change_children():
    """
    Test scenario with multiple PA's where one has a change in known children
    """
    children_left = pd.DataFrame({"rel": [[{"id": 1}, {"id": 3}], [{"id": 4}, {"id": 5}]]})
    children_right = pd.DataFrame({"rel": [[{"id": 1}, {"id": 2}], [{"id": 5}, {"id": 4}]]})
    mask = relation_diff_index(children_left, children_right, "rel")
    assert_series_equal(mask, pd.Series([True, False]))


def test_mixed_parent_vs_children_types_true():
    """
    Test (probabLy) unused edge case of the relationship changing from a list to a single
    dict or vice-verse
    """
    parent_left = pd.DataFrame({"rel": [{"id": 1}]})
    children_right = pd.DataFrame({"rel": [[{"id": 1}]]})
    mask = relation_diff_index(parent_left, children_right, "rel")
    assert_series_equal(mask, pd.Series([True]))


def test_alignment_when_right_has_extra_rows():
    # Left has 1 row; right has 2 rows. We compare by left's index.
    children_left = pd.DataFrame({"rel": [[{"id": 1}, {"id": 2}]]}, index=[10])
    children_right = pd.DataFrame({"rel": [[{"id": 1}, {"id": 2}], [{"id": 3}]]}, index=[10, 11])
    mask = relation_diff_index(children_left, children_right, "rel")
    assert_series_equal(mask, pd.Series([False], index=[10]))


def test_alignment_when_left_has_extra_rows():
    # Right has 1 row; left has 2 rows.
    children_left = pd.DataFrame({"rel": [[{"id": 1}], [{"id": 2}]]}, index=[0, 1])
    children_right = pd.DataFrame({"rel": [[{"id": 1}]]}, index=[0])
    mask = relation_diff_index(children_left, children_right, "rel")
    # Row 0 equal; row 1 compares to missing on right → treated as None → True
    assert_series_equal(mask, pd.Series([False, True], index=[0, 1]))
