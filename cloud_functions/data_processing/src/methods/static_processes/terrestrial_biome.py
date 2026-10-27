import concurrent.futures
import datetime
import threading
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import rasterio
from google.cloud import storage
from shapely.geometry import mapping
from tqdm.auto import tqdm

from src.core.commons import add_tolerance_suffix, get_cover_areas
from src.core.land_cover_params import (
    BIOME_RASTER_PATH,
    LAND_COVER_CLASSES,
    reclass_function,
)
from src.core.params import (
    BUCKET,
    COUNTRY_TERRESTRIAL_HABITATS_FILE_NAME,
    GADM_FILE_NAME,
    PROCESSED_BIOME_RASTER_PATH,
    PROJECT,
    TOLERANCE,
)
from src.utils.gcp import (
    download_file_from_gcs,
    read_json_df,
    upload_dataframe,
    upload_file_to_gcs,
)
from src.utils.geo import tile_geometry
from src.utils.logger import Logger

logger = Logger()


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
    tolerance: float = TOLERANCE,
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
