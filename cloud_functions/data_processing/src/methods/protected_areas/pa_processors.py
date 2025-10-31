from collections.abc import Iterable, Sequence
from typing import Any

import pandas as pd


def normalize_value(v):
    if isinstance(v, float):
        func = "<NA>" if (pd.isna(v) or v is None) else int(v)
    elif v is None:
        func = "<NA>"
    else:
        func = v
    return str(func)


def get_unique_identifier(row, cols):
    return "_".join(normalize_value(row[c]) for c in cols)


def get_identifier(pa, cols, current_db):
    """
    get database ID associated with a unique identifier (combination
    of environment, wdpaid, wdpa_pid, zone_id, location) if one exists. Used to
    add id to parent/children columns
    """
    if not isinstance(pa, dict):
        return None

    # build identifier in the same way as updated_pas["identifier"]
    identifier = get_unique_identifier(pa, cols)

    if len(current_db) > 0:
        match = current_db.loc[current_db["identifier"] == identifier, "id"]
        _id = int(match.iloc[0]) if not match.empty else None
    else:
        _id = None

    return {**pa, "id": _id}


def get_identifier_children(children, cols, current_db):
    if not isinstance(children, list):
        return None
    return [get_identifier(child, cols, current_db) for child in children]


def str_dif_idx(df1, df2, col):
    return (~df2[col].isnull()) & (df2[col] != df1[col])


def num_dif_idx(df1, df2, col):
    # Round to 2 digits to match precision of DB.
    # Round with added epsilon so that 0.005 rounds up.
    df1[col] = (df1[col] + 1e-6).round(2)
    df2[col] = (df2[col] + 1e-6).round(2)
    return (~df2[col].isna()) & ((df1[col].isna()) | (abs(df2[col] - df1[col]) / df1[col] > 0.01))


def unordered_list_dif_idx(df1, df2, col):
    """Return True where list elements differ, ignoring order and NaNs."""

    def to_sorted_tuple(x):
        if not isinstance(x, (list, tuple)):
            return tuple() if pd.isna(x) else (x,)
        return tuple(sorted([v for v in x if pd.notna(v)]))

    return df1[col].apply(to_sorted_tuple) != df2[col].apply(to_sorted_tuple)


def ordered_list_dif_idx(df1, df2, col):
    """Return True where ordered list elements are unequal or either is not a sequence"""

    def is_listlike(x):
        # Avoid treating strings and bytes as sequences
        return isinstance(x, Sequence) and not isinstance(x, (str, bytes, bytearray))

    def compare(a, b):
        if is_listlike(a) and is_listlike(b):
            return a != b
        return True

    mask = [compare(a, b) for a, b in zip(df1[col], df2[col], strict=False)]
    return pd.Series(mask, index=df1.index)


def relation_diff_index(
    df_left: pd.DataFrame,
    df_right: pd.DataFrame,
    column: str,
) -> pd.Series:
    """
    Return a boolean mask for rows where the relation in `column` differs between df_left and
    df_right. Used to check if PA relationships, parent (dict) or children (list[dict]),
    have changed

    True if:
      * Only one side is None.
      * (Non-list case) Only one side has an 'id' != None.
      * (Non-list case) Both have 'id' but the 'id' values differ.
      * (List case) Lists have different lengths.
      * (List case) Any dict in either list has 'id' == None.
      * (List case) Any 'id' present in one list is not present in the other (order-insensitive).
    """

    right_series = df_right[column].reindex_like(df_left)
    left_values = df_left[column].values
    right_values = right_series.values

    def is_none(value: Any) -> bool:
        return value is None

    def is_list_of_dicts(value: Any) -> bool:
        return isinstance(value, (list, tuple))

    def extract_single_id(value: dict[str, Any]) -> Any | None:
        return value.get("id")

    def extract_list_ids_and_flags(
        value: Iterable[dict[str, Any]],
    ) -> tuple[list[Any | None], bool]:
        """
        From a list/tuple of dicts, return:
          - list of 'id' values (may include None)
          - flag: True if any dict has 'id' == None
        """
        ids: list[Any | None] = []
        any_none_id = False
        for item in value:
            current_id = item.get("id", None)
            if current_id is None:
                any_none_id = True
            ids.append(current_id)
        return ids, any_none_id

    difference_flags: list[bool] = []

    for left_cell, right_cell in zip(left_values, right_values, strict=False):
        # Only one side is None -> changed from or to no relationships
        if is_none(left_cell) ^ is_none(right_cell):
            difference_flags.append(True)
            continue

        # Both None → No relationships, hasn't changed
        if is_none(left_cell) and is_none(right_cell):
            difference_flags.append(False)
            continue

        left_is_list = is_list_of_dicts(left_cell)
        right_is_list = is_list_of_dicts(right_cell)

        # If types differ (one list, one dict), treat as a change
        # This should not happen, but will support potential future
        # update to allow multiple parents
        if left_is_list != right_is_list:
            difference_flags.append(True)
            continue

        # Parent case -> only one relationship
        if not left_is_list:
            left_id = extract_single_id(left_cell)
            right_id = extract_single_id(right_cell)

            # Only one side has an 'id' not None
            # PA has an existing parent and update has a net-new PA as the parent
            if (left_id is not None) ^ (right_id is not None):
                difference_flags.append(True)
                continue

            # Both have ids but differ
            # Changing parent to another pre-exisitng PA
            if (left_id is not None) and (right_id is not None) and (left_id != right_id):
                difference_flags.append(True)
                continue

            # Otherwise equal
            difference_flags.append(False)
            continue

        # Relationship is a list so checking children relations
        left_ids, left_has_none_id = extract_list_ids_and_flags(left_cell)
        right_ids, right_has_none_id = extract_list_ids_and_flags(right_cell)

        # Different lengths -> added or removed a child
        if len(left_ids) != len(right_ids):
            difference_flags.append(True)
            continue

        # Any dict has id == None on either side
        # Adding a net-new PA to the eraltionship list
        if left_has_none_id or right_has_none_id:
            difference_flags.append(True)
            continue

        # Compare membership of ids (order-insensitive, ignoring None since none exist now)
        # Some relationship to a pre-exisitn PA has changed
        if set(left_ids) != set(right_ids):
            difference_flags.append(True)
            continue

        # Otherwise equal
        difference_flags.append(False)

    return pd.Series(difference_flags, index=df_left.index)
