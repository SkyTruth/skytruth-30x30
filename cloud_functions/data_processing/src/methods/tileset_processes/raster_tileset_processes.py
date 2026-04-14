from src.core.map_params import (
    CORAL_REEF_COLOR_RAMP,
    CORAL_REEF_DOMAIN,
    CORAL_REEF_MAX_ZOOM,
    CORAL_REEF_TILESET_FILE,
    CORAL_REEF_TILESET_NAME,
)
from src.core.params import CORAL_REEF_SOURCE_FILE, RASTER_BUCKET
from src.utils.logger import Logger
from src.utils.tileset_pipelines.raster_tile_pipeline import (
    PMTilesetConfig,
    run_raster_tileset_pipeline,
)

logger = Logger()


def create_and_update_coral_reef_tileset(
    bucket: str = RASTER_BUCKET,
    source_blob: str = CORAL_REEF_SOURCE_FILE,
    output_blob: str = CORAL_REEF_TILESET_FILE,
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
            bucket=bucket,
            source_blob=source_blob,
            output_blob=output_blob,
            display_name=display_name,
            color_ramp=color_ramp,
            domain=domain,
            max_zoom=max_zoom,
            verbose=verbose,
        )

        return run_raster_tileset_pipeline(config)

    except Exception as error:
        logger.error(
            {
                "message": f"Error creating and updating {display_name} raster tileset",
                "error": str(error),
            }
        )
        raise
