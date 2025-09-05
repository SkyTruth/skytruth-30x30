import os
import tempfile

from src.core.map_params import (
    EEZ_TILESET_FILE,
    EEZ_TILESET_ID,
    EEZ_TILESET_NAME,
    EEZ_TOLERANCE,
    MAPBOX_TOKEN,
    MAPBOX_USER,
    MARINE_REGIONS_TILESET_FILE,
    MARINE_REGIONS_TILESET_ID,
    MARINE_REGIONS_TILESET_NAME,
)
from src.core.map_processors import generate_mbtiles, upload_to_mapbox
from src.core.params import (
    BUCKET,
    EEZ_FILE_NAME,
    EEZ_MULTIPLE_SOV_FILE_NAME,
    LOCATIONS_TRANSLATED_FILE_NAME,
    REGIONS_FILE_NAME,
)
from src.core.processors import add_translations
from src.utils.gcp import read_dataframe, read_json_df, read_json_from_gcs, upload_file_to_gcs
from src.utils.logger import Logger

logger = Logger()


def create_and_update_eez_tileset(
    bucket: str = BUCKET,
    source_file: str = EEZ_MULTIPLE_SOV_FILE_NAME,
    tileset_file: str = EEZ_TILESET_FILE,
    verbose: bool = False,
):
    try:
        _check_map_box_credentials()

        if verbose:
            print("Creating and updating EEZ tileset...")

        with tempfile.TemporaryDirectory() as temp_dir:
            tileset_local = os.path.join(temp_dir, f"{EEZ_TILESET_ID}.mbtiles")
            geojson_local = os.path.join(temp_dir, "eez.geojson")

            if verbose:
                print("Downloading source EEZ file from GCS...")

            input_file = source_file.replace(".geojson", f"_{EEZ_TOLERANCE}.geojson")

            eez_df = read_json_df(bucket, input_file, verbose=verbose)
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
    source_file: str = EEZ_FILE_NAME,
    tileset_file: str = MARINE_REGIONS_TILESET_FILE,
    verbose: bool = False,
):
    try:
        _check_map_box_credentials()

        if verbose:
            print("Creating and updating Marine Regions tileset...")

        with tempfile.TemporaryDirectory() as temp_dir:
            tileset_local = os.path.join(temp_dir, f"{MARINE_REGIONS_TILESET_ID}.mbtiles")
            geojson_local = os.path.join(temp_dir, "marine_regions.geojson")

            if verbose:
                print("Downloading source Marine Regions file from GCS...")

            eez_in_file = source_file.replace(".geojson", f"_{EEZ_TOLERANCE}.geojson")

            eez_df = read_json_df(bucket, eez_in_file, verbose=verbose)
            translations_df = read_dataframe(
                bucket, LOCATIONS_TRANSLATED_FILE_NAME, verbose=verbose
            )
            regions = read_json_from_gcs(bucket, REGIONS_FILE_NAME, verbose)

            iso_to_region = {
                iso: region_id for region_id, iso_list in regions.items() for iso in iso_list
            }

            eez_df["region_id"] = eez_df["location"].map(iso_to_region)
            region_gdf = (
                eez_df.dissolve(by="region_id", as_index=False)
                .drop(
                    columns=[
                        "MRGID",
                        "AREA_KM2",
                        "has_shared_marine_area",
                        "index",
                        "code",
                        "location",
                    ],
                    errors="ignore",
                )
                .pipe(add_translations, translations_df, "region_id", "code")
                .dropna(subset=["region_id"])
            )

            region_gdf["geometry"] = region_gdf["geometry"].make_valid()
            region_gdf.to_file(geojson_local, driver="GeoJSON")

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
                tileset_id=MARINE_REGIONS_TILESET_ID,
                display_name=MARINE_REGIONS_TILESET_NAME,
                username=MAPBOX_USER,
                token=MAPBOX_TOKEN,
                verbose=verbose,
            )

    except Exception as excep:
        logger.error(
            {"message": "Error creating and updating Marine Regions tileset", "error": str(excep)}
        )
        raise excep


def _check_map_box_credentials():
    if not MAPBOX_USER or not MAPBOX_TOKEN:
        raise ValueError("MAPBOX_USERNAME and MAPBOX_TOKEN environment variables must be set")
