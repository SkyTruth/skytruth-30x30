import gc

import geopandas as gpd
import pandas as pd

from src.core.commons import add_tolerance_suffix
from src.core.params import (
    BUCKET,
    GADM_FILE_NAME,
    GADM_ZIPFILE_NAME,
    RELATED_COUNTRIES_FILE_NAME,
    TOLERANCE,
)
from src.core.processors import clean_geometries
from src.utils.gcp import read_json_from_gcs, read_zipped_gpkg_from_gcs, upload_gdf
from src.utils.logger import Logger

logger = Logger()


def process_gadm_geoms(
    gadm_file_name: str = GADM_FILE_NAME,
    gadm_zipfile_name: str = GADM_ZIPFILE_NAME,
    bucket: str = BUCKET,
    related_countries_file_name: str = RELATED_COUNTRIES_FILE_NAME,
    tolerance: float = TOLERANCE,
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
