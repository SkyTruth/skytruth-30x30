from io import BytesIO
import pandas as pd
import geopandas as gpd
import numpy as np
import gcsfs
import zipfile
from shapely.ops import unary_union
from shapely.validation import make_valid
from tqdm.auto import tqdm

from src.core.commons import load_marine_regions

from src.core.params import (
    MANGROVES_BY_COUNTRY_FILE_NAME,
    GLOBAL_MANGROVE_AREA_FILE_NAME,
    HABITATS_ZIP_FILE_NAME,
    SEAMOUNTS_ZIPFILE_NAME,
    SEAMOUNTS_SHAPEFILE_NAME,
    WDPA_MARINE_FILE_NAME,
    GADM_EEZ_UNION_FILE_NAME,
    EEZ_PARAMS,
    BUCKET,
)

from src.core.processors import clean_geometries

from src.utils.gcp import (
    load_zipped_shapefile_from_gcs,
    read_json_from_gcs,
    read_json_df,
)

from src.utils.geo import get_area_km2


def create_seamounts_subtable(
    seamounts_zipfile_name,
    seamounts_shapefile_name,
    bucket,
    eez_params,
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

    def eez_location(row):
        return row["ISO_TER1"] if isinstance(row["ISO_TER1"], str) else row["ISO_SOV1"]

    if verbose:
        print("loading seamounts")

    seamounts = load_zipped_shapefile_from_gcs(
        seamounts_zipfile_name, bucket, internal_shapefile_path=seamounts_shapefile_name
    )

    if verbose:
        print("loading eezs")
    eez = load_marine_regions(eez_params, bucket)
    eez["location"] = eez.apply(eez_location, axis=1)

    if verbose:
        print("spatially joining seamounts with eezs and marine protected areas")

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
    gadm_eez_union_file_name: str = GADM_EEZ_UNION_FILE_NAME,
    mangroves_by_country_file_name: str = MANGROVES_BY_COUNTRY_FILE_NAME,
    global_mangrove_area_file_name: str = GLOBAL_MANGROVE_AREA_FILE_NAME,
    tolerance: float = 0.001,
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

    if verbose:
        print("loading eez/land union")
    gadm_eez_union_file_name = gadm_eez_union_file_name.replace(".geojson", f"_{tolerance}.geojson")
    country_union = read_json_df(bucket, gadm_eez_union_file_name, verbose=verbose)

    if verbose:
        print("loading pre-processed mangroves")
    mangroves_by_country = read_json_df(bucket, mangroves_by_country_file_name, verbose=True).pipe(
        clean_geometries
    )
    global_mangrove_area = read_json_from_gcs(bucket, global_mangrove_area_file_name)[
        "global_area_km2"
    ]

    if verbose:
        print("getting protected mangrove area by country")
    protected_mangroves = []
    for cnt in tqdm(list(sorted(set(country_union["location"].dropna())))):
        country_geom = country_union[country_union["location"] == cnt].iloc[0].geometry

        country_mangroves = mangroves_by_country[mangroves_by_country["country"] == cnt]
        if len(country_mangroves) > 0:
            mangrove_geom = country_mangroves.iloc[0]["geometry"]
            country_mangrove_area_km2 = country_mangroves.iloc[0]["mangrove_area_km2"]

            country_pas = mpa[mpa["location"] == cnt].make_valid()
            country_pas = gpd.clip(country_pas, country_geom)

            pa_geom = make_valid(unary_union(country_pas.geometry))

            pa_mangrove_area_km2 = get_area_km2(mangrove_geom.intersection(pa_geom))

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


def create_ocean_habitat_subtable(
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

    ocean_habitats = pd.DataFrame()
    for habitat in habitats:
        tmp = dfs[habitat][["ISO3", "protected_area", "total_area"]].copy()
        tmp["environment"] = "marine"
        tmp["habitat"] = habitat
        ocean_habitats = pd.concat((ocean_habitats, tmp))

    if verbose:
        print("Grouping by sovereign country and region")

    ocean_habitats_group = []
    for habitat in habitats:
        df = pd.DataFrame(
            [
                stat
                for loc in combined_regions
                if (stat := get_group_stats(ocean_habitats, loc, combined_regions, habitat))
                is not None
            ]
        )
        ocean_habitats_group.append(df)

    return pd.concat(ocean_habitats_group, axis=0, ignore_index=True)


def dissolve_multipolygons(gdf: gpd.GeoDataFrame, key: str = "WDPAID") -> gpd.GeoDataFrame:
    counts = gdf[key].value_counts()

    singles = gdf[gdf[key].isin(counts[counts == 1].index)]
    multiples = gdf[gdf[key].isin(counts[counts > 1].index)]

    dissolved = multiples.dissolve(by=key)
    dissolved = dissolved.reset_index()
    result = pd.concat([singles, dissolved], ignore_index=True)

    return result


def process_marine_habitats(
    combined_regions,
    gadm_eez_union_file_name: str = GADM_EEZ_UNION_FILE_NAME,
    habitats_zipfile_name: str = HABITATS_ZIP_FILE_NAME,
    seamounts_zipfile_name: str = SEAMOUNTS_ZIPFILE_NAME,
    seamounts_shapefile_name: str = SEAMOUNTS_SHAPEFILE_NAME,
    mangroves_by_country_file_name: str = MANGROVES_BY_COUNTRY_FILE_NAME,
    global_mangrove_area_file_name: str = GLOBAL_MANGROVE_AREA_FILE_NAME,
    marine_pa_file_name: str = WDPA_MARINE_FILE_NAME,
    eez_params: dict = EEZ_PARAMS,
    bucket: str = BUCKET,
    verbose: bool = True,
):
    if verbose:
        print("getting protected areas (this may take a few minutes)")

    marine_protected_areas = read_json_df(bucket, marine_pa_file_name, verbose=verbose)

    if verbose:
        print("dissolving over protected areas")

    marine_protected_areas = (
        dissolve_multipolygons(marine_protected_areas[["ISO3", "WDPAID", "geometry"]])
        .rename(columns={"ISO3": "location", "WDPAID": "wdpa_id"})
        .pipe(clean_geometries)
    )

    if verbose:
        print("getting marine habitats subtable")
    ocean_habitats_subtable = create_ocean_habitat_subtable(
        bucket, habitats_zipfile_name, combined_regions, verbose
    )

    if verbose:
        print("getting seamounts subtable")
    seamounts_subtable = create_seamounts_subtable(
        seamounts_zipfile_name,
        seamounts_shapefile_name,
        bucket,
        eez_params,
        marine_protected_areas,
        combined_regions,
        verbose,
    )

    if verbose:
        print("getting mangroves subtable")

    mangroves_subtable = create_mangroves_subtable(
        marine_protected_areas,
        combined_regions,
        gadm_eez_union_file_name,
        mangroves_by_country_file_name,
        global_mangrove_area_file_name,
    )

    marine_habitats = pd.concat(
        (ocean_habitats_subtable, seamounts_subtable, mangroves_subtable), axis=0
    )

    return marine_habitats
