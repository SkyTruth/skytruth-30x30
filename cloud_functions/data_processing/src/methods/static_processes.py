import concurrent.futures
import datetime
import fnmatch
import gc
import threading
import zipfile
from collections.abc import Callable
from pathlib import Path

import fsspec
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import shapely
from google.cloud import storage
from joblib import Parallel, delayed
from shapely.geometry import box, mapping
from shapely.strtree import STRtree
from shapely.validation import make_valid
from tqdm.auto import tqdm

from src.core.commons import (
    add_tolerance_suffix,
    download_and_duplicate_zipfile,
    get_cover_areas,
    load_marine_regions,
    safe_union,
)
from src.core.land_cover_params import (
    BIOME_RASTER_PATH,
    LAND_COVER_CLASSES,
    marine_tolerance,
    reclass_function,
    terrestrial_tolerance,
)
from src.core.params import (
    BUCKET,
    CHUNK_SIZE,
    COUNTRY_TERRESTRIAL_HABITATS_FILE_NAME,
    EEZ_FILE_NAME,
    EEZ_LAND_UNION_PARAMS,
    EEZ_MULTIPLE_SOV_FILE_NAME,
    EEZ_PARAMS,
    EEZS_TRANSLATED_FILE_NAME,
    GADM_EEZ_UNION_FILE_NAME,
    GADM_FILE_NAME,
    GADM_ZIPFILE_NAME,
    GLOBAL_MANGROVE_AREA_FILE_NAME,
    GLOBAL_UNEP_HABITAT_AREA_FILE_PATTERN,
    HIGH_SEAS_PARAMS,
    IHO_SEA_AREAS_FILE_NAME,
    IHO_SEA_AREAS_PARAMS,
    MANGROVES_BY_LOCATION_FILE_NAME,
    MANGROVES_ZIPFILE_NAME,
    MARINE_HABITAT_PARAMS,
    PROCESSED_BIOME_RASTER_PATH,
    PROJECT,
    RELATED_COUNTRIES_FILE_NAME,
    TOLERANCES,
    UNEP_HABITAT_BY_LOCATION_FILE_PATTERN,
    UNEP_HABITAT_TOLERANCE,
    UNEP_HABITATS,
    UNEP_POINT_AREA_KM2,
)
from src.core.processors import add_translations, clean_geometries
from src.utils.gcp import (
    download_file_from_gcs,
    load_zipped_shapefile_from_gcs,
    read_dataframe,
    read_json_df,
    read_json_from_gcs,
    read_parquet_from_gcs,
    read_zipped_gpkg_from_gcs,
    save_json_to_gcs,
    upload_dataframe,
    upload_file_to_gcs,
    upload_gdf,
)
from src.utils.geo import (
    get_area_km2,
    robust_unary_union,
    split_at_antimeridian,
    tile_geometry,
)
from src.utils.logger import Logger

logger = Logger()


def process_gadm_geoms(
    gadm_file_name: str = GADM_FILE_NAME,
    gadm_zipfile_name: str = GADM_ZIPFILE_NAME,
    bucket: str = BUCKET,
    related_countries_file_name: str = RELATED_COUNTRIES_FILE_NAME,
    tolerances: list | tuple = TOLERANCES,
    verbose: bool = True,
) -> None:
    if verbose:
        logger.info({"message": f"loading gadm gpkg from {gadm_zipfile_name}"})
    related_countries = read_json_from_gcs(bucket, related_countries_file_name, verbose=verbose)

    # Create an inverse parent child location map excluding sovereign rollups with a trailing '*'
    inv_map = {
        child: parent
        for parent, children in related_countries.items()
        if parent[-1] != "*"
        for child in children
    }

    def get_valid_iso(codes):
        for code in codes:
            if code in inv_map:
                return code

            return pd.NA

    countries, sub_countries = read_zipped_gpkg_from_gcs(
        bucket, gadm_zipfile_name, layers=["ADM_0", "ADM_1"]
    )
    if verbose:
        logger.info({"message": "Layers extracted from gpkg"})

    countries.drop(
        columns=list(set(countries.columns) - set(["GID_0", "COUNTRY", "geometry"])), inplace=True
    )

    sub_countries.drop(
        columns=list(set(countries.columns) - set(["GID_0", "COUNTRY", "geometry"])), inplace=True
    )

    # Some contested areas have invalid ISO codes (e.g. Z01), but have a valid Country name to
    # they tentatively belong, e.g. parts of Kashmir are mapped to India or Pakistan.
    # Following the suggested country name appears to be what WDPA does, so we follow that pattern.
    countries = countries.dissolve(by="COUNTRY", as_index=False, aggfunc={"GID_0": get_valid_iso})

    # Pull Hong Kong from the ADM_1 layer to add it as a territory to our countries map
    hong_kong = sub_countries[sub_countries["GID_1"] == "CHN.HKG"].copy()
    hong_kong.loc[:, "GID_0"] = "HKG"
    hong_kong = hong_kong[["GID_0", "COUNTRY", "geometry"]]
    # Remove Hong Kong from China in the countries layer
    countries.loc[countries["GID_0"] == "CHN", "geometry"] = countries.loc[
        countries["GID_0"] == "CHN", "geometry"
    ].difference(hong_kong.geometry.iloc[0])

    abnj = {"GID_0": "ABNJ", "COUNTRY": "Areas Beyond National Jurisdiction", "geometry": None}
    abnj = gpd.GeoDataFrame([abnj], crs=countries.crs)

    countries = pd.concat([countries, hong_kong, abnj], ignore_index=True, sort=False)

    # Map each code to inv_map[code] if it exists, otherwise leave it unchanged
    # This catches things like Northern Cyprus being rolled into Cyprus
    countries["GID_0"] = countries["GID_0"].map(inv_map).fillna(countries["GID_0"])
    countries = countries.dissolve(by="GID_0", as_index=False)

    countries = (
        countries.rename(columns={"GID_0": "location"})
        .drop(columns=["COUNTRY"])
        .pipe(clean_geometries)
    )

    for tolerance in tolerances:
        df = countries.copy()

        if tolerance is not None:
            if verbose:
                logger.info({"message": f"simplifying geometries with tolerance {tolerance}"})
            df["geometry"] = df["geometry"].simplify(tolerance=tolerance)

        df = df.pipe(clean_geometries)

        out_fn = add_tolerance_suffix(gadm_file_name, tolerance)
        if verbose:
            logger.info({"message": f"uploading simplified GADM countries to {out_fn}"})
        upload_gdf(bucket, df, out_fn)

    gc.collect()


def process_eez_geoms(
    eez_file_name: str = EEZ_FILE_NAME,
    eez_params: dict = EEZ_PARAMS,
    bucket: str = BUCKET,
    related_countries_file_name: str = RELATED_COUNTRIES_FILE_NAME,
    tolerances: list | tuple = TOLERANCES,
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

    for tolerance in tolerances:
        if tolerance is not None:
            if verbose:
                logger.info(
                    {
                        "message": (
                            f"simplifying eez by sovereign geometries with tolerance {tolerance}"
                        )
                    }
                )
            eez_by_sov["geometry"] = eez_by_sov["geometry"].simplify(tolerance=tolerance)

        eez_by_sov = eez_by_sov.pipe(clean_geometries)

        out_fn = add_tolerance_suffix(eez_file_name, tolerance)
        if verbose:
            logger.info({"message": f"uploading eez by sovereign file to {out_fn}"})
        upload_gdf(bucket, eez_by_sov, out_fn)

    if verbose:
        logger.info(
            {
                "message": (
                    f"simplifying eez with mulit-sovereign geometries "
                    f"with tolerance {TOLERANCES[1]}"
                )
            }
        )
    eez_multiple_sovs["geometry"] = eez_multiple_sovs["geometry"].simplify(tolerance=TOLERANCES[1])
    eez_multiple_sovs = eez_multiple_sovs.pipe(clean_geometries)

    blob_name = add_tolerance_suffix(EEZ_MULTIPLE_SOV_FILE_NAME, TOLERANCES[1])
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
    tolerance: float = marine_tolerance,
    bucket: str = BUCKET,
    verbose: bool = True,
):
    """Build the per-location land/EEZ union from the Marine Regions EEZ-land-union.

    Each feature is mapped to its parent location(s) with ``_pick_eez_parents`` -
    the same logic ``process_eez_geoms`` uses - so a feature claimed by multiple
    ISO_TER/ISO_SOV entries is attributed to every claimant (intentional, and
    consistent with how shared marine areas are over-attributed elsewhere). The
    result is exploded to one row per location, dissolved, and written to
    ``gadm_eez_union_file_name`` - the file consumed by the mangrove and
    climate-resilient-coral subtables.
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


def stitch_mediterannean(iho):
    iho = iho.copy()

    medi_mrgid = [4280, 3315, 3351, 4279, 3322, 3324, 3346, 3369, 3386, 3314, 3363]
    medi = iho[iho["MRGID"].isin(medi_mrgid)].dissolve().reset_index(drop=True)

    # Recompute the geometry-derived fields from the dissolved polygon
    bounds = medi.total_bounds  # (minx, miny, maxx, maxy) in the layer CRS (4326)
    centroid = medi.to_crs(epsg=6933).geometry.centroid.to_crs(epsg=4326).iloc[0]

    medi["NAME"] = "Mediterranean Region"
    medi["ID"] = None
    medi["MRGID"] = "MEDI"
    medi["Longitude"] = centroid.x
    medi["Latitude"] = centroid.y
    medi["min_X"], medi["min_Y"], medi["max_X"], medi["max_Y"] = bounds
    medi["area"] = medi.to_crs(epsg=6933).geometry.area.iloc[0] / 1e6

    iho["MRGID"] = iho["MRGID"].astype(str)
    iho = pd.concat((iho, medi), axis=0, ignore_index=True)

    return iho


def process_iho_sea_areas(
    iho_params: dict = IHO_SEA_AREAS_PARAMS,
    iho_file_name: str = IHO_SEA_AREAS_FILE_NAME,
    tolerances: list | tuple = TOLERANCES,
    bucket: str = BUCKET,
    verbose: bool = True,
):
    if verbose:
        logger.info({"message": f"loading IHO sea areas from {iho_params['zipfile_name']}"})

    iho = load_marine_regions(iho_params, bucket)
    iho = stitch_mediterannean(iho)
    original_geometry = iho["geometry"].copy()

    for tolerance in tolerances:
        if verbose:
            logger.info({"message": f"simplifying IHO sea areas with tolerance {tolerance}"})
        iho_t = iho.copy()
        iho_t["geometry"] = original_geometry.simplify(tolerance=tolerance)
        iho_t = iho_t.pipe(clean_geometries)

        out_fn = add_tolerance_suffix(iho_file_name, tolerance)
        if verbose:
            logger.info({"message": f"uploading IHO sea areas to {out_fn}"})
        upload_gdf(bucket, iho_t, out_fn)


def download_marine_habitats(
    habitats: str | list[str] | None = None,
    marine_habitat_params: dict = MARINE_HABITAT_PARAMS,
    bucket: str = BUCKET,
    chunk_size: int = CHUNK_SIZE,
    verbose: bool = True,
) -> None:
    """
    Downloads marine habitat source datasets and uploads them to GCS as both
    current and archived versions.

    Parameters:
    ----------
    habitats : str | list[str] | None
        Habitat key(s) from marine_habitat_params to download. None
        downloads all of them.
    marine_habitat_params : dict
        Habitat key -> {"url", "zipfile_name", "archive_file_name"} config.
    bucket : str
        Name of the GCS bucket where all files will be uploaded.
    chunk_size : int, optional
        Size in bytes of each chunk used during download.
    verbose : bool, optional
        If True, prints progress messages. Default is True.
    """
    if habitats is None:
        habitats = list(marine_habitat_params)
    elif isinstance(habitats, str):
        habitats = [habitats]

    unknown = set(habitats) - set(marine_habitat_params)
    if unknown:
        raise ValueError(f"unknown marine habitat(s): {sorted(unknown, key=repr)}")

    for habitat in habitats:
        download = marine_habitat_params[habitat]
        if verbose:
            logger.info({"message": f"downloading {habitat} from {download['url']}"})
        download_and_duplicate_zipfile(
            download["url"],
            bucket,
            download["zipfile_name"],
            download["archive_file_name"],
            chunk_size=chunk_size,
            verbose=verbose,
        )


def process_mangroves(
    mangroves_by_location_file_name: str = MANGROVES_BY_LOCATION_FILE_NAME,
    mangroves_zipfile_name: str = MANGROVES_ZIPFILE_NAME,
    gadm_eez_union_file_name: dict = GADM_EEZ_UNION_FILE_NAME,
    iho_file_name: str = IHO_SEA_AREAS_FILE_NAME,
    global_mangrove_area_file_name: str = GLOBAL_MANGROVE_AREA_FILE_NAME,
    bucket: str = BUCKET,
    project: str = PROJECT,
    verbose: bool = True,
    tolerance=0.001,
    batch_size=3000,
):
    tqdm.pandas()

    if verbose:
        logger.info({"message": "loading mangroves"})
    mangrove = load_zipped_shapefile_from_gcs(mangroves_zipfile_name, bucket).pipe(clean_geometries)
    mangrove["index"] = range(len(mangrove))

    if verbose:
        logger.info({"message": "loading eezs/gadm union"})
    gadm_eez_union_file_name = add_tolerance_suffix(gadm_eez_union_file_name, tolerance)
    gadm_eez_union = read_json_df(bucket, gadm_eez_union_file_name, verbose=verbose)

    if verbose:
        logger.info({"message": "loading IHO sea areas"})
    iho = read_parquet_from_gcs(
        bucket, add_tolerance_suffix(iho_file_name, tolerance), verbose=verbose
    )
    iho["location"] = iho["MRGID"].astype(str)

    regions = gpd.GeoDataFrame(
        pd.concat(
            [gadm_eez_union[["location", "geometry"]], iho[["location", "geometry"]]],
            ignore_index=True,
        ),
        geometry="geometry",
        crs=gadm_eez_union.crs,
    )

    if verbose:
        logger.info({"message": "re-projecting mangroves for global area calculation"})
    mangrove_reproj = mangrove.to_crs("EPSG:6933").pipe(clean_geometries)

    if verbose:
        logger.info(
            {
                "message": f"saving global mangrove area to gs://{bucket}/{global_mangrove_area_file_name}"
            }
        )
    mangrove_reproj["area_km2"] = mangrove_reproj.geometry.area / 1e6
    global_mangrove_area = mangrove_reproj["area_km2"].sum()

    save_json_to_gcs(
        bucket,
        {"global_area_km2": global_mangrove_area},
        global_mangrove_area_file_name,
        project,
        verbose,
    )

    if verbose:
        logger.info({"message": "generating mangrove polygons by country and IHO region"})
    mangroves_by_location = []
    for cnt in tqdm(list(sorted(set(regions["location"].dropna())))):
        country_geom = regions[regions["location"] == cnt].iloc[0].geometry

        # clip mangroves to country bounding box
        xmin, ymin, xmax, ymax = country_geom.bounds
        mangroves_clipped = mangrove[mangrove.intersects(box(xmin, ymin, xmax, ymax))]

        # Build STRtree index
        mangrove_geoms = list(mangroves_clipped.geometry)
        tree = STRtree(mangrove_geoms)

        indices = tree.query(country_geom, predicate="intersects")
        location_mangroves = mangroves_clipped.iloc[indices].copy()
        location_mangroves["geometry"] = location_mangroves.geometry.apply(make_valid)
        if len(location_mangroves) > 0:
            mangrove_geom = safe_union(
                location_mangroves, batch_size=batch_size, simplify_tolerance=tolerance
            )
            mangroves_by_location.append(
                {
                    "location": cnt,
                    "n_mangrove_polygons": len(location_mangroves),
                    "bbox": country_geom.bounds,
                    "mangrove_area_km2": location_mangroves.to_crs("EPSG:6933").area.sum() / 1e6,
                    "geometry": mangrove_geom,
                }
            )

    mangroves_by_location = gpd.GeoDataFrame(
        mangroves_by_location, geometry="geometry", crs="EPSG:4326"
    )
    upload_gdf(
        bucket,
        mangroves_by_location,
        mangroves_by_location_file_name,
        project_id=project,
        verbose=True,
        timeout=600,
    )


def _find_unep_layer_paths(bucket: str, zipfile_name: str) -> tuple[str, str]:
    """
    Locate the point and polygon shapefiles inside a UNEP-WCMC download.
    """
    with (
        fsspec.open(f"gs://{bucket}/{zipfile_name}", mode="rb") as remote_zip,
        zipfile.ZipFile(remote_zip) as zf,
    ):
        names = zf.namelist()

    def match_layer(pattern: str) -> str:
        matches = [name for name in names if fnmatch.fnmatch(name, pattern)]
        if len(matches) != 1:
            raise ValueError(
                f"expected exactly one layer matching {pattern} in {zipfile_name}, "
                f"found {len(matches)}: {matches}"
            )
        return matches[0]

    return match_layer("*/01_Data/*_Pt_*.shp"), match_layer("*/01_Data/*_Py_*.shp")


def _buffer_unep_points(
    points: gpd.GeoDataFrame,
    fallback_area_km2: float = UNEP_POINT_AREA_KM2,
) -> gpd.GeoDataFrame:
    """Convert a UNEP-WCMC point layer into polygons by buffering each point.

    Where a reported area is recorded, the radius is derived (r = sqrt(area/pi));
    where it is not, the point is buffered so that the area equals
    fallback_area_km2 (default 1 km²).
    """
    points = points.explode(index_parts=False).reset_index(drop=True)

    reported_area_km2 = pd.to_numeric(points.get("REP_AREA_K"), errors="coerce")
    area_km2 = reported_area_km2.where(reported_area_km2 > 0, fallback_area_km2)

    # Buffer points
    buffered = points.to_crs("EPSG:6933")
    buffered["geometry"] = buffered.geometry.buffer(np.sqrt(area_km2 / np.pi) * 1000)
    buffered = buffered.to_crs(points.crs)

    # Split buffer polygons that wrap the antimeridian
    longitudes = points.geometry.x
    wrapped = buffered.geometry.bounds.eval("maxx - minx") > 180
    if wrapped.any():
        buffered.loc[wrapped, "geometry"] = [
            split_at_antimeridian(geom, reference_lon)
            for geom, reference_lon in zip(
                buffered.geometry[wrapped], longitudes[wrapped], strict=True
            )
        ]

    buffered["rep_area_km2"] = reported_area_km2
    return buffered


def _clip_and_union_habitat(
    location: str,
    parts: np.ndarray,
    location_geom,
    batch_size: int,
) -> dict | None:
    """Clip a location's habitat parts to its boundary and dissolve them into one geometry.

    Clipping ensures that only the areas that intersect the location are considered.
    Dissolving removes the overlap between the buffered points and the polygon layer.
    """
    clipped = shapely.intersection(parts, location_geom)
    clipped = clipped[~shapely.is_missing(clipped) & ~shapely.is_empty(clipped)]
    if len(clipped) == 0:
        return None

    habitat_geom = safe_union(
        gpd.GeoSeries(clipped), batch_size=batch_size, simplify_tolerance=None
    )
    if habitat_geom is None or habitat_geom.is_empty:
        return None

    return {
        "location": location,
        "n_habitat_polygons": int(len(clipped)),
        "bbox": location_geom.bounds,
        "area_km2": get_area_km2(habitat_geom),
        "geometry": habitat_geom,
    }


def process_marine_unep_habitats(
    habitats: str | list[str] | None = None,
    unep_habitats: dict = UNEP_HABITATS,
    gadm_eez_union_file_name: str = GADM_EEZ_UNION_FILE_NAME,
    iho_file_name: str = IHO_SEA_AREAS_FILE_NAME,
    by_location_file_pattern: str = UNEP_HABITAT_BY_LOCATION_FILE_PATTERN,
    global_area_file_pattern: str = GLOBAL_UNEP_HABITAT_AREA_FILE_PATTERN,
    fallback_area_km2: float = UNEP_POINT_AREA_KM2,
    bucket: str = BUCKET,
    project: str = PROJECT,
    verbose: bool = True,
    tolerance: float = 0.001,
    simplify_tolerance: float = UNEP_HABITAT_TOLERANCE,
    batch_size: int = 3000,
    n_jobs: int = -1,
) -> None:
    """
    Turn the downloaded UNEP-WCMC habitat zips into per-location habitat geometries.

    For each habitat, the point layer is buffered into polygons (see
    _buffer_unep_points), merged with the polygon layer, and written to GCS
    as a geoparquet. The merged layer is then dissolved per location
    and written alongside a global area. Areas are taken from the dissolved
    geometry to address overlaps.

    Parameters:
    ----------
    habitats : str | list[str] | None
        Habitat key(s) from unep_habitats to process. None processes all.
    unep_habitats : dict
        Habitat key -> {"zipfile_name": ...} config.
    gadm_eez_union_file_name : str
        GCS blob of the land/EEZ union, used together with the IHO sea areas as
        the set of locations to dissolve by.
    iho_file_name : str
        GCS blob of the processed IHO sea areas.
    by_location_file_pattern : str
        Template for the dissolved per-location blob name.
    global_area_file_pattern : str
        Template for the global area JSON blob name.
    fallback_area_km2 : float
        Area assigned to points with no reported area.
    bucket : str
        GCS bucket to read from and write to.
    project : str
        GCP project used for uploads.
    verbose : bool
        If True, logs progress.
    tolerance : float
        Which simplification of the location boundaries to read (file suffix only).
    simplify_tolerance : float
        Simplification applied to the habitat geometry.
    batch_size : int
        Batch size passed to safe_union.
    n_jobs : int
        Worker count for the per-location clip and dissolve.
        -1 uses every core.
    """
    if habitats is None:
        habitats = list(unep_habitats)
    elif isinstance(habitats, str):
        habitats = [habitats]

    unknown = set(habitats) - set(unep_habitats)
    if unknown:
        raise ValueError(f"unknown UNEP habitat(s): {sorted(unknown)}")

    if verbose:
        logger.info({"message": "loading eezs/gadm union"})
    gadm_eez_union = read_json_df(
        bucket, add_tolerance_suffix(gadm_eez_union_file_name, tolerance), verbose=verbose
    )

    if verbose:
        logger.info({"message": "loading IHO sea areas"})
    iho = read_parquet_from_gcs(
        bucket, add_tolerance_suffix(iho_file_name, tolerance), verbose=verbose
    )
    iho["location"] = iho["MRGID"].astype(str)

    regions = gpd.GeoDataFrame(
        pd.concat(
            [gadm_eez_union[["location", "geometry"]], iho[["location", "geometry"]]],
            ignore_index=True,
        ),
        geometry="geometry",
        crs=gadm_eez_union.crs,
    )

    for habitat in habitats:
        zipfile_name = unep_habitats[habitat]["zipfile_name"]

        if verbose:
            logger.info({"message": f"locating {habitat} layers in {zipfile_name}"})
        point_layer, polygon_layer = _find_unep_layer_paths(bucket, zipfile_name)

        if verbose:
            logger.info({"message": f"loading {habitat} point layer {point_layer}"})
        points = load_zipped_shapefile_from_gcs(
            zipfile_name, bucket, internal_shapefile_path=point_layer
        )

        # Buffer points using reported area where available and fallback area otherwise
        if verbose:
            logger.info({"message": f"buffering {len(points)} {habitat} point records"})
        buffered_points = _buffer_unep_points(points, fallback_area_km2=fallback_area_km2)

        # Combine buffered points with polygons
        if verbose:
            logger.info({"message": f"loading {habitat} polygon layer {polygon_layer}"})
        polygons = load_zipped_shapefile_from_gcs(
            zipfile_name, bucket, internal_shapefile_path=polygon_layer
        ).pipe(clean_geometries)
        polygons["rep_area_km2"] = pd.to_numeric(polygons.get("REP_AREA_K"), errors="coerce")

        columns = ["rep_area_km2", "geometry"]
        buffered_points["source"] = "point"
        polygons["source"] = "polygon"
        merged = gpd.GeoDataFrame(
            pd.concat(
                [buffered_points[["source", *columns]], polygons[["source", *columns]]],
                ignore_index=True,
            ),
            geometry="geometry",
            crs=polygons.crs,
        ).pipe(clean_geometries)
        merged["habitat"] = habitat

        del points, buffered_points, polygons
        gc.collect()

        # Separate multi-polygons to single polygons for improved union performance
        if verbose:
            logger.info({"message": f"simplifying and validating {habitat} geometry"})
        merged = merged.explode(index_parts=False, ignore_index=True)

        # Make geometries valid and simplify to reduce size
        merged["geometry"] = shapely.make_valid(
            shapely.simplify(merged.geometry.values, simplify_tolerance)
        )
        merged = merged[~merged.geometry.is_empty & merged.geometry.notna()]

        merged_sindex = merged.sindex

        if verbose:
            logger.info({"message": f"dissolving {habitat} by location"})

        # Clean location geometries
        location_geoms = (
            regions.dropna(subset=["location"])
            .drop_duplicates(subset=["location"])
            .set_index("location")
            .geometry.sort_index()
        )

        # Dissolve in parallel by location
        jobs = []
        for location, location_geom in location_geoms.items():
            if location_geom is None or location_geom.is_empty:
                continue
            indices = merged_sindex.query(location_geom, predicate="intersects")
            if len(indices) == 0:
                continue
            jobs.append((location, merged.geometry.values[indices], location_geom))

        results = Parallel(n_jobs=n_jobs, backend="loky")(
            delayed(_clip_and_union_habitat)(location, parts, location_geom, batch_size)
            for location, parts, location_geom in tqdm(jobs)
        )

        habitat_by_location = gpd.GeoDataFrame(
            [{**result, "habitat": habitat} for result in results if result is not None],
            geometry="geometry",
            crs="EPSG:4326",
        )

        # Union all the geometries to get the global area
        if verbose:
            logger.info({"message": f"computing global {habitat} area"})
        global_area_km2 = (
            get_area_km2(robust_unary_union(merged.geometry.values)) if len(merged) > 0 else 0.0
        )

        global_area_file_name = global_area_file_pattern.format(habitat=habitat)
        save_json_to_gcs(
            bucket,
            {"global_area_km2": global_area_km2},
            global_area_file_name,
            project,
            verbose,
        )

        by_location_file_name = by_location_file_pattern.format(habitat=habitat)

        # Upload the dissolved per-location habitat layer to GCS
        upload_gdf(
            bucket,
            habitat_by_location,
            by_location_file_name,
            project_id=project,
            verbose=verbose,
            timeout=600,
        )

        del merged, habitat_by_location
        gc.collect()


def process_terrestrial_biome_raster(
    biome_raster_path: Path = BIOME_RASTER_PATH,
    processed_biome_raster_path: Path = PROCESSED_BIOME_RASTER_PATH,
    func: Callable = reclass_function,
    f_args: tuple = None,
    f_kwargs: dict = None,
    bucket: str = BUCKET,
    verbose: bool = True,
) -> None:
    """
    Downloads a raster file from GCS, processes it tile-by-tile using a user-defined function,
    saves the processed result locally, and uploads it back to GCS.

    Parameters
    ----------
    biome_raster_path : Path
        Path to the input raster in the GCS bucket.
    processed_biome_raster_path : Path
        Destination path for the processed raster in the GCS bucket.
    func : Callable
        A function that will be applied to each tile of the raster.
    f_args : Tuple
        Positional arguments to pass to the processing function.
    f_kwargs : Dict
        Keyword arguments to pass to the processing function.
    bucket : str
        Name of the GCS bucket.
    verbose : bool
        If True, prints logging messages for progress tracking.

    Returns
    -------
    None
    """

    num_workers = 200

    out_data_profile = {
        "dtype": rasterio.uint8,
        "count": 1,
        "compress": "lzw",
        "tiled": True,
        "blockxsize": 512,
        "blockysize": 512,
    }

    local_biome_raster_path = biome_raster_path.split("/")[-1]
    if verbose:
        logger.info({"message": f"downloading {biome_raster_path} to {local_biome_raster_path}"})
    client = storage.Client()
    bucket = client.bucket(bucket)
    blob = bucket.blob(biome_raster_path)
    blob.download_to_filename(local_biome_raster_path)

    fn_out = processed_biome_raster_path.split("/")[-1]

    if verbose:
        logger.info({"message": f"processing raster and saving to {fn_out}"})
    with rasterio.open(local_biome_raster_path) as src:
        # Create a destination dataset based on source params. The
        # destination will be tiled, and we'll process the tiles
        # concurrently.
        profile = src.profile.copy()
        profile.update(**out_data_profile)

        with rasterio.open(fn_out, "w", **profile) as dst:
            windows = [window for ij, window in dst.block_windows()]
            read_lock = threading.Lock()
            write_lock = threading.Lock()

            def process(window):
                status_message = {
                    "diagnostics": {},
                    "messages": [f"Processing chunk: {window}"],
                    "return_val": None,
                }
                # read the chunk
                try:
                    status_message["messages"].append("reading data")

                    with read_lock:
                        data = src.read(window=window)

                    status_message["messages"].append("processing data")
                    result = func(data, *f_args or (), **f_kwargs or {})

                    status_message["messages"].append("writing data")
                    with write_lock:
                        dst.write(result, window=window)

                    status_message["messages"].append("success in processing chunk")

                except Exception as e:
                    status_message["diagnostics"]["error"] = e

                return status_message

            # We map the process() function over the list of
            # windows.

            futures = []

            with (
                concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor,
                tqdm(total=len(windows), desc="Computing raster stats", unit="chunk") as p_bar,
            ):
                for _, window in enumerate(windows):
                    futures.append(executor.submit(process, window))

                results = []
                for f in futures:
                    results.append(f.result())
                    p_bar.update(1)

            dst.build_overviews([2, 4, 8, 16, 32, 64], rasterio.enums.Resampling.mode)
            dst.update_tags(ns="rio_overview", resampling="average")

    if verbose:
        logger.info({"message": f"saving processed raster to {processed_biome_raster_path}"})
    upload_file_to_gcs(bucket, fn_out, processed_biome_raster_path)

    if verbose:
        logger.info({"message": "finished uploading"})


def generate_terrestrial_biome_stats_country(
    land_cover_classes: dict = LAND_COVER_CLASSES,
    country_stats_filename: str = COUNTRY_TERRESTRIAL_HABITATS_FILE_NAME,
    raster_path: str = PROCESSED_BIOME_RASTER_PATH,
    gadm_file_name: str = GADM_FILE_NAME,
    bucket: str = BUCKET,
    project: str = PROJECT,
    tolerance: float = terrestrial_tolerance,
    verbose: bool = True,
):
    gadm_file_name = add_tolerance_suffix(gadm_file_name, tolerance)

    logger.info({"message": "loading and simplifying GADM geometries"})
    gadm = read_json_df(bucket, gadm_file_name, verbose=verbose)

    if verbose:
        logger.info({"message": f"downloading raster from {raster_path}"})
    local_raster_path = raster_path.split("/")[-1]
    download_file_from_gcs(bucket, raster_path, local_raster_path, verbose=False)

    if verbose:
        logger.info({"message": "getting country habitat stats"})
    country_stats = []
    with rasterio.open(local_raster_path) as src:
        for country in tqdm(gadm["location"].unique()):
            st = datetime.datetime.now()
            country_poly = gadm[gadm["location"] == country].iloc[0]["geometry"]
            tile_geoms = tile_geometry(country_poly, src.transform)

            results = []
            for tile in tile_geoms:
                entry = get_cover_areas(
                    src, [mapping(tile)], country, "location", land_cover_classes
                )
                if entry is not None:
                    results.append(entry)

            results = pd.DataFrame(results)
            cs = results[[c for c in results.columns if c != "location"]].agg("sum").to_dict()
            cs["location"] = country

            country_stats.append(cs)
            fn = datetime.datetime.now()
            if verbose:
                elapsed_seconds = round((fn - st).total_seconds())
                logger.info(
                    {
                        "message": f"processed {len(tile_geoms)} tiles within {country}'s PAs "
                        f"in {elapsed_seconds} seconds"
                    }
                )

    country_stats = pd.DataFrame(country_stats)

    upload_dataframe(
        bucket,
        country_stats,
        country_stats_filename,
        project_id=project,
        verbose=verbose,
    )

    return country_stats
