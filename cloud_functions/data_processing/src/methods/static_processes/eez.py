import geopandas as gpd
import pandas as pd

from src.core.commons import (
    add_tolerance_suffix,
    load_iho_regions,
    load_marine_regions,
)
from src.core.params import (
    BUCKET,
    EEZ_FILE_NAME,
    EEZ_LAND_UNION_PARAMS,
    EEZ_MULTIPLE_SOV_FILE_NAME,
    EEZ_PARAMS,
    EEZS_TRANSLATED_FILE_NAME,
    GADM_EEZ_UNION_FILE_NAME,
    HIGH_SEAS_PARAMS,
    MARINE_LOCATIONS_FILE_NAME,
    RELATED_COUNTRIES_FILE_NAME,
    TOLERANCE,
)
from src.core.processors import add_translations, clean_geometries
from src.utils.gcp import read_dataframe, read_json_from_gcs, upload_gdf
from src.utils.logger import Logger

logger = Logger()


def process_eez_geoms(
    eez_file_name: str = EEZ_FILE_NAME,
    eez_params: dict = EEZ_PARAMS,
    bucket: str = BUCKET,
    related_countries_file_name: str = RELATED_COUNTRIES_FILE_NAME,
    tolerance: float = TOLERANCE,
    verbose: bool = True,
):
    """
    Method to process the downloaded EEZ shape file from marine regions. This method processes the
    data in two distinct ways and writes each of these to GCP.

    1. EEZ's are processed so each entry in the dataset maps to a single location (excluding ISO*
        roll ups). These entries contain multipolygons which contain all EEZ's that have the given
        location as a parent. This data is used for mapping habitat stats to ccountries and for
        updating the locations table in the database. This data is referred to as eez_by_sov
        in the code and is written as geojson to EEZ_FILE_NAME

    2. EEZ's are processed so each entry in the dataset is a unique polygon and each EEZ contains
        properties of ISO_SOV1, ISO_SOV2, ISO_SOV3, which map the EEZ to all locations which
        have a claim on the EEZ. This structure is used to generate EEZ and Marine regions map
        tiles. This data is referred to as eez_multiple_sovs in the code and writen as a
        .geojson file to EEZ_MULTIPLE_SOV_FILE_NAME
    """
    if verbose:
        logger.info({"message": f"loading eezs from {eez_params['zipfile_name']}"})

    related_countries = read_json_from_gcs(bucket, related_countries_file_name, verbose=verbose)

    eez = load_marine_regions(eez_params, bucket)

    eez[["parents", "sovs"]] = eez.apply(
        _pick_eez_parents, args=(related_countries,), axis=1, result_type="expand"
    )
    eez.loc[eez["parents"].apply(lambda parents: len(parents) > 1), "has_shared_marine_area"] = True

    # Load in High Seas Data
    high_seas = load_marine_regions(HIGH_SEAS_PARAMS, bucket)
    high_seas[["GID_0"]] = "ABNJ"
    high_seas[["ISO_TER1"]] = "ABNJ"
    high_seas[["POL_TYPE"]] = "High Seas"
    high_seas[["GEONAME"]] = "High Seas"
    high_seas[["has_shared_marine_area"]] = False
    high_seas.rename(columns={"area_km2": "AREA_KM2", "mrgid": "MRGID"}, inplace=True)

    # Load in EEZ translations
    translations = read_dataframe(bucket, EEZS_TRANSLATED_FILE_NAME)

    eez_by_sov = _process_eez_by_sov(eez.copy(), high_seas.copy())
    eez_multiple_sovs = _proccess_eez_multiple_sovs(eez.copy(), high_seas.copy(), translations)

    if tolerance is not None:
        if verbose:
            logger.info(
                {"message": (f"simplifying eez by sovereign geometries with tolerance {tolerance}")}
            )
        eez_by_sov["geometry"] = eez_by_sov["geometry"].simplify(tolerance=tolerance)

    eez_by_sov = eez_by_sov.pipe(clean_geometries)

    out_fn = add_tolerance_suffix(eez_file_name, tolerance)
    if verbose:
        logger.info({"message": f"uploading eez by sovereign file to {out_fn}"})
    upload_gdf(bucket, eez_by_sov, out_fn)

    iho = load_iho_regions()[["location", "geometry"]]
    if tolerance is not None:
        if verbose:
            logger.info({"message": f"simplifying iho sea areas with tolerance {tolerance}"})
        iho["geometry"] = iho["geometry"].simplify(tolerance=tolerance)

    marine_locations = pd.concat(
        [eez_by_sov[["location", "geometry"]], iho], ignore_index=True
    ).pipe(clean_geometries)

    marine_locations_fn = add_tolerance_suffix(MARINE_LOCATIONS_FILE_NAME, tolerance)
    if verbose:
        logger.info({"message": f"uploading marine locations file to {marine_locations_fn}"})
    upload_gdf(bucket, marine_locations, marine_locations_fn)

    if verbose:
        logger.info(
            {
                "message": (
                    f"simplifying eez with mulit-sovereign geometries with tolerance {tolerance}"
                )
            }
        )
    eez_multiple_sovs["geometry"] = eez_multiple_sovs["geometry"].simplify(tolerance=tolerance)
    eez_multiple_sovs = eez_multiple_sovs.pipe(clean_geometries)

    blob_name = add_tolerance_suffix(EEZ_MULTIPLE_SOV_FILE_NAME, tolerance)
    if verbose:
        logger.info({"message": f"uploading eez with multi-sovereign file to {blob_name}"})
    upload_gdf(bucket, eez_multiple_sovs, blob_name)


