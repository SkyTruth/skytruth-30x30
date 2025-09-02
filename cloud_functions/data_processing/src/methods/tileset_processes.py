import os
import tempfile

import geopandas as gdp

from src.core.map_params import (
    EEZ_TILESET_FILE,
    EEZ_TILESET_ID,
    EEZ_TILESET_NAME,
    MAPBOX_TOKEN,
    MAPBOX_USER,
    MARINE_REGIONS_TILESET_FILE,
    MARINE_REGIONS_TILESET_ID,
)
from src.core.map_processors import generate_mbtiles, upload_to_mapbox
from src.core.params import BUCKET, EEZ_MULTIPLE_SOV_FILE_NAME
from src.utils.gcp import read_json_df, upload_file_to_gcs
from src.utils.logger import Logger

logger = Logger()


def create_and_update_eez_tileset(
    bucket: str = BUCKET,
    source_file: str = EEZ_MULTIPLE_SOV_FILE_NAME,
    tileset_file: str = EEZ_TILESET_FILE,
    verbose: bool = False,
):
    try:
        if not MAPBOX_USER or not MAPBOX_TOKEN:
            raise ValueError("MAPBOX_USERNAME and MAPBOX_TOKEN environment variables must be set")

        if verbose:
            print("Creating and updating EEZ tileset...")

        with tempfile.TemporaryDirectory() as temp_dir:
            tileset_local = os.path.join(temp_dir, f"{EEZ_TILESET_ID}.mbtiles")
            geojson_local = os.path.join(temp_dir, "eez.geojson")

            if verbose:
                print("Downloading source EEZ file from GCS...")

            eez_df = read_json_df(bucket, source_file, verbose=verbose)
            eez_df = gdp.read_file(geojson_local)
            eez_df.drop(columns=["MRGID", "AREA_KM2"], errors="ignore", inplace=True)
            eez_df["geometry"] = eez_df["geometry"].make_valid()
            eez_df.to_file(geojson_local, driver="GeoJSON")

            generate_mbtiles(
                input_file=geojson_local,
                output_file=tileset_local,
                verbose=verbose,
            )

            if verbose:
                print("Uploading tileset to GCS...")
            upload_file_to_gcs(bucket=bucket, file_name=tileset_local, blob_name=tileset_file)

            if verbose:
                print("Uploading tileset to Mapbox...")

            upload_to_mapbox(
                source=tileset_local,
                tileset_id=EEZ_TILESET_ID,
                display_name=EEZ_TILESET_NAME,
                username=MAPBOX_USER,
                token=MAPBOX_TOKEN,
                verbose=verbose,
            )

    except Exception as excep:
        logger.error({"message": "Error creating and updating EEZ tileset", "error": str(excep)})
        raise excep


def create_and_update_marine_regions_tileset(
    bucket: str = BUCKET,
    source_file: str = EEZ_MULTIPLE_SOV_FILE_NAME,
    tileset_file: str = MARINE_REGIONS_TILESET_FILE,
    verbose: bool = False,
):
    try:
        if not MAPBOX_USER or not MAPBOX_TOKEN:
            raise ValueError("MAPBOX_USERNAME and MAPBOX_TOKEN environment variables must be set")

        if verbose:
            print("Creating and updating Marine Regions tileset...")

        with tempfile.TemporaryDirectory() as temp_dir:
            tileset_local = os.path.join(temp_dir, f"{MARINE_REGIONS_TILESET_ID}.mbtiles")
            geojson_local = os.path.join(temp_dir, "eez.geojson")

            if verbose:
                print("Downloading source Marine Regions file from GCS...")

            eez_df = read_json_df(bucket, source_file, verbose=verbose)
            eez_df.drop(columns=["MRGID", "AREA_KM2"], errors="ignore", inplace=True)
            eez_df["geometry"] = eez_df["geometry"].make_valid()
            eez_df.to_file(geojson_local, driver="GeoJSON")

            generate_mbtiles(
                input_file=geojson_local,
                output_file=tileset_local,
                verbose=verbose,
            )

            if verbose:
                print("Uploading tileset to GCS...")
            upload_file_to_gcs(bucket=bucket, file_name=tileset_local, blob_name=tileset_file)

            if verbose:
                print("Uploading tileset to Mapbox...")

            upload_to_mapbox(
                source=tileset_local,
                tileset_id=EEZ_TILESET_ID,
                display_name=EEZ_TILESET_NAME,
                username=MAPBOX_USER,
                token=MAPBOX_TOKEN,
                verbose=verbose,
            )

    except Exception as excep:
        logger.error({"message": "Error creating and updating EEZ tileset", "error": str(excep)})
        raise excep
