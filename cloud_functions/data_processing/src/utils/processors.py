import geopandas as gpd


def add_constants(df, const):
    for c in const:
        df[c] = const[c]
    return df


def add_environment(df):
    df["environment"] = df["MARINE"].map({"0": "terrestrial", "1": "marine", "2": "marine"})
    return df


def add_simplified_name(df):
    df["simplified_name"] = df["name"].apply(lambda x: x.split(" - ")[0])
    return df


def add_year(df):
    df["year"] = df["designated_date"].apply(lambda x: int(x.split("-")[0]))
    return df


def calculate_area(
    df: gpd.GeoDataFrame, output_area_column="area_km2", round: None | int = 2
) -> gpd.GeoDataFrame:
    col = df.geometry.to_crs("ESRI:53009").area / 1e6  # convert to km2
    if round:
        col = col.round(round)
    return df.assign(**{output_area_column: col})


def remove_columns(df, columns):
    df = df.drop(columns=columns)
    return df


def remove_non_designated_m(df):
    return df[df["designated_date"].notnull()]


def remove_non_designated_p(df):
    return df[df["STATUS"] == "Designated"]
