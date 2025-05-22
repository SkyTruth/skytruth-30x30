import ast
import geopandas as gpd
import pandas as pd


def add_constants(df, const):
    for c in const:
        df[c] = const[c]
    return df


def add_environment(df):
    df = df.copy()
    df["environment"] = df["MARINE"].map({"0": "terrestrial", "1": "marine", "2": "marine"})
    return df


def add_highly_protected_from_fishing_area(df):
    df = df.copy()
    df["highly_protected_area"] = df["lfp5_area"] + df["lfp4_area"]
    return df


def add_highly_protected_from_fishing_percent(df):
    df = df.copy()
    df["pct"] = 100 * df["highly_protected_area"] / df["area"]
    return df


def add_pas_oecm(df):
    df = df.copy()
    df["pas_percent_area"] = 100 * df["pa_coverage"] / df["coverage"]
    df["oecm_percent_area"] = 100 * (1 - df["pa_coverage"] / df["coverage"])
    df["pas_count"] = df["n_pa_poly"] + df["n_pa_point"]
    df["oecm_count"] = df["n_oecm_poly"] + df["n_oecm_point"]
    return df


def add_percentage_protection_mp(df):
    df = df.copy()
    df["percentage"] = df["protected_area"] / df["area"]
    return df


def add_simplified_name(df):
    df = df.copy()
    df["simplified_name"] = df["name"].apply(lambda x: x.split(" - ")[0])
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


def extract_column_dict_str(df, column_dict, column):
    if isinstance(column_dict, dict):
        for d in column_dict:
            df[column_dict[d]] = df[column].apply(
                lambda x: ast.literal_eval(x).get(d) if pd.notnull(x) else None
            )
    if isinstance(column_dict, list):
        for d in column_dict:
            df[d] = df[column].apply(
                lambda x: ast.literal_eval(x).get(d) if pd.notnull(x) else None
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
