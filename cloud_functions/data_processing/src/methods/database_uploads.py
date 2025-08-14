from ast import literal_eval
import pandas as pd

from src.core.strapi import Strapi
from src.core.params import BUCKET, LOCATIONS_FILE_NAME
from src.utils.gcp import read_dataframe


def upload_locations(
    bucket: str = BUCKET, filename: str = LOCATIONS_FILE_NAME, verbose: bool = True
):
    list_fields = ["groups", "members", "terrestrial_bounds", "marine_bounds"]

    converters = {field: _parse_list_or_na for field in list_fields}
    locs_df = read_dataframe(bucket_name=bucket, filename=filename, converters=converters)

    # locations = locs_df.to_dict(orient="records")

    # Remove keys with NA values, this will allow us ot only upsert data we actually have rather than
    # stubbing defaults
    locations = [
        {key: val for key, val in row.items() if isinstance(val, list) or pd.notna(val)}
        for row in locs_df.to_dict(orient="records")
    ]
    print(locations[:3])

    client = Strapi()
    # return "Success"
    return client.upsert_locations(locations[:3])


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
        return parsed_val if isinstance(parsed_val, list) else [val]
    except (ValueError, SyntaxError):
        return pd.NA  # fallback if bad format
