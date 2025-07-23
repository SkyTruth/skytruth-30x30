import os
from io import BytesIO
import pandas as pd
import geopandas as gpd
import numpy as np
import gcsfs
import zipfile
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
from shapely.validation import make_valid
from tqdm.auto import tqdm

from commons import load_marine_regions, adjust_eez_sovereign, extract_polygons
from params import (
    EEZ_LAND_UNION_PARAMS,
    MANGROVES_BY_COUNTRY_FILE_NAME,
    GLOBAL_MANGROVE_AREA_FILE_NAME,
)

from utils.gcp import (
    load_zipped_shapefile_from_gcs,
    read_json_from_gcs,
    read_json_df,
)

from utils.processors import clean_geometries


verbose = True
PP_API_KEY = os.getenv("PP_API_KEY", "")
BUCKET = os.getenv("BUCKET", "")
PROJECT = os.getenv("PROJECT", "")


def create_seamounts_subtable(
    seamounts_zipfile_name,
    seamounts_shapefile_name,
    bucket,
    eez_params,
    parent_country,
    marine_protected_areas,
    combined_regions,
    verbose,
):
    def get_group_stats(df_eez, df_pa, loc, relations, global_seamount_area, hs_seamount_area):
        if loc == "GLOB":
            df_pa_group = df_pa[["PEAKID", "AREA2D"]].drop_duplicates()
            total_area = global_seamount_area
        else:
            df_pa_group = df_pa[df_pa["location"].isin(relations[loc])][
                ["PEAKID", "AREA2D"]
            ].drop_duplicates()
            if loc == "ABNJ":
                total_area = hs_seamount_area
            else:
                df_eez_group = df_eez[df_eez["location"].isin(relations[loc])][
                    ["PEAKID", "AREA2D"]
                ].drop_duplicates()
                total_area = df_eez_group["AREA2D"].sum()

        protected_area = min(df_pa_group["AREA2D"].sum(), total_area)

        return {
            "location": loc,
            "habitat": "seamounts",
            "environment": "marine",
            "protected_area": protected_area,
            "total_area": total_area,
            # "percent_protected": 100 * protected_area / total_area if total_area > 0 else np.nan,
        }

    if verbose:
        print("loading seamounts")

    seamounts = load_zipped_shapefile_from_gcs(
        seamounts_zipfile_name, bucket, internal_shapefile_path=seamounts_shapefile_name
    )

    if verbose:
        print("loading eezs")
    eez = load_marine_regions(eez_params, bucket)
    eez = adjust_eez_sovereign(eez, parent_country)

    if verbose:
        print("spatially joining seamounts with eezs and marine protected areas")

    global_seamount_area = seamounts["AREA2D"].sum()

    eez_joined = gpd.sjoin(
        seamounts[["PEAKID", "AREA2D", "geometry"]],
        eez[["GEONAME", "location", "geometry"]],
        how="left",
        predicate="intersects",
    )
    high_seas_seamounts = eez_joined[eez_joined["index_right"].isna()]
    eez_seamounts = eez_joined[eez_joined["index_right"].notna()]

    marine_pa_joined = gpd.sjoin(
        seamounts[["PEAKID", "AREA2D", "geometry"]],
        marine_protected_areas[["wdpa_id", "location", "geometry"]],
        how="left",
        predicate="intersects",
    )
    marine_pa_seamounts = marine_pa_joined[marine_pa_joined["index_right"].notna()]

    global_seamount_area = seamounts["AREA2D"].sum()
    hs_seamount_area = high_seas_seamounts["AREA2D"].sum()

    return pd.DataFrame(
        [
            get_group_stats(
                eez_seamounts,
                marine_pa_seamounts,
                cnt,
                combined_regions,
                global_seamount_area,
                hs_seamount_area,
            )
            for cnt in combined_regions
        ]
    )


