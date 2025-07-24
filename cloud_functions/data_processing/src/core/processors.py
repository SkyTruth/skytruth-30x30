import ast
import geopandas as gpd
import pandas as pd
from shapely.geometry import MultiPolygon, Polygon


def add_constants(df, const):
    for c in const:
        df[c] = const[c]
    return df


def add_environment(df):
    df = df.copy()
    df["environment"] = df["MARINE"].map({"0": "terrestrial", "1": "marine", "2": "marine"})
    return df


def add_protected_from_fishing_area(df, fishing_protection_levels):
    df = df.copy()

    for level in fishing_protection_levels:
        df[f"{level}_protected_area"] = df[fishing_protection_levels[level]].sum(axis=1)
    return df


def add_protected_from_fishing_percent(df, fishing_protection_levels):
    df = df.copy()
    for level in fishing_protection_levels:
        df[f"{level}_pct"] = 100 * df[f"{level}_protected_area"] / df["area"]
    return df


def add_parent(df, parent_dict, location_name="location"):
    df = df.copy()
    df["parent_id"] = df[location_name].apply(lambda x: parent_dict[x] if x in parent_dict else x)
    return df


def add_pas_oecm(df):
    df = df.copy()
    df["pas_percent_area"] = 100 * df["pa_coverage"] / df["coverage"]
    df["oecm_percent_area"] = 100 * (1 - df["pa_coverage"] / df["coverage"])
    df["pas_count"] = df["protected_area_polygon_count"] + df["protected_area_point_count"]
    df["oecm_count"] = df["oecm_polygon_count"] + df["oecm_point_count"]
    return df


def add_percentage_protection_mp(df):
    df = df.copy()
    df["percentage"] = df["protected_area"] / df["area"]
    return df


def add_year(df):
    df = df.copy()
    df["year"] = df["designated_date"].apply(lambda x: int(x.split("-")[0]))
    return df


def calculate_area(
    df: gpd.GeoDataFrame, output_area_column="area_km2", round: None | int = 2
) -> gpd.GeoDataFrame:
    col = df.geometry.to_crs("ESRI:53009").area / 1e6  # convert to km2
    if round:
        col = col.round(round)
    return df.assign(**{output_area_column: col})


def clean_geometries(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf.geometry = gdf.geometry.make_valid()
    return gdf


def convert_poly_to_multi(df):
    df = df.copy()
    df["geometry"] = df["geometry"].apply(
        lambda x: MultiPolygon([x])
        if isinstance(x, Polygon)
        else x
        if isinstance(x, MultiPolygon)
        else x
    )
    return df


def convert_type(df, conversion):
    df = df.copy()
    for col in conversion:
        for con in conversion[col]:
            df[col] = df[col].astype(con)

    return df


def safe_literal_eval(x):
    try:
        return ast.literal_eval(x) if isinstance(x, str) else None
    except (ValueError, SyntaxError):
        return None


def extract_column_dict_str(df, column_dict, column):
    df = df.copy()
    parsed_col = df[column].apply(safe_literal_eval)

    if isinstance(column_dict, dict):
        for d in column_dict:
            df[column_dict[d]] = parsed_col.apply(
                lambda x: x.get(d) if isinstance(x, dict) else None
            )

    elif isinstance(column_dict, list):
        for d in column_dict:
            df[d] = parsed_col.apply(lambda x: x.get(d) if isinstance(x, dict) else None)

    return df


def fp_location(df):
    df = df.copy()
    df["location"] = df.apply(
        lambda x: x["iso_ter"]
        if isinstance(x["iso_ter"], str) and x["iso_ter"] != ""
        else x["iso_sov"],
        axis=1,
    )
    return df


def get_highly_protected_from_fishing_area(df):
    return df.groupby("location")[["area", "highly_protected_area"]].sum().reset_index()


def remove_columns(df, columns):
    df = df.drop(columns=columns)
    return df


def remove_non_designated_m(df):
    return df[df["designated_date"].notnull()]


def remove_non_designated_p(df):
    return df[df["STATUS"] == "Designated"]


def rename_habitats(df):
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
    asterisks in 'location'Returns a filtered or modified DataFrame in all cases.
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
