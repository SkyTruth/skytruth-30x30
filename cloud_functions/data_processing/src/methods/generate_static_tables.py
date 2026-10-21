import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from shapely.ops import unary_union

from src.core.commons import add_tolerance_suffix, load_iho_regions
from src.core.params import (
    BUCKET,
    EEZ_FILE_NAME,
    GADM_FILE_NAME,
    LOCATIONS_FILE_NAME,
    LOCATIONS_TRANSLATED_FILE_NAME,
    MPATLAS_COUNTRY_LEVEL_API_URL,
    NATIONAL_TARGETS_FILE_NAME,
    REGIONS_FILE_NAME,
    RELATED_COUNTRIES_FILE_NAME,
    TOLERANCE,
)
from src.core.processors import round_to_list
from src.utils.gcp import (
    read_dataframe,
    read_json_df,
    read_json_from_gcs,
    upload_dataframe,
)
from src.utils.geo import get_area_km2
from src.utils.logger import Logger

logger = Logger()


def process_national_targets(
    bucket: str = BUCKET,
    cbd_filename: str = NATIONAL_TARGETS_FILE_NAME,
    mpatlas_url: str = MPATLAS_COUNTRY_LEVEL_API_URL,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Prioritizes national targets from the Convention on Biological Diversity and
    falls back on MPAtlas defined targes if the CBD targets are not available. CBD targets are
    read from a CSV in GCS, MPAtlas targets from its country-level API. MPAtlas only publishes
    marine targets, so terrestrial targets come from the CBD alone.

    Args:
        bucket (str): The GCS bucket name.
        cbd_filename (str): The name of the CBD national targets CSV file.
        mpatlas_url (str): The MPAtlas country-level API url.
        verbose (bool): If True, logs the process.

    Returns:
        pd.DataFrame: Targets keyed by location code, one nullable integer column per target
            and target year, plus marine_target_source naming which dataset supplied the
            marine target.
    """
    if verbose:
        logger.info({"message": f"Reading national targets from {cbd_filename} in bucket {bucket}"})

    cbd_national_targets = read_dataframe(
        bucket_name=bucket, filename=cbd_filename, verbose=verbose
    )

    response = requests.get(mpatlas_url)
    response.raise_for_status()
    data = response.json()
    mpa_national_targets = pd.DataFrame(data)[
        ["id", "thirty_by_thirty_target", "national_target", "fully_highly_target", "target_year"]
    ]
    mpa_national_targets = mpa_national_targets[
        mpa_national_targets["thirty_by_thirty_target"].notnull()
    ]
    mpa_national_targets = mpa_national_targets.rename(
        columns={
            "id": "code",
            "national_target": "marine_target",
            "target_year": "marine_target_year",
        }
    )[["code", "marine_target", "marine_target_year"]]

    target_cols = [
        "marine_target",
        "marine_target_year",
        "terrestrial_target",
        "terrestrial_target_year",
    ]
    cbd = (
        cbd_national_targets.set_index("code")
        .reindex(columns=target_cols)
        .apply(pd.to_numeric, errors="coerce")
    )
    mpa = mpa_national_targets.set_index("code").apply(pd.to_numeric, errors="coerce")

    national_targets = cbd.combine_first(mpa)[target_cols].astype("Int64")

    # Only the marine target has two possible sources; terrestrial targets only come from the CBD
    from_cbd = national_targets.index.isin(cbd.index[cbd["marine_target"].notna()])
    national_targets["marine_target_source"] = pd.Series(
        np.where(from_cbd, "CBD", "MPAtlas"), index=national_targets.index
    ).where(national_targets["marine_target"].notna())

    national_targets = national_targets.reset_index()

    if verbose:
        logger.info(
            {
                "message": (
                    f"Resolved national targets for {len(national_targets)} locations"
                    f" ({len(cbd_national_targets)} from CBD,"
                    f" {len(mpa_national_targets)} available from MPAtlas)"
                )
            }
        )

    return national_targets


def generate_locations_table(
    eez_file_name: str = EEZ_FILE_NAME,
    gadm_file_name: str = GADM_FILE_NAME,
    output_file_name: str = LOCATIONS_FILE_NAME,
    related_countries_file_name: str = RELATED_COUNTRIES_FILE_NAME,
    regions_file_name: str = REGIONS_FILE_NAME,
    translation_file_name: str = LOCATIONS_TRANSLATED_FILE_NAME,
    bucket: str = BUCKET,
    tolerance: float = TOLERANCE,
    verbose: bool = True,
):
    if verbose:
        logger.info({"message": "Generating locations table"})

    eez_file = add_tolerance_suffix(eez_file_name, tolerance)
    gadm_file = add_tolerance_suffix(gadm_file_name, tolerance)

    eez = read_json_df(bucket_name=bucket, filename=eez_file, verbose=verbose)
    gadm = read_json_df(bucket_name=bucket, filename=gadm_file, verbose=verbose)
    iho_sea_areas = load_iho_regions()

    related_countries = read_json_from_gcs(
        bucket_name=bucket, filename=related_countries_file_name, verbose=verbose
    )
    region_map = read_json_from_gcs(bucket_name=bucket, filename=regions_file_name, verbose=verbose)
    translations = read_dataframe(
        bucket_name=bucket, filename=translation_file_name, verbose=verbose
    )
    national_targets = process_national_targets(bucket=bucket, verbose=verbose)

    if verbose:
        logger.info({"message": "Processing data to create the locations table"})

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

    # Adding type "sea" for all the IHO bodies of water
    iho_sea_areas["type"] = "sea"

    if verbose:
        logger.info({"message": "Processing EEZs and their country relation mappings"})
    # Add country groups and regions
    eez = (
        eez.rename(columns={"location": "GID_0", "AREA_KM2": "total_marine_area"})
        .pipe(_add_groups, group_map, "country")
        .pipe(_add_groups, region_map, "region")
    )

    if verbose:
        logger.info({"message": "Processing GADM and its country relation mappings"})
    gadm = (
        gadm.rename(columns={"location": "GID_0"})
        .pipe(_add_groups, group_map, "country")
        .pipe(_add_groups, region_map, "region")
    )

    if verbose:
        logger.info({"message": "Processing IHO Sea Areas"})
    iho_sea_areas = iho_sea_areas.rename(
        columns={"MRGID": "code", "NAME": "name", "area": "total_marine_area"}
    )
    iho_sea_areas["total_marine_area"] = pd.to_numeric(
        iho_sea_areas["total_marine_area"], errors="coerce"
    )
    iho_sea_areas["total_terrestrial_area"] = 0

    # Add total areas and bounds where needed
    gadm["total_terrestrial_area"] = gadm["geometry"].apply(get_area_km2).round(0).astype("Int64")
    gadm["terrestrial_bounds"] = gadm.geometry.bounds.apply(round_to_list, axis=1)

    # Marine area is precomputed for countries with unique EEZ's but for groups and regions
    # we ned to calculate to avoid duplicating shared EEZ areas
    marine_area = pd.to_numeric(eez["total_marine_area"], errors="coerce")
    mask = marine_area.isna()
    filled = marine_area.copy()
    filled.loc[mask] = eez.loc[mask, "geometry"].apply(get_area_km2)
    eez["total_marine_area"] = filled
    eez["marine_bounds"] = eez.geometry.bounds.apply(round_to_list, axis=1)

    # Adding bounds based on existing min/max coordinates
    iho_sea_areas["marine_bounds"] = (
        iho_sea_areas[["min_X", "min_Y", "max_X", "max_Y"]].astype(str).agg(",".join, axis=1)
    )

    # Adding None for terrestrial bounds
    iho_sea_areas["terrestrial_bounds"] = None

    # Adding empty strings for translations
    iho_sea_areas[["name_es", "name_fr", "name_pt"]] = ""

    # Put it all together
    locs = (
        gadm.merge(
            eez[["GID_0", "marine_bounds", "total_marine_area", "has_shared_marine_area"]],
            on="GID_0",
            how="outer",
        )
        .pipe(_add_translations, translations)
        .drop(columns=["geometry", "GID_0"])
    )

    locs = pd.concat(
        [
            locs,
            iho_sea_areas[
                [
                    "type",
                    "terrestrial_bounds",
                    "total_terrestrial_area",
                    "marine_bounds",
                    "total_marine_area",
                    "code",
                    "name",
                    "name_es",
                    "name_fr",
                    "name_pt",
                ]
            ],
        ],
        ignore_index=True,
    )

    target_cols = [
        "marine_target",
        "marine_target_year",
        "terrestrial_target",
        "terrestrial_target_year",
    ]
    locs = locs.merge(
        national_targets[["code", *target_cols, "marine_target_source"]], on="code", how="left"
    )

    # Typesafe defaults that might be missing after merger
    locs["has_shared_marine_area"] = (
        locs.get("has_shared_marine_area").astype("boolean").fillna(False)
    )
    locs["total_marine_area"] = locs.get("total_marine_area").round(0).fillna(0).astype("Int64")
    locs[target_cols] = locs[target_cols].apply(pd.to_numeric, errors="coerce").astype("Int64")

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
