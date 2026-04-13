from src.utils.logger import Logger
from src.utils.raster_tileset_pipeline import PMTilesetConfig, run_raster_tileset_pipeline

logger = Logger()


def create_and_update_coral_reef_tileset(
    bucket: str = "dev-cogs",
    source_blob: str = "climate-resilient-corals.tif",
    output_blob: str = "maps/coral_reef_prioritization.pmtiles",
    display_name: str = "Coral Reef Prioritization",
    color_ramp: str = "coral",
    domain: tuple[float, float] = (0.0, 1.0),
    max_zoom: int = 10,
    verbose: bool = False,
):
    try:
        if verbose:
            logger.info({"message": f"Creating and updating {display_name} raster tileset..."})

        cfg = PMTilesetConfig(
            bucket=bucket,
            source_blob=source_blob,
            output_blob=output_blob,
            display_name=display_name,
            color_ramp=color_ramp,
            domain=domain,
            max_zoom=max_zoom,
            verbose=verbose,
        )

        return run_raster_tileset_pipeline(cfg)

    except Exception as e:
        logger.error(
            {
                "message": f"Error creating and updating {display_name} raster tileset",
                "error": str(e),
            }
        )
        raise
