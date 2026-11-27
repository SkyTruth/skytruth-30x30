import gc
import glob
import os
import traceback

import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from joblib import Parallel, delayed
from shapely import wkb
from shapely.geometry import MultiPoint, Point
from tqdm.auto import tqdm

from src.core.processors import choose_pa_area
from src.utils.logger import Logger

logger = Logger()


def stream_parquet_chunks(paths, batch_size=1000):
    """
    Lazily stream GeoDataFrame chunks from one or more Parquet files.
    """
    for path in paths:
        try:
            parquet_file = pq.ParquetFile(path)
        except Exception as e:
            logger.info({"message": f"Skipping {path}: {e}"})
            continue

        for batch in parquet_file.iter_batches(batch_size=batch_size):
            df = batch.to_pandas()
            df["geometry"] = df["geometry"].apply(wkb.loads)
            gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")
            yield gdf


def calculate_radius(rep_area: float, geom) -> float:
    """
    Radius in metres of a circle whose area matches rep_area, divided evenly
    across the parts of a multipart geometry.
    """
    npts = len(geom.geoms) if geom.geom_type == "MultiPoint" else 1
    return (((rep_area / npts) * 1e6) / np.pi) ** 0.5


def create_point_buffer(df: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Create circular buffer polygons around point geometries based on a
    representative area field.
    """
    df = df.to_crs("ESRI:54009")
    df["geometry"] = df.apply(
        lambda row: row.geometry.buffer(calculate_radius(row["REP_AREA"], row["geometry"])),
        axis=1,
    )
    return df.to_crs("EPSG:4326").copy()


def buffer_if_point(row, crs):
    """
    Conditionally buffer a single point or multipoint geometry based on a
    representative area value.
    """

    # Do not buffer MAB reserves as area can be unreliable
    # Points stay in PA table but not used in statistics (see filter_protected_planet)
    rep_area = row.REP_AREA if row["DESIG_ENG"] != "UNESCO-MAB Biosphere Reserve" else 0

    g = row.geometry
    if rep_area and rep_area > 0 and isinstance(g, (Point, MultiPoint)):
        # build a 1-row GeoDataFrame with the same CRS
        row_gdf = gpd.GeoDataFrame(
            row.to_frame().T,
            geometry="geometry",
            crs=crs,  # 1-row DataFrame
        )
        buffed = create_point_buffer(row_gdf)  # your existing function
        return buffed.geometry.iloc[0]
    return g


def simplify_chunk(chunk, tolerance):
    """
    Simplify and buffer geometries in a GeoDataFrame chunk.
    """

    try:
        chunk["bbox"] = chunk.geometry.apply(lambda g: g.bounds if g is not None else None)

        chunk = choose_pa_area(chunk)
        crs = chunk.crs
        chunk["geometry"] = chunk.apply(lambda r: buffer_if_point(r, crs), axis=1)

        chunk = chunk.loc[chunk.geometry.is_valid]
        chunk.geometry = chunk.geometry.simplify(tolerance=tolerance, preserve_topology=True)
        return chunk
    except MemoryError as e:
        logger.error({"message": "MemoryError simplifying chunk", "error": str(e)})
        return None
    except Exception as e:
        logger.warning({"message": f"Error simplifying chunk: {e}"})
        return None
    finally:
        del chunk
        gc.collect()


def process_all_files(paths, tolerance, batch_size=1000, n_jobs=-1, verbose=True):
    """
    Process multiple Parquet files in parallel, simplifying geometries
    in streamed chunks while managing memory and logging progress.
    """

    # Count total number of rows across all parquet files
    total_rows = 0
    for p in paths:
        parquet_file = pq.ParquetFile(p)
        total_rows += parquet_file.metadata.num_rows

    # Estimate how many chunk batches will be processed
    est_batches = int(np.ceil(total_rows / batch_size))
    if verbose:
        logger.info(
            {"message": (f"Processing parquet files: {total_rows} rows, ~{est_batches} batches")}
        )

    try:
        # Simplify geometries in parallel batches
        results = Parallel(n_jobs=n_jobs, backend="loky", timeout=60 * 60)(
            delayed(simplify_chunk)(
                chunk,
                tolerance,
            )
            for chunk in tqdm(
                stream_parquet_chunks(paths, batch_size=batch_size), total=est_batches
            )
        )
        if verbose:
            logger.info({"message": "Completed parallel processing of parquet files"})

        # return concatenated results
        return pd.concat([r for r in results if r is not None], ignore_index=True)

    except Exception as e:
        tb = traceback.format_exc()
        logger.error(
            {
                "message": f"process_all_files failed: {type(e).__name__}: {e}",
                "traceback": tb,
            }
        )
        raise


def process_protected_area_geoms(pa_dir, tolerance, batch_size=1000, n_jobs=-1, verbose=True):
    """
    Simplifies every protected area geometry in the parquets under pa_dir.
    """
    parquet_files = glob.glob(os.path.join(pa_dir, "*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(f"No parquet files found in {pa_dir}")

    results = process_all_files(
        parquet_files,
        tolerance=tolerance,
        batch_size=batch_size,
        n_jobs=n_jobs,
        verbose=verbose,
    )
    return results