def create_mangroves_subtable(
    mpa,
    combined_regions,
    eez_land_union_params: dict = EEZ_LAND_UNION_PARAMS,
    mangroves_by_country_file_name: str = MANGROVES_BY_COUNTRY_FILE_NAME,
    global_mangrove_area_file_name: str = GLOBAL_MANGROVE_AREA_FILE_NAME,
    bucket: str = BUCKET,
    verbose: bool = True,
):
    def get_group_stats(df, loc, relations, global_mangrove_area):
        if loc == "GLOB":
            df_group = df
            total_area = global_mangrove_area
        else:
            df_group = df[df["location"].isin(relations[loc])]

            # Ensure numeric conversion
            total_area = df_group["total_mangrove_area_km2"].sum()

        protected_area = df_group["protected_mangrove_area_km2"].sum()

        return {
            "location": loc,
            "habitat": "mangroves",
            "environment": "marine",
            "protected_area": protected_area,
            "total_area": total_area,
            # "percent_protected": 100 * protected_area / total_area if total_area else None,
        }

    # TODO: using eez/land union instead of eez, which may miss some coastal regions where
    # mangroves are. However, several regions are listed under ISO_TER1 = None, most notably,
    # Alaska, which doesn't matter for mangroves, but there are also tropical areas missing
    # including Hawaii. Need to find a way to stick them together
    if verbose:
        print("loading eez/land union")
    country_union = (
        load_marine_regions(eez_land_union_params, bucket)[["ISO_TER1", "geometry"]]
        .rename(columns={"ISO_TER1": "location"})
        .pipe(clean_geometries)
    )

    if verbose:
        print("loading pre-processed mangroves")
    mangroves_by_country = read_json_df(bucket, mangroves_by_country_file_name, verbose=True).pipe(
        clean_geometries
    )
    global_mangrove_area = read_json_from_gcs(bucket, global_mangrove_area_file_name)["global_area"]

    if verbose:
        print("Updating CRS to EPSG:6933 (equal-area for geometry ops)")
    crs = "EPSG:6933"
    country_union_reproj = country_union.to_crs(crs).pipe(clean_geometries)
    mpa_reproj = mpa.to_crs(crs).pipe(clean_geometries)

    if verbose:
        print("getting protected mangrove area by country")
    protected_mangroves = []
    for cnt in tqdm(list(sorted(set(country_union_reproj["location"].dropna())))):
        country_geom = make_valid(
            extract_polygons(
                unary_union(country_union_reproj[country_union_reproj["location"] == cnt].geometry)
            )
        )

        country_mangroves = mangroves_by_country[mangroves_by_country["country"] == cnt]
        if len(country_mangroves) > 0:
            mangrove_geom = country_mangroves.iloc[0]["geometry"]
            country_mangrove_area_km2 = country_mangroves.iloc[0]["mangrove_area_km2"]

            # Get MPA features in country and clip
            country_pas = mpa_reproj[mpa_reproj["location"] == cnt]
            country_pas = gpd.clip(country_pas, country_geom)
            country_pas = country_pas[
                ~country_pas.geometry.is_empty & country_pas.geometry.is_valid
            ]
            geom_list = [g for g in country_pas.geometry if isinstance(g, (Polygon, MultiPolygon))]

            if not geom_list:
                pa_geom = None
            else:
                pa_geom = make_valid(unary_union(geom_list))
            pa_geom = make_valid(unary_union(country_pas.geometry))

            pa_mangrove_area_km2 = mangrove_geom.intersection(pa_geom).area / 1e6

            protected_mangroves.append(
                {
                    "location": cnt,
                    "total_mangrove_area_km2": country_mangrove_area_km2,
                    "protected_mangrove_area_km2": pa_mangrove_area_km2,
                }
            )

    protected_mangroves = pd.DataFrame(protected_mangroves)
    protected_mangroves["percent_protected"] = (
        100
        * protected_mangroves["protected_mangrove_area_km2"]
        / protected_mangroves["total_mangrove_area_km2"]
    )

    mangrove_habitat = pd.DataFrame(
        [
            stat
            for loc in combined_regions
            if (
                stat := get_group_stats(
                    protected_mangroves, loc, combined_regions, global_mangrove_area
                )
            )
            is not None
        ]
    )

    return mangrove_habitat[mangrove_habitat["total_area"] > 0]


def create_marine_habitat_subtable(
    bucket: str, habitats_file_name: str, combined_regions: dict, verbose: bool
):
    def get_group_stats(df, loc, relations, habitat):
        if loc == "GLOB":
            df_group = df[df["habitat"] == habitat].replace("-", np.nan)
        else:
            df_group = df[(df["ISO3"].isin(relations[loc])) & (df["habitat"] == habitat)].replace(
                "-", np.nan
            )

        # Ensure numeric conversion
        df_group["total_area"] = pd.to_numeric(df_group["total_area"], errors="coerce")
        total_area = df_group["total_area"].sum()

        df_group["protected_area"] = pd.to_numeric(df_group["protected_area"], errors="coerce")
        protected_area = df_group["protected_area"].sum()

        return {
            "location": loc,
            "habitat": habitat,
            "environment": "marine",
            "protected_area": protected_area,
            "total_area": total_area,
            # "percent_protected": 100 * protected_area / total_area if total_area else None,
        }

    habitats = ["warmwatercorals", "coldwatercorals", "seagrasses", "saltmarshes"]

    if verbose:
        print("downloading habitats zipfile into memory")

    fs = gcsfs.GCSFileSystem()
    with fs.open(f"gs://{bucket}/{habitats_file_name}", "rb") as f:
        zip_bytes = f.read()

    dfs = {}
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        for name in habitats:
            with zf.open(f"Ocean+HabitatsDownload_Global/{name}.csv") as csv_file:
                dfs[name] = pd.read_csv(csv_file)

    if verbose:
        print("generating habitats table")

    marine_habitats = pd.DataFrame()
    for habitat in habitats:
        tmp = dfs[habitat][["ISO3", "protected_area", "total_area"]].copy()
        tmp["environment"] = "marine"
        tmp["habitat"] = habitat
        marine_habitats = pd.concat((marine_habitats, tmp))

    if verbose:
        print("Grouping by sovereign country and region")

    marine_habitats_group = []
    for habitat in habitats:
        df = pd.DataFrame(
            [
                stat
                for loc in combined_regions
                if (stat := get_group_stats(marine_habitats, loc, combined_regions, habitat))
                is not None
            ]
        )
        marine_habitats_group.append(df)

    return pd.concat(marine_habitats_group, axis=0, ignore_index=True)
