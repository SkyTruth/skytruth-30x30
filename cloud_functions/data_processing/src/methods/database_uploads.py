from ast import literal_eval

import pandas as pd

from src.core.params import BUCKET, LOCATIONS_FILE_NAME
from src.core.strapi import Strapi
from src.utils.gcp import read_dataframe


def upload_locations(
    bucket: str = BUCKET,
    filename: str = LOCATIONS_FILE_NAME,
    request: dict = None,
    verbose: bool = True,
):
    """
    Prepares processed locations csv and passes it to Strapi method to update the database
    with data included in the csv.

    Preparation inlcudes:
    - converting stringified lists to actual lists
    - removing empty values
    - converting to a dict
    """
    list_fields = ["groups", "members", "terrestrial_bounds", "marine_bounds"]

    converters = {field: _parse_list_or_na for field in list_fields}
    dtype = {"total_marine_area": "Int64"}
    locs_df = read_dataframe(
        bucket_name=bucket, filename=filename, converters=converters, dtype=dtype
    )

    # Because there are empty values for land locked countries this has to be explicitly typecast
    locs_df["total_marine_area"] = locs_df["total_marine_area"].astype("Int64")

    # Remove keys with NA values, this will allow us ot only upsert data we actually have
    # rather than stubbing defaults
    locations = _extract_non_na_values(locs_df)

    options = request.get("options") if request else None

    if verbose:
        print("Writing locations to the database")

    client = Strapi()
    return client.upsert_locations(locations, options)


def _extract_non_na_values(df: pd.DataFrame) -> list[dict]:
    """Converts a dataframe to a dictionary while leaving off any None/NA/NaN values"""
    cleaned = [
        {key: val for key, val in row.items() if isinstance(val, list) or pd.notna(val)}
        for row in df.to_dict(orient="records")
    ]

    return cleaned


def _parse_list_or_na(val):
    """
    Helper method to parse lists for a dict when read from csv. Lists in csvs become
    stringified, this takes a cell value and returns either a python list if the cell is a
    stringified list, otherwise it will for the value into a list unless the value is NA or "" -
    typically this represents an empty cell in a csv - then it will return pd.NA
    """
    if pd.isna(val) or val == "":
        return pd.NA
    try:
        parsed_val = literal_eval(val)
        return parsed_val if isinstance(parsed_val, list) else [parsed_val]
    except (ValueError, SyntaxError):
        return pd.NA  # fallback if bad format
