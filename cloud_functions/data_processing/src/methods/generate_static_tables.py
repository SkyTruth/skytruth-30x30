import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.ops import unary_union

from src.core.land_cover_params import marine_tolerance, terrestrial_tolerance
from src.core.params import (
    BUCKET,
    EEZ_FILE_NAME,
    GADM_FILE_NAME,
    LOCATIONS_FILE_NAME,
    LOCATIONS_TRANSLATED_FILE_NAME,
    REGIONS_FILE_NAME,
    RELATED_COUNTRIES_FILE_NAME,
)
from src.core.processors import round_to_list
from src.utils.gcp import read_dataframe, read_json_df, read_json_from_gcs, upload_dataframe
from src.utils.geo import get_area_km2


def generate_locations_table(
    eez_file_name: str = EEZ_FILE_NAME,
    gadm_file_name: str = GADM_FILE_NAME,
    output_file_name: str = LOCATIONS_FILE_NAME,
    related_countries_file_name: str = RELATED_COUNTRIES_FILE_NAME,
    regions_file_name: str = REGIONS_FILE_NAME,
    translation_file_name: str = LOCATIONS_TRANSLATED_FILE_NAME,
    bucket: str = BUCKET,
    verbose: bool = True,
):
    if verbose:
        print("Generating locations table")

    eez_file = eez_file_name.replace(".geojson", f"_{marine_tolerance}.geojson")
    gadm_file = gadm_file_name.replace(".geojson", f"_{terrestrial_tolerance}.geojson")

    eez = read_json_df(bucket_name=bucket, filename=eez_file, verbose=verbose)
    gadm = read_json_df(bucket_name=bucket, filename=gadm_file, verbose=verbose)

    related_countries = read_json_from_gcs(
        bucket_name=bucket, filename=related_countries_file_name, verbose=verbose
    )
    region_map = read_json_from_gcs(bucket_name=bucket, filename=regions_file_name, verbose=verbose)
    translations = read_dataframe(
        bucket_name=bucket, filename=translation_file_name, verbose=verbose
    )

    if verbose:
        print("Processing data to create the locations table")

    # Get just a map of the ISO* roll up countries and their territories
    group_map = {
        country: territory
        for country, territory in related_countries.items()
        if country.endswith("*")
    }

    # For now we area assuming that all entities that came from GADM or Marine Regions are lumped
    # countries
    eez["type"] = eez.apply(_add_default_types, axis=1)
    gadm["type"] = gadm.apply(_add_default_types, axis=1)

    if verbose:
        print("Processing EEZs and their country relation mappings")
    # Add country groups and regions
    eez = (
        eez.rename(columns={"location": "GID_0", "AREA_KM2": "total_marine_area"})
        .pipe(_add_groups, group_map, "country")
        .pipe(_add_groups, region_map, "region")
    )

    if verbose:
        print("Processing GADM and its country relation mappings")
    gadm = (
        gadm.rename(columns={"location": "GID_0"})
        .pipe(_add_groups, group_map, "country")
        .pipe(_add_groups, region_map, "region")
    )

    # Add total areas and bounds where needed
    gadm["total_terrestrial_area"] = gadm["geometry"].apply(get_area_km2).round(0).astype("Int64")
    gadm["terrestrial_bounds"] = gadm.geometry.bounds.apply(round_to_list, axis=1)

    # Marine area is precomputed for countries with unioque EEZ's but for groups and regions
    # we ned to calculate to avoid duplicating shared EEZ areas
    marine_area = pd.to_numeric(eez["total_marine_area"], errors="coerce")
    mask = marine_area.isna()
    filled = marine_area.copy()
    filled.loc[mask] = eez.loc[mask, "geometry"].apply(get_area_km2)
    eez["total_marine_area"] = filled.round(0).astype("Int64")
    eez["marine_bounds"] = eez.geometry.bounds.apply(round_to_list, axis=1)

    # Put it all together
    locs = (
        gadm.merge(
            eez[["GID_0", "marine_bounds", "total_marine_area", "has_shared_marine_area"]],
            on="GID_0",
            how="outer",
        )
        .pipe(_add_translations, translations)
        .drop(columns=["geometry", "COUNTRY", "GID_0"])
    )

    # Typesafe default for has_shared_marine_area
    locs["has_shared_marine_area"] = (
        locs.get("has_shared_marine_area").astype("boolean").fillna(False)
    )

    upload_dataframe(bucket_name=bucket, df=locs, destination_blob_name=output_file_name)


def _add_groups(gdf: gpd.GeoDataFrame, group_map: dict, group_type: str) -> gpd.GeoDataFrame:
    """Add region rows and update member rows' 'groups' lists."""
    gdf = gdf.copy()

    # Ensure 'groups' column exists and contains independent lists
    if "groups" not in gdf.columns:
        gdf["groups"] = None

    new_rows = []

    for group, members in group_map.items():
        subset = gdf[gdf["GID_0"].isin(members)]
        if subset.empty:
            continue

        geom = unary_union(subset.geometry.values)

        # Queue a new region row
        new_rows.append(
            {
                "GID_0": group,
                "geometry": geom,
                "type": group_type,
                "members": list(members),
                # currently we have no locations that are a group AND part of a groups.
                # This is because soverigns are pollitically grouped and regions are
                # geographically grouped
                "groups": None,
            }
        )

        # Append this group code to each member's 'groups' list
        member_mask = gdf["GID_0"].isin(members)
        gdf.loc[member_mask, "groups"] = gdf.loc[member_mask, "groups"].apply(
            lambda lst, group=group: _as_list(lst) + [group]
        )

    if new_rows:
        new_gdf = gpd.GeoDataFrame(new_rows, crs=gdf.crs)
        gdf = pd.concat([gdf, new_gdf], ignore_index=True, sort=False)

    return gdf


def _as_list(value):
    """Normalize cell content to a list copy for safe appends."""
    if isinstance(value, list):
        return list(value)  # copy so we don't mutate shared list objects
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return []
    return [value]


def _add_translations(gdf: gpd.GeoDataFrame, translations: pd.DataFrame) -> gpd.GeoDataFrame:
    gdf = gdf.copy()

    gdf = gdf.merge(
        translations[["code", "name", "name_es", "name_fr", "name_pt"]],
        left_on="GID_0",
        right_on="code",
        how="left",
    )
    return gdf


def _add_default_types(row):
    return "country" if row["location"] != "ABNJ" else "highseas"