def _pick_eez_parents(row, related_countries: dict) -> list:
    """
    Helper method to assign EEZ parents and sovereigns. Marine regions offeres 3 possible country
    + territory locations for an EEZ. ISO_TER# is the immediate, independant location and ISO_SOV#
    is the sovereign for the matching ISO_TER. ISO_TER may be None, e.g. the Alaska EEZ has no
    ISO_TER1 but it does have USA for ISO_SOV1 - USA is considered a parent rather than a sovereign
    in this example because we want the Alaska EEZ to be part of USA not USA*. The guiding logic
    for assigning countries to EEZ's that we employ is:

    1. Compare each ISO_TER#, ISO_SOV# pair
    2. If, for a given pair, there is an ISO_TER we take that as a parent.
        2a. If the ISO_SOV is tracked as a sovereign roll up (e.g. We have data for ISO*) we add
        the ISO_SOV as a soverign
    3. If there is no ISO_TER we take the ISO_SOV as a parent if it exists
    3. We dedupe any acrued ISO codes

    This reults is at most 3 potential parent locations and assumes any mapping between defined
    territories and their sovereigns will occur during sovereign rollups not here.

    Example:
    The EEZ Around Myotis has:
    ISO_TER1 = MYT, ISO_TER2 = MYT, ISO_TER3 = None
    ISO_SOV1 = COM, ISO_SOV2 = FRA, ISO_SOV3 = None
    In this case it is only assinged the parent of MYT, however MYT is defined as a territory of
    FRA*, so for roll-up stats, this EEZ will still get included with FRA* when that proccessing
    occurs.
    """
    parents = set()
    sovs = set()
    if row.ISO_TER1:
        parents.add(row.ISO_TER1)
    else:
        parents.add(row.ISO_SOV1)
    sov = f"{row.ISO_SOV1}*" if row.ISO_SOV1 else None
    if related_countries.get(sov) is not None:
        sovs.add(sov)

    if row.ISO_TER2:
        parents.add(row.ISO_TER2)
    elif row.ISO_SOV2:
        parents.add(row.ISO_SOV2)
    sov = f"{row.ISO_SOV2}*" if row.ISO_SOV2 else None
    if related_countries.get(sov) is not None:
        sovs.add(sov)

    if row.ISO_TER3:
        parents.add(row.ISO_TER3)
    elif row.ISO_SOV3:
        parents.add(row.ISO_SOV3)
    sov = f"{row.ISO_SOV3}*" if row.ISO_SOV3 else None
    if related_countries.get(sov) is not None:
        sovs.add(sov)

    return list(parents), list(sovs)


