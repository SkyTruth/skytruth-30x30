import ast
from collections.abc import Mapping, Sequence
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import MultiPolygon, Polygon


def add_constants(df: pd.DataFrame, const: Mapping[str, Any]) -> pd.DataFrame:
    """
    Add a set of constant columns to a DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame (modified in-place).
    const : Mapping[str, Any]
        Mapping of column name -> constant value to assign.
    """
    for c in const:
        df[c] = const[c]
    return df


def add_environment(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add an 'environment' column derived from string-coded 'MARINE'.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain a 'MARINE' column with values '0', '1', or '2'.
    """
    df = df.copy()
    df["environment"] = df["MARINE"].map({"0": "terrestrial", "1": "marine", "2": "marine"})
    return df


def add_protected_from_fishing_area(
    df: pd.DataFrame,
    fishing_protection_levels: Mapping[str, Sequence[str]],
) -> pd.DataFrame:
    """
    For each protection level, sum the listed columns row-wise into
    a new '<level>_protected_area' column.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    fishing_protection_levels : Mapping[str, Sequence[str]]
        Dict like {'highly': ['lfp5_area', 'lfp4_area'], 'fully': ['lfp3_area'], ..}.
    """
    df = df.copy()

    for level in fishing_protection_levels:
        df[f"{level}_protected_area"] = df[fishing_protection_levels[level]].sum(axis=1)
    return df


def add_protected_from_fishing_percent(
    df: pd.DataFrame,
    fishing_protection_levels: Mapping[str, Sequence[str]],
) -> pd.DataFrame:
    """
    For each protection level, compute percent protected from fishing

    Parameters
    ----------
    df : pd.DataFrame
        Must include 'total_area' and '<level>_protected_area' columns.
    fishing_protection_levels : Mapping[str, Sequence[str]]
        Same keys as used in add_protected_from_fishing_area.
    """
    df = df.copy()
    for level in fishing_protection_levels:
        df[f"{level}_pct"] = 100 * df[f"{level}_protected_area"] / df["total_area"]
    return df


def add_parent(
    df: pd.DataFrame,
    parent_dict: Mapping[Any, Any],
    location_name: str = "location",
) -> pd.DataFrame:
    """
    Add a 'parent_id' column by mapping values from a location column.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    parent_dict : Mapping[Any, Any]
        Map from location -> parent id.
    location_name : str, default 'location'
        Column whose values are looked up in parent_dict.
    """
    df = df.copy()
    df["parent_id"] = df[location_name].apply(lambda loc: parent_dict.get(loc, loc))
    return df


def add_pas_oecm(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add PAS/OECM percentage and count columns.

    Parameters
    ----------
    df : pd.DataFrame
        Must include:
        - 'pa_coverage', 'coverage'
        - 'protected_area_polygon_count', 'protected_area_point_count'
        - 'oecm_polygon_count', 'oecm_point_count'
    """
    df = df.copy()
    df["pas_percent_area"] = 100 * df["pa_coverage"] / df["coverage"]
    df["oecm_percent_area"] = 100 * (1 - df["pa_coverage"] / df["coverage"])
    df["pas_count"] = df["protected_area_polygon_count"] + df["protected_area_point_count"]
    df["oecm_count"] = df["oecm_polygon_count"] + df["oecm_point_count"]
    return df


def add_percentage_protection_mp(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add 'percentage' (percent protected) to MPAtlas stats

    Parameters
    ----------
    df : pd.DataFrame
        Must include 'protected_area' and 'area'.
    """
    df = df.copy()
    df["percentage"] = df["protected_area"] / df["area"]
    return df


def add_total_area_mp(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add 'total_area' to MPAtlas stats

    Parameters
    ----------
    df : pd.DataFrame
        Must include 'protected_area', 'percentage', 'wdpa_marine_km2'.
    """
    df = df.copy()
    df["total_area"] = df["protected_area"] / (df["percentage"] / 100.0)
    df.loc[df["percentage"] == 0, "total_area"] = df["wdpa_marine_km2"]
    return df


def add_year(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parse 'designated_date' as YYYY-MM-dd and extract the year.

    Parameters
    ----------
    df : pd.DataFrame
        Must include 'designated_date' string column.
    """
    df = df.copy()
    df["year"] = df["designated_date"].apply(lambda x: int(x.split("-")[0]))
    return df


def clean_geometries(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Make geometries valid (fix self-intersections, etc.).

    Parameters
    ----------
    gdf : gpd.GeoDataFrame
    """
    gdf.geometry = gdf.geometry.make_valid()
    return gdf


def convert_poly_to_multi(df: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Ensure all polygon geometries are MultiPolygon.

    Parameters
    ----------
    df : gpd.GeoDataFrame
        Must include a 'geometry' column of Polygon/MultiPolygon.
    """
    df = df.copy()
    df["geometry"] = df["geometry"].apply(
        lambda x: MultiPolygon([x])
        if isinstance(x, Polygon)
        else x
        if isinstance(x, MultiPolygon)
        else x
    )
    return df


def convert_type(
    df: pd.DataFrame,
    conversion: Mapping[str, Sequence[str | type]],
) -> pd.DataFrame:
    """
    Convert column dtypes using a mapping of column -> sequence of dtypes.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    conversion : Mapping[str, Sequence[Union[str, type]]]
        For each column, try casting in order (e.g., ['float', 'Int64'])
    """
    df = df.copy()
    for col in conversion:
        for con in conversion[col]:
            df[col] = df[col].astype(con)

    return df


def extract_column_dict_str(
    df: pd.DataFrame,
    column_dict: Mapping[str, str] | Sequence[str],
    column: str,
) -> pd.DataFrame:
    """
    Parse a column of dict-like strings and expand keys into new columns.

    Parameters
    ----------
    df : pd.DataFrame
        Input data.
    column_dict : Mapping[str, str] or Sequence[str]
        If dict: map source_key -> new_column_name.
        If list: keys to extract; new columns use the same key names.
    column : str
        Column containing dict-like strings.
    """

    def safe_literal_eval(x):
        try:
            return ast.literal_eval(x) if isinstance(x, str) else None
        except (ValueError, SyntaxError):
            return None

    df = df.copy()
    parsed_col = df[column].apply(safe_literal_eval)

    if isinstance(column_dict, dict):
        for d in column_dict:
            df[column_dict[d]] = parsed_col.apply(
                lambda x, d=d: x.get(d) if isinstance(x, dict) else None
            )

    elif isinstance(column_dict, list):
        for d in column_dict:
            df[d] = parsed_col.apply(lambda x, d=d: x.get(d) if isinstance(x, dict) else None)

    return df


def fp_location(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parse Protected Seas location information to separate into territories

    Parameters
    ----------
    df : pd.DataFrame
        Must include 'iso_sov' and 'iso_ter'.
    """

    def _process_one_country(df):
        if len(df) == 1 and df.iloc[0]["iso_ter"] == "":
            df["location"] = df["iso_sov"]
            return df.drop(columns=["iso_ter"])

        df = df[df["iso_ter"] != ""]
        df.loc[df["iso_ter"] == "NAT", "iso_ter"] = df.loc[df["iso_ter"] == "NAT", "iso_sov"]
        df["location"] = df["iso_ter"]
        return df.drop(columns=["iso_ter"])

    df = df.copy()
    return df.groupby("iso_sov", group_keys=False).apply(_process_one_country)


def get_highly_protected_from_fishing_area(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sum area and highly_protected_area per location.

    Parameters
    ----------
    df : pd.DataFrame
        Must include 'location', 'area', 'highly_protected_area'.
    """
    return df.groupby("location")[["area", "highly_protected_area"]].sum().reset_index()


def remove_columns(df: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    """
    Drop specified columns.

    Parameters
    ----------
    df : pd.DataFrame
    columns : Sequence[str]
    """
    df = df.drop(columns=columns)
    return df


def remove_non_designated_m(df: pd.DataFrame) -> pd.DataFrame:
    """
    Keep rows where 'designated_date' is not null.
    """
    return df[df["designated_date"].notnull()]


def remove_non_designated_p(df: pd.DataFrame) -> pd.DataFrame:
    """
    Keep rows where 'STATUS' == 'Designated'.

    Returns
    -------
    pd.DataFrame
    """
    return df[df["STATUS"] == "Designated"]


def rename_habitats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter to known habitat names and map them to standardized labels.

    Parameters
    ----------
    df : pd.DataFrame
        Must include 'habitat' column.
    """
    naming_conventions = {
        "coldwatercorals": "cold-water corals",
        "saltmarshes": "saltmarshes",
        "warmwatercorals": "warm-water corals",
        "seagrasses": "seagrasses",
        "mangroves": "mangroves",
        "seamounts": "seamounts",
        "Artificial": "artificial",
        "Forest": "forest",
        "Grassland": "grassland",
        "Wetlands/open water": "wetlands-open-waters",
        "Desert": "desert",
        "Rocky/mountains": "rocky-mountains",
        "Savanna": "savanna",
        "Shrubland": "shrubland",
    }

    df = df.copy()
    df = df[df["habitat"].isin(naming_conventions)]
    df["habitat"] = df["habitat"].apply(lambda x: naming_conventions[x])
    return df


def update_mpatlas_asterisk(df: pd.DataFrame, asterisk: bool = False) -> pd.DataFrame:
    """
    If `asterisk` is True, updates 'protected_area' using values from rows with
    asterisks in 'location' Returns a filtered or modified DataFrame in all cases.

    Parameters
    ----------
    df : pd.DataFrame
        Must include 'location' and 'protected_area'.
    asterisk : bool, default False
        If True, apply updates; if False, drop asterisk rows and return others.
    """

    # Separate rows with and without asterisk
    reg = df[~df["location"].str.contains(r"\*", regex=True)].copy()

    if not asterisk:
        return reg

    star = df[df["location"].str.contains(r"\*", regex=True)].copy()
    star["location"] = star["location"].str.replace("*", "", regex=False)

    for _, row in star.iterrows():
        loc = row["location"]
        value = row["protected_area"]
        reg.loc[reg["location"] == loc, "protected_area"] = value

    return reg


def round_to_list(bounds: pd.DataFrame) -> list[float]:
    """
    Convert a dataframe of geometry.bounds to a rounded list of bounds
    """
    return list(np.round(bounds, decimals=5))

def add_translations(gdf: gpd.GeoDataFrame, translations: pd.DataFrame, gdf_field: str, translation_field:str) -> gpd.GeoDataFrame:
    """
    Add translated names to a GeoDataFrame from a translations DataFrame.
    Parameters
    ----------
    gdf : gpd.GeoDataFrame
        The GeoDataFrame to which translations will be added.
    translations : pd.DataFrame
        DataFrame containing translation data with columns for codes and names.
    gdf_field : str
        The column in gdf to match with the translation codes.
    translation_field : str
        The column in translations containing the codes to match against gdf_field.
    Returns
    -------
    gpd.GeoDataFrame
        The updated GeoDataFrame with added translation columns.
    """
    gdf = gdf.copy()

    gdf = gdf.merge(
        translations[[translation_field, "name", "name_es", "name_fr", "name_pt"]],
        left_on=gdf_field,
        right_on=translation_field,
        how="left",
    )
    return gdf