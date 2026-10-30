import geopandas as gpd
import pandas as pd
from skytruth_shared_datasets import Catalog

from src.core.commons import (
    add_tolerance_suffix,
    load_high_seas,
    load_iho_regions,
    process_buffered_iho,
)
from src.core.params import (
    BUCKET,
    BUFFERED_MARINE_LOCATIONS_FILE_NAME,
    GADM_EEZ_UNION_FILE_NAME,
    NEAR_SHORE_BUFFER_KM,
    NEAR_SHORE_IHO_FILE_NAME,
    TOLERANCE,
)
from src.core.processors import clean_geometries
from src.utils.gcp import read_json_df, upload_gdf
from src.utils.logger import Logger

logger = Logger()


def process_near_shore_iho(
    near_shore_iho_file_name: str = NEAR_SHORE_IHO_FILE_NAME,
    gadm_eez_union_file_name: str = GADM_EEZ_UNION_FILE_NAME,
    buffered_marine_locations_file_name: str = BUFFERED_MARINE_LOCATIONS_FILE_NAME,
    km: int = NEAR_SHORE_BUFFER_KM,
    tolerance: float = TOLERANCE,
    bucket: str = BUCKET,
    n_jobs: int = -1,
    verbose: bool = True,
):
    """Build the near-shore IHO sea areas, and from them the buffered marine locations.

    Each IHO sea area is buffered ``km`` inshore, clipped against its neighbours,
    and saved to ``near_shore_iho_file_name``. Those sea areas are then
    concatenated with the land/EEZ union — which ``process_eez_land_union`` must
    already have written — and the high seas into the buffered marine locations,
    the location set the marine habitat stats and the unprotected-habitat layers
    are both built over.
    """
    if verbose:
        logger.info({"message": "fetching iho-world-seas from SkyTruth shared-datasets"})

    ref = Catalog.load().fetch("iho-world-seas", "fgb", access="public")
    water_bodies = gpd.read_file(ref.cache_path)

    near_shore = process_buffered_iho(water_bodies, km=km, n_jobs=n_jobs)

    if verbose:
        logger.info(
            {"message": f"saving near-shore IHO to gs://{bucket}/{near_shore_iho_file_name}"}
        )

    upload_gdf(bucket, near_shore, near_shore_iho_file_name, verbose=verbose)

    if verbose:
        logger.info({"message": "loading eez/land union for the buffered marine locations"})
    gadm_eez_union = read_json_df(
        bucket, add_tolerance_suffix(gadm_eez_union_file_name, tolerance), verbose=verbose
    )

    iho = load_iho_regions(buffer=True)[["location", "geometry"]]
    high_seas = load_high_seas(bucket)[["location", "geometry"]]
    if tolerance is not None:
        if verbose:
            logger.info(
                {"message": f"simplifying near-shore IHO and high seas with tolerance {tolerance}"}
            )
        iho["geometry"] = iho["geometry"].simplify(tolerance=tolerance)
        high_seas["geometry"] = high_seas["geometry"].simplify(tolerance=tolerance)

    buffered_marine_locations = pd.concat(
        [gadm_eez_union[["location", "geometry"]], iho, high_seas], ignore_index=True
    ).pipe(clean_geometries)

    out_fn = add_tolerance_suffix(buffered_marine_locations_file_name, tolerance)
    if verbose:
        logger.info({"message": f"uploading buffered marine locations to {out_fn}"})
    upload_gdf(bucket, buffered_marine_locations, out_fn)

    return near_shore