def _process_eez_by_sov(eez: gpd.GeoDataFrame, high_seas: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    eez_by_sov = (
        eez.drop(columns=["sovs"])
        .explode("parents")
        .rename(columns={"parents": "GID_0"})[
            ["GID_0", "AREA_KM2", "geometry", "has_shared_marine_area"]
        ]
    )

    high_seas.drop(
        columns=list(
            set(high_seas.columns)
            - set(
                [
                    "GID_0",
                    "geometry",
                    "AREA_KM2",
                    "GEONAME",
                    "has_shared_marine_area",
                ]
            )
        ),
        inplace=True,
    )

    eez_by_sov = pd.concat([eez_by_sov, high_seas], ignore_index=True, sort=False)
    eez_by_sov = eez_by_sov.dissolve(
        by="GID_0", as_index=False, aggfunc={"AREA_KM2": "sum", "has_shared_marine_area": "any"}
    ).reset_index()

    eez_by_sov.rename(columns={"GID_0": "location"}, inplace=True)
    return eez_by_sov


def _proccess_eez_multiple_sovs(
    eez: gpd.GeoDataFrame, high_seas: gpd.GeoDataFrame, translations: pd.DataFrame
) -> gpd.GeoDataFrame:
    eez = eez.apply(_assign_terrs_and_sovs, axis=1)

    eez_multiple_sovs = pd.concat([eez, high_seas], ignore_index=True, sort=False)

    eez_multiple_sovs = eez_multiple_sovs.drop(
        columns=list(
            set(eez_multiple_sovs.columns)
            - set(
                [
                    "ISO_SOV1",
                    "ISO_SOV2",
                    "ISO_SOV3",
                    "ISO_TER1",
                    "ISO_TER2",
                    "ISO_TER3",
                    "geometry",
                    "AREA_KM2",
                    "POL_TYPE",
                    "MRGID",
                ]
            )
        ),
    ).pipe(add_translations, translations, "MRGID", "MRGID")

    return eez_multiple_sovs


def _assign_terrs_and_sovs(row):
    row["ISO_TER1"] = row["parents"][0] if len(row["parents"]) >= 1 else None
    row["ISO_TER2"] = row["parents"][1] if len(row["parents"]) >= 2 else None
    row["ISO_TER3"] = row["parents"][2] if len(row["parents"]) >= 3 else None

    row["ISO_SOV1"] = row["sovs"][0] if len(row["sovs"]) >= 1 else None
    row["ISO_SOV2"] = row["sovs"][1] if len(row["sovs"]) >= 2 else None
    row["ISO_SOV3"] = row["sovs"][2] if len(row["sovs"]) >= 3 else None
    return row


def process_eez_land_union(
    eez_land_union_params: dict = EEZ_LAND_UNION_PARAMS,
    gadm_eez_union_file_name: str = GADM_EEZ_UNION_FILE_NAME,
    related_countries_file_name: str = RELATED_COUNTRIES_FILE_NAME,
    tolerance: float = TOLERANCE,
    bucket: str = BUCKET,
    verbose: bool = True,
):
    """Build the per-location land/EEZ union from the Marine Regions EEZ-land-union.

    Each feature is mapped to its parent location(s) with ``_pick_eez_parents`` -
    the same logic ``process_eez_geoms`` uses - so a feature claimed by multiple
    ISO_TER/ISO_SOV entries is attributed to every claimant (intentional, and
    consistent with how shared marine areas are over-attributed elsewhere). The
    result is exploded to one row per location, dissolved, and written to
    ``gadm_eez_union_file_name`` - the file ``process_near_shore_iho`` builds the
    buffered marine locations from, and the climate-resilient-coral subtable reads.
    """
    if verbose:
        logger.info(
            {"message": f"loading eez/land union from {eez_land_union_params['zipfile_name']}"}
        )

    related_countries = read_json_from_gcs(bucket, related_countries_file_name, verbose=verbose)
    union = load_marine_regions(eez_land_union_params, bucket)

    # Empty ISO fields can load as NaN; coerce to None so the truthiness checks in
    # _pick_eez_parents treat them as absent rather than as a (truthy) NaN parent.
    iso_columns = ["ISO_TER1", "ISO_TER2", "ISO_TER3", "ISO_SOV1", "ISO_SOV2", "ISO_SOV3"]
    for column in iso_columns:
        union[column] = union[column].apply(
            lambda value: value if isinstance(value, str) and value.strip() else None
        )

    union[["parents", "sovs"]] = union.apply(
        _pick_eez_parents, args=(related_countries,), axis=1, result_type="expand"
    )

    if verbose:
        logger.info({"message": "exploding eez/land union to one row per location"})

    eez_land_union = (
        union[["parents", "geometry"]].explode("parents").rename(columns={"parents": "location"})
    )
    eez_land_union = eez_land_union[eez_land_union["location"].notna()]
    eez_land_union = eez_land_union.dissolve(by="location", as_index=False)

    if tolerance is not None:
        if verbose:
            logger.info({"message": f"simplifying eez/land union with tolerance {tolerance}"})
        eez_land_union["geometry"] = eez_land_union["geometry"].simplify(tolerance=tolerance)

    eez_land_union = eez_land_union[["location", "geometry"]].pipe(clean_geometries)

    out_fn = add_tolerance_suffix(gadm_eez_union_file_name, tolerance)
    if verbose:
        logger.info({"message": f"uploading eez/land union to {out_fn}"})
    upload_gdf(bucket, eez_land_union, out_fn)
