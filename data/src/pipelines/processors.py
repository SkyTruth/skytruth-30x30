from pathlib import Path
from typing import Callable, List, Union, Dict
import pandas as pd
import geopandas as gpd
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.validation import make_valid
import json

import asyncio
from tqdm.asyncio import tqdm

from data_commons.loader import (
    load_regions,
    load_locations_code,
    load_iso_mapping,
    load_country_mapping,
)
from pipelines.utils import background


## DATAFRAME PROCESSORS
def filter_by_methodology(df: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    mask = (df["STATUS"] != "Not Reported") & ~(df["DESIG_ENG"].str.contains("MAB", case=False))
    return df[mask].reset_index(drop=True)


def filter_by_terrestrial(gdf):
    return gdf[gdf["MARINE"].astype(int) != 2].reset_index(drop=True)


def filter_by_exluding_propossed_mpas(df: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    mask = df["STATUS"] != "Proposed"
    return df[mask].reset_index(drop=True)


def set_wdpa_id(df: pd.DataFrame) -> pd.DataFrame:
    """Set the wdpa_id column to the value of wdpa_pid if it is not None, otherwise set it to the value of wdpa_id.

    Args:
        df (pd.DataFrame): The DataFrame to process.

    Returns:
        pd.DataFrame: The processed DataFrame.

    """
    return df.assign(
        wdpa_id=df["wdpa_pid"]
        .replace(to_replace=[None, "None"], value=np.nan)
        .fillna(df["wdpa_id"])
    )


def protection_level(df: pd.DataFrame) -> pd.DataFrame:
    """
    Set the protection_level column to "fully or highly protected" if the protection_mpaguide_level column is "full" or "high",
    otherwise set it to "less protected or unknown".
    """
    return df.assign(
        protection_level=np.where(
            df["protection_mpaguide_level"].isin(["full", "high"]),
            "fully or highly protected",
            "less protected or unknown",
        ),
        expand=False,
    )


def mpaatlas_filter_stablishment(df: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    return df[(df["establishm"].isin(["actively managed", "implemented"]))].copy()


def status(df: pd.DataFrame | gpd.GeoDataFrame) -> pd.DataFrame | gpd.GeoDataFrame:
    return df.replace(
        {"establishment_stage": "proposed/committed"},
        {"establishment_stage": "proposed or committed"},
        regex=True,
    )


def create_year(df: pd.DataFrame | gpd.GeoDataFrame) -> pd.DataFrame | gpd.GeoDataFrame:
    df["proposed_date"] = df["proposed_date"].str[:4].astype("Int64")
    df["designated_date"] = df["designated_date"].str[:4].astype("Int64")
    df["implemented_date"] = df["implemented_date"].str[:4].astype("Int64")
    year = (
        df[["proposed_date", "designated_date", "implemented_date"]]
        .max(axis=1)
        .fillna(0)
        .astype(int)
    )
    year = np.where(
        year == 0, np.nan, year  # type: ignore
    )  # Use numpy.where to conditionally replace 0 with pd.NaT
    return df.assign(year=year)


# def create_year(df: pd.DataFrame | gpd.GeoDataFrame) -> pd.DataFrame | gpd.GeoDataFrame:
#     df["proposed_date"] = df["proposed_date"].str[:4].astype("Int64")
#     df["designated_date"] = df["designated_date"].str[:4].astype("Int64")
#     df["implemented_date"] = df["implemented_date"].str[:4].astype("Int64")
#     return df.assign(
#         year=df[["proposed_date", "designated_date", "implemented_date"]]
#         .max(axis=1)
#         .fillna(0)
#         .astype(int)
#         .replace(0, pd.NaT)
#     )


def split_by_year(
    gdf: gpd.GeoDataFrame, year_col: str = "STATUS_YR", year_val: int = 2010
) -> List[gpd.GeoDataFrame]:
    """Split data by year. relevant for MPA data.(coverage indicator)"""
    prior_2010 = (
        gdf[gdf[year_col] <= year_val]
        .dissolve(
            by=["PA_DEF", "iso_3"],
            aggfunc={
                "PA_DEF": "count",
            },
        )
        .assign(year=2010)
        .rename(columns={"PA_DEF": "protectedAreasCount"})
        .reset_index()
    )
    after_2010 = (
        gdf[gdf["STATUS_YR"] > 2010][["iso_3", "STATUS_YR", "PA_DEF", "geometry"]]
        .assign(protectedAreasCount=1)
        .rename(columns={"STATUS_YR": "year"})
    )
    return [prior_2010, after_2010]


def get_mpas(df: pd.DataFrame | gpd.GeoDataFrame) -> pd.DataFrame | gpd.GeoDataFrame:
    mask1 = df["wdpa_id"].notna()
    mask2 = df["wdpa_id"] != "0"
    return df[mask1][mask2].reset_index()


def set_fps_classes(df: pd.DataFrame | gpd.GeoDataFrame) -> pd.DataFrame | gpd.GeoDataFrame:
    fps_classes = {1: "less", 2: "less", 3: "moderately", 4: "highly", 5: "highly"}
    return df.assign(
        FPS_cat=df["removal_of_marine_life_is_prohibited"].map(fps_classes),
        expand=False,
    )


### Iso processors
def set_location_iso(df: pd.DataFrame | gpd.GeoDataFrame) -> pd.DataFrame | gpd.GeoDataFrame:
    country_map = load_country_mapping()

    def get_parent_iso(country):
        try:
            if country:
                return country_map.get(country, np.nan)
            else:
                return "FRA"
        except ValueError:
            return np.nan

    return df.assign(iso=df.country.apply(get_parent_iso))


def assign_iso3(df: pd.DataFrame | gpd.GeoDataFrame) -> pd.DataFrame | gpd.GeoDataFrame:
    """Assign ISO3 code. specific for Mpa data"""

    def set_iso3(row):
        """relevant for MPA data."""
        return (
            row["PARENT_ISO"]
            if (
                row["POL_TYPE"] == "200NM"
                and row["PARENT_ISO"] != row["iso"]
                and len(row["PARENT_ISO"]) <= 4
            )
            else row["iso"]
        )

    return df.assign(iso_3=df.apply(lambda row: set_iso3(row), axis=1))


def add_location_iso(
    df: pd.DataFrame | gpd.GeoDataFrame, iso_cols: List[str] = ["ISO_SOV1", "ISO_SOV2", "ISO_SOV3"]
) -> pd.DataFrame | gpd.GeoDataFrame:
    # Create new column "iso" that has the field "ISO_SOV1" for all rows except those in which ISO_SOV2 and ISO_SOV3 are not null. In such cases concatenate ISO_SOV1, ISO_SOV2 and ISO_SOV3
    def reduce_iso(row):
        filtered_isos = filter(lambda iso: isinstance(iso, str), row)

        return ";".join(list(filtered_isos))

    return df.assign(iso=lambda row: row[iso_cols].apply(reduce_iso, axis=1))


def add_region_iso(
    df: pd.DataFrame | gpd.GeoDataFrame, iso_column
) -> pd.DataFrame | gpd.GeoDataFrame:
    regions = load_regions()

    def find_region_iso(iso: str) -> Union[str, None]:
        filtered_regions = list(filter(lambda x: iso in x["country_iso_3s"], regions.get("data")))
        return filtered_regions[0]["region_iso"] if len(filtered_regions) > 0 else None

    return df.assign(region=lambda row: row[iso_column].apply(find_region_iso))


def add_location_name(df: pd.DataFrame | gpd.GeoDataFrame) -> pd.DataFrame | gpd.GeoDataFrame:
    iso_map = load_iso_mapping()

    def get_name(iso):
        test = iso_map.get(iso, np.nan)
        return test

    return df.assign(name=df.iso.apply(get_name))


def add_groups_and_members(df: pd.DataFrame | gpd.GeoDataFrame) -> pd.DataFrame | gpd.GeoDataFrame:
    return df.assign(
        groups=lambda row: row[["region", "location_type"]].apply(
            lambda x: (np.where(df.iso == x["region"])[0] + 1).tolist()
            if x["location_type"] == "country"
            else [],
            axis=1,
        )
    )


## Geometry processors


def clean_geometries(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf.geometry = gdf.geometry.make_valid()
    return gdf


def collection_to_multipolygon(geometry_collection):
    """Convert collection of polygons to multipolygon."""
    print(type(geometry_collection.geoms))
    geom_list = [
        geom
        for geom in geometry_collection.geoms
        if geom.geom_type == "Polygon" or geom.geom_type == "MultiPolygon"
    ]
    return unary_union(geom_list)


def repair_geometry(geom):
    if not geom:
        return Polygon()
    elif not geom.is_valid:
        geom = collection_to_multipolygon(make_valid(geom.buffer(0.0)))
    elif geom.geom_type == "GeometryCollection":
        geom = collection_to_multipolygon(geom)
    return geom


def add_envelope(df: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    return df.assign(geometry=lambda row: row["geometry"].envelope)


def add_bbox(df: gpd.GeoDataFrame, col_name: str = "bounds") -> gpd.GeoDataFrame:
    return df.assign(**{col_name: df.geometry.bounds.apply(list, axis=1)})


def calculate_area(
    df: gpd.GeoDataFrame, output_area_column="area_km2", round: None | int = 2
) -> gpd.GeoDataFrame:
    col = df.geometry.to_crs("ESRI:53009").area / 1e6  # convert to km2
    if round:
        col = col.round(round)
    return df.assign(**{output_area_column: col})


def create_buffer(df: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    def calculate_radius(rep_area: float) -> float:
        return ((rep_area * 1000) / 3.14159265358979323846) ** 0.5

    df["geometry"] = df.to_crs("ESRI:54009").apply(
        lambda row: row.geometry.buffer(calculate_radius(row["REP_AREA"])),
        axis=1,
    )
    return df.to_crs("EPSG:4326").copy()


def transform_points(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if "MultiPoint" in gdf.geometry.geom_type.values:
        filtered_gdf = gdf[gdf["REP_AREA"] > 0].copy()
        return filtered_gdf.pipe(create_buffer)
    else:
        return gdf


### Spatial joins and dissolves

def get_matches(geom: Polygon, df: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Get matches."""
    candidates = df.iloc[df.sindex.intersection(geom.bounds)]
    if len(candidates) > 0:
        candidates = candidates[candidates.intersects(geom)]
    return candidates


def arrange_dimensions(
    geodataframe_a: gpd.GeoDataFrame, geodataframe_b: gpd.GeoDataFrame
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Arrange dimensions."""
    return (
        (geodataframe_a, geodataframe_b)
        if geodataframe_a.shape[0] < geodataframe_b.shape[0]
        else (geodataframe_b, geodataframe_a)
    )


## TODO properly type this
## TODO: generalize the next operations to make them more reusable
@background
def spatial_join_chunk(row_small, df_large, pbar):
    test_row = gpd.GeoDataFrame([row_small], crs=df_large.crs)
    candidates = get_matches(row_small.geometry, df_large.geometry)
    if len(candidates) > 0:
        subset = df_large.loc[candidates.index]

        result = subset.sjoin(test_row, how="inner").clip(test_row.geometry).reset_index(drop=True)
        result.geometry = result.geometry.apply(repair_geometry)
    else:
        result = gpd.GeoDataFrame(columns=test_row.columns)
    pbar.update(1)
    return result


async def spatial_join(
    geodataframe_a: gpd.GeoDataFrame, geodataframe_b: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    """Create spatial join between two GeoDataFrames."""
    # we build the spatial index for the larger GeoDataFrame
    smaller_dim, larger_dim = arrange_dimensions(geodataframe_a, geodataframe_b)
    with tqdm(total=smaller_dim.shape[0]) as pbar:  # we create a progress bar
        new_df = await asyncio.gather(
            *(
                spatial_join_chunk(row, larger_dim, pbar)
                for row in smaller_dim.itertuples(index=False)
            )
        )
    return gpd.GeoDataFrame(pd.concat(new_df, ignore_index=True), crs=smaller_dim.crs)


@background
def difference(geom_col_value, df, pbar):
    candidates = get_matches(geom_col_value, df)
    if len(candidates) > 0:
        geometry = repair_geometry(geom_col_value.difference(candidates.geometry.unary_union))
    else:
        geometry = geom_col_value
    pbar.update(1)

    return geometry


async def create_difference(geodataframe1, geodataframe2):
    """Create difference between two GeoDataFrames."""
    # we build the spatial index for the larger GeoDataFrame

    result = geodataframe1.copy()
    with tqdm(total=result.shape[0]) as pbar:  # we create a progress bar
        result["geometry"] = await asyncio.gather(
            *(difference(val, geodataframe2[["geometry"]], pbar) for val in result["geometry"])
        )

    return result


@background
def spatial_dissolve_chunk(i, gdf, pbar, _by, _aggfunc):
    result = (
        gdf[gdf["year"] <= i]
        .dissolve(by=_by, aggfunc=_aggfunc)
        .assign(year=i)
        .reset_index()
        .pipe(calculate_area, "area", None)
        .drop(columns=["geometry"])
    )
    pbar.update(1)
    return result


## Calculations


def calculate_global_area(
    df: pd.DataFrame,
    gby_col: list,
    agg_ops: Dict[str, str] = {"area_km2": "sum"},
    iso_column="location_i",
) -> pd.DataFrame:
    global_area = df.groupby([*gby_col]).agg(agg_ops).reset_index().assign(**{iso_column: "GLOB"})
    return pd.concat([global_area, df], ignore_index=True)


def calculate_eez_area(df: pd.DataFrame) -> pd.DataFrame:
    glob = gpd.GeoDataFrame(
        {
            "iso": "GLOB",
            "AREA_KM2": 361000000,
            "location_type": "worldwide",
            "region": np.nan,
            "geometry": gpd.GeoSeries([gpd.GeoSeries(df["geometry"]).unary_union]),
        },
        crs="EPSG:4326",
    )
    mask = df.iso == "ABNJ"
    marine_areas = (
        df[~mask]
        .dissolve(by=["iso", "region"], aggfunc={"AREA_KM2": "sum"})
        .reset_index()
        .assign(location_type="country")
    )
    regions_areas = (
        df[~mask]
        .dissolve(by=["region"], aggfunc={"AREA_KM2": "sum"})
        .reset_index()
        .rename(columns={"region": "iso"})
        .assign(location_type="region")
    )
    highseas = (
        df[mask]
        .dissolve(by=["iso"], aggfunc={"AREA_KM2": "sum"})
        .reset_index()
        .assign(location_type="highseas")
    )
    result = (
        pd.concat(
            [
                glob,
                highseas,
                regions_areas,
                marine_areas,
            ],
            ignore_index=True,
        )
        .dropna(subset=["iso"])
        .reset_index(drop=True)
    )
    result.index = result.index + 1
    result.index.name = "id"

    return result.assign(id=result.index)


# TODO: check if this is still needed as we also have calculate_global_area
def calculate_global_coverage(df: pd.DataFrame) -> pd.DataFrame:
    global_area = (
        df.groupby(["PA_DEF", "year", "PARENT_ISO"])
        .agg(
            {
                "cumSumProt": "sum",
                "protectedA": "first",
            }
        )
        .reset_index()
        .groupby(["PA_DEF", "year"])
        .sum()
        .reset_index()
        .assign(PARENT_ISO="GLOB")
    )
    return pd.concat(
        [
            df.replace(
                {
                    "PARENT_ISO": {
                        "COK": "NZL",
                        "IOT": "GBR",
                        "NIU": "NZL",
                        "SHN": "GBR",
                        "SJM": "NOR",
                        "UMI": "USA",
                    }
                }
            ),
            global_area,
        ],
        ignore_index=True,
    )


def calculate_stats(
    df: pd.DataFrame, gby_col: list, iso_column: str, ops: dict[str, str] = {"area_km2": "sum"}
) -> pd.DataFrame:
    regions = (
        df.groupby([*gby_col, "region"])
        .agg(ops)
        .reset_index()
        .rename(columns={"region": iso_column})
    )

    return pd.concat(
        [
            regions,
            df.groupby([*gby_col, iso_column]).agg(ops).reset_index(),
        ],
        ignore_index=True,
    )


def calculate_stats_cov(df: pd.DataFrame, gby_col: list, iso_column: str):
    return calculate_stats(df, gby_col, iso_column, {"area": "sum", "protectedAreasCount": "sum"})


def coverage_stats(
    df: pd.DataFrame,
    area_col: str = "area",
    sort_vals: List[str] = ["iso_3", "year", "PA_DEF"],
) -> pd.DataFrame:
    """only relevant to get the coverage numbers for mpa"""
    return df.assign(
        cumSumProtectedArea=df[area_col].round(2),
        protectedArea=(
            df.sort_values(by=sort_vals)[area_col]
            - df.sort_values(by=sort_vals)
            .groupby(sort_vals)[area_col]
            .shift(-1, fill_value=0)
            .reset_index(drop=True)
        ).round(2),
    )


# # TODO: check if this is still needed as we also have calculate_stats
# def calculate_region_coverage(df: pd.DataFrame):
#     regions = (
#         df.pipe(add_region_iso)
#         .groupby(["PA_DEF", "region", "year"])
#         .agg({"cumSumProt": "sum", "protectedA": "sum"})
#         .reset_index()
#     )
#     return pd.concat(
#         [df, regions.assign(PARENT_ISO=lambda row: row["region"]).drop(columns="region")],
#         ignore_index=True,
#     )


## TODO: check as this is a component of calculate_stats
def aggregate_area(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby(["PA_DEF", "PARENT_ISO", "year"])
        .agg({"cumSumProt": "sum", "protectedA": "first"})
        .reset_index()
    )


async def process_mpa_data(
    gdf: gpd.GeoDataFrame, loop: list[int], by: list[str], aggfunc: dict
) -> pd.DataFrame:
    """process protected planet data. relevant for acc coverage extent by year indicator."""
    # we split the data by =< year so we can acumulate the coverage
    base = split_by_year(gdf)

    result_to_iter = pd.concat(base, ignore_index=True).copy()

    with tqdm(total=len(loop)) as pbar:  # we create a progress bar
        new_df = await asyncio.gather(
            *(spatial_dissolve_chunk(year, result_to_iter, pbar, by, aggfunc) for year in loop)
        )
    return pd.concat(
        [base[0].pipe(calculate_area, "area", None).drop(columns=["geometry"]), *new_df],
        ignore_index=True,
    )


def process_mpaatlas_data(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    return (
        gdf.dissolve(by=["protecti_1", "location_i"], aggfunc={"name": "count"})
        .reset_index()
        .pipe(calculate_area, "area_km2", None)
        .drop(columns=["geometry"])
    )


## MISC


def fix_monaco(df: pd.DataFrame, iso_column="location_i", area_column="area_km2") -> pd.DataFrame:
    df.loc[df[iso_column] == "MCO", area_column] = 288
    return df


def separate_parent_iso(df: pd.DataFrame, iso_column="location_i", separator=";") -> pd.DataFrame:
    df[iso_column] = (
        df[iso_column].str.replace(" ", "").str.replace(":", separator).str.split(separator)
    )
    return df.explode(iso_column)


# TODO: check if this is still needed as we also have separate_parent_iso
def expand_multiple_locations(df: pd.DataFrame) -> pd.DataFrame:
    mask = df["iso"].str.contains(";", na=False)
    split_rows = df[mask].copy()
    split_rows["iso"] = split_rows["iso"].str.split(";")
    split_rows = split_rows.explode("iso")
    return pd.concat([df[~mask], split_rows], ignore_index=True)


def filter_location(df: pd.DataFrame) -> pd.DataFrame:
    return df[~df.location.isna()]


def extract_wdpaid_mpaatlas(gdf):
    return gdf.assign(wdpaid=gdf.wdpa_id.str.extract(r"(\d+(?:_\d+)*)").astype("Int64"))


def columns_to_lower(gdf):
    gdf.columns = gdf.columns.str.lower()
    return gdf


def define_is_child(
    gdf: pd.DataFrame | gpd.GeoDataFrame,
    gby: str = "wdpaid",
    sort_by: dict[str, bool] = {"wdpa_pid": True, "wdpa_pid": True, "source": False},
    col_name: str = "is_child",
) -> pd.DataFrame | gpd.GeoDataFrame:
    return gdf.assign(
        **{
            col_name: np.where(
                gdf.index.isin(
                    gdf.sort_values(by=list(sort_by.keys()), ascending=list(sort_by.values()))
                    .groupby(gby)
                    .nth(slice(1, None))
                    .index
                ),
                True,
                False,
            )
        }
    )


def define_childs_ids(group) -> tuple:

    if len(group) > 1:
        return (
            group[group.is_child.eq(False)].index.values[0],
            group[group.is_child.eq(True)].index.tolist(),
        )
    else:
        return pd.NA, pd.NA


def add_child_parent_relationship(
    df: pd.DataFrame | gpd.GeoDataFrame,
    gby: str = "wdpaid",
    cols: list = ["wdpaid", "wdpa_pid", "is_child", "data_source"],
) -> pd.DataFrame | gpd.GeoDataFrame:
    groups: pd.Series = df.groupby(gby)[cols].apply(define_childs_ids)
    df["children"] = (
        pd.DataFrame([[a, b] for a, b in groups.values], columns=["parent", "children"])
        .dropna(subset=["parent"])
        .set_index("parent")
    )

    return df


def set_child_id(
    df: pd.DataFrame | gpd.GeoDataFrame, columns: list[str] = ["wdpa_pid", "mpa_zone_i"]
) -> pd.DataFrame | gpd.GeoDataFrame:
    return df.assign(child_id=df[columns].bfill(axis=1)[columns[0]])


## OUTPUT FUNCTIONS


def output(
    df: pd.DataFrame, iso_column: str, rep_d: dict, rename: Dict[str, str], drop_cols: List[str]
) -> pd.DataFrame:
    """Output function formatter for the data.

    Args:
        df (pd.DataFrame): The DataFrame to process.
        iso_column (str): The column containing the ISO codes.
        rep_d (dict): A dictionary of values to replace.
        rename (Dict[str, str]): A dictionary of columns to rename.
        drop_cols (List[str]): A list of columns to drop.

    Returns:
        pd.DataFrame: The processed DataFrame.
    """
    if iso_column:
        locations_code = load_locations_code()
        df = df.join(locations_code.set_index("code"), on=iso_column, how="left")
    return (
        df.replace(rep_d)
        .rename(columns=rename)
        .drop(columns=drop_cols)
        .assign(
            id=df.index + 1,
        )
        .set_index("id")
    )


# TODO: type this better
def batch_export(
    df: pd.DataFrame,
    batch_size: int,
    schema: Callable[[pd.DataFrame], pd.DataFrame],
    folder: Path,
    filename: str,
    format: str = "csv",
    strapi_colection: str = "mpa",
) -> None:
    prev = 0
    if format == "csv":
        for idx, size in enumerate(range(batch_size, len(df.index) + batch_size, batch_size)):
            schema(df[(df.index > prev) & (df.index < size)]).to_csv(
                folder.joinpath(f"{filename}_{idx}.csv"),
                index=True,
                encoding="utf-8",
            )
            prev = size
    elif format == "json":
        df = df.assign(id=df.index)
        for idx, size in enumerate(range(batch_size, len(df.index) + batch_size, batch_size)):
            output_locations = {
                "version": 2,
                "data": {
                    f"api::{strapi_colection}.{strapi_colection}": schema(
                        df[(df.index > prev) & (df.index < size)]
                    ).to_dict(orient="index", index=True)
                },
            }
            with open(folder.joinpath(f"{filename}_{idx}.json"), "w") as f:
                json.dump(output_locations, f)
            prev = size
    else:
        raise ValueError("Invalid format")
