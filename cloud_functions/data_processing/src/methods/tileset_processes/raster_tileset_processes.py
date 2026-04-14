from src.core.map_params import (
    CORAL_REEF_COLOR_RAMP,
    CORAL_REEF_DOMAIN,
    CORAL_REEF_MAX_ZOOM,
    CORAL_REEF_TILESET_ARCHIVE_FILE,
    CORAL_REEF_TILESET_FILE,
    CORAL_REEF_TILESET_NAME,
    PMTILES_BUCKET,
)
from src.core.params import BUCKET, CORAL_REEF_SOURCE_FILE
from src.utils.gcp import upload_file_to_gcs
from src.utils.logger import Logger
from src.utils.tileset_pipelines.raster_tile_pipeline import (
    PMTilesetConfig,
    run_raster_tileset_pipeline,
)

logger = Logger()


def create_and_update_climate_resilient_coral_tileset(
    source_bucket: str = BUCKET,
    source_blob: str = CORAL_REEF_SOURCE_FILE,
    output_bucket: str = PMTILES_BUCKET,
    output_blob: str = CORAL_REEF_TILESET_FILE,
    archive_bucket: str = BUCKET,
    archive_blob: str = CORAL_REEF_TILESET_ARCHIVE_FILE,
    display_name: str = CORAL_REEF_TILESET_NAME,
    color_ramp: str = CORAL_REEF_COLOR_RAMP,
    domain: tuple[float, float] = CORAL_REEF_DOMAIN,
    max_zoom: int = CORAL_REEF_MAX_ZOOM,
    verbose: bool = False,
):
    try:
        if verbose:
            logger.info({"message": f"Creating and updating {display_name} raster tileset..."})

        config = PMTilesetConfig(
            source_bucket=source_bucket,
            source_blob=source_blob,
            output_bucket=output_bucket,
            output_blob=output_blob,
            display_name=display_name,
            color_ramp=color_ramp,
            domain=domain,
            max_zoom=max_zoom,
            verbose=verbose,
            keep_temp=True,  # Keep temp so we can archive
        )

        result = run_raster_tileset_pipeline(config)

        # Archive a dated copy to the data-processing bucket
        if archive_blob and result.get("temp_dir"):
            pmtiles_local = f"{result['temp_dir']}/output.pmtiles"
            if verbose:
                logger.info({"message": f"Archiving PMTiles to {archive_bucket}/{archive_blob}"})
            upload_file_to_gcs(
                bucket=archive_bucket,
                file_name=pmtiles_local,
                blob_name=archive_blob,
            )

        return result

    except Exception as error:
        logger.error(
            {
                "message": f"Error creating and updating {display_name} raster tileset",
                "error": str(error),
            }
        )
        raise
