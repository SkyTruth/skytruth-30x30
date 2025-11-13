import datetime
import gc
import glob
import os
import shutil
import subprocess
import sys
import textwrap
import traceback
import zipfile
from io import BytesIO

import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests
from joblib import Parallel, delayed

# from pyogrio import read_dataframe
from shapely import wkb
from shapely.geometry import MultiPoint, Point, shape
from tqdm.auto import tqdm

from src.core.commons import (
    download_file_with_progress,
    download_mpatlas_zone,
    show_container_mem,
    show_mem,
    unzip_file,
)
from src.core.params import (
    ARCHIVE_MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    ARCHIVE_MPATLAS_FILE_NAME,
    ARCHIVE_PROTECTED_SEAS_FILE_NAME,
    ARCHIVE_WDPA_COUNTRY_LEVEL_FILE_NAME,
    ARCHIVE_WDPA_GLOBAL_LEVEL_FILE_NAME,
    BUCKET,
    MPATLAS_COUNTRY_LEVEL_API_URL,
    MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    MPATLAS_FILE_NAME,
    MPATLAS_META_FILE_NAME,
    MPATLAS_URL,
    PP_API_KEY,
    PROJECT,
    PROTECTED_SEAS_FILE_NAME,
    PROTECTED_SEAS_URL,
    TOLERANCES,
    WDPA_API_URL,
    WDPA_COUNTRY_LEVEL_FILE_NAME,
    WDPA_GLOBAL_LEVEL_FILE_NAME,
    WDPA_GLOBAL_LEVEL_URL,
    WDPA_MARINE_FILE_NAME,
    WDPA_META_FILE_NAME,
    WDPA_TERRESTRIAL_FILE_NAME,
    WDPA_URL,
)
from src.core.processors import calculate_area, choose_pa_area
from src.utils.gcp import (
    duplicate_blob,
    read_json_from_gcs,
    upload_dataframe,
    upload_gdf,
)
from src.utils.logger import Logger

logger = Logger()

pa.set_memory_pool(pa.default_memory_pool())
pa.default_memory_pool().release_unused()


def download_mpatlas_country(
    bucket: str = BUCKET,
    project: str = PROJECT,
    url: str = MPATLAS_COUNTRY_LEVEL_API_URL,
    current_filename: str = MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    archive_filename: str = ARCHIVE_MPATLAS_COUNTRY_LEVEL_FILE_NAME,
):
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

    upload_dataframe(bucket, pd.DataFrame(data), archive_filename, project_id=project, verbose=True)
    duplicate_blob(bucket, archive_filename, current_filename, verbose=True)


def download_mpatlas(
    url: str = MPATLAS_URL,
    bucket: str = BUCKET,
    project: str = PROJECT,
    mpatlas_filename: str = MPATLAS_FILE_NAME,
    meta_file_name: str = MPATLAS_META_FILE_NAME,
    archive_mpatlas_filename: str = ARCHIVE_MPATLAS_FILE_NAME,
    mpatlas_country_url: str = MPATLAS_COUNTRY_LEVEL_API_URL,
    mpatlas_country_file_name: str = MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    archive_mpatlas_country_file_name: str = ARCHIVE_MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    verbose: bool = True,
    project_id: str = PROJECT,
) -> None:
    def safe_shape(geom):
        try:
            return shape(geom) if geom else None
        except Exception:
            return None

    download_mpatlas_country(
        bucket=bucket,
        project=project,
        url=mpatlas_country_url,
        current_filename=mpatlas_country_file_name,
        archive_filename=archive_mpatlas_country_file_name,
    )

    download_mpatlas_zone(
        url=url,
        bucket=bucket,
        filename=mpatlas_filename,
        archive_filename=archive_mpatlas_filename,
        verbose=verbose,
    )

    if verbose:
        print(f"loading MPAtlas from {mpatlas_filename}")
    mpa = read_json_from_gcs(bucket, mpatlas_filename)

    mpa_all = gpd.GeoDataFrame(
        [
            {**feat["properties"], "geometry": safe_shape(feat.get("geometry"))}
            for feat in mpa["features"]
        ],
        geometry="geometry",
        crs="EPSG:4326",
    )

    # add area column
    if verbose:
        print("calculating MPA area (calculated_area_km2)")
    mpa_all = calculate_area(mpa_all, output_area_column="calculated_area_km2")

    # add bounding box column
    if verbose:
        print("calculating MPA bounding box (bbox)")
    mpa_all["bbox"] = mpa_all.geometry.apply(lambda g: g.bounds if g is not None else None)

    # Upload metadata (no geometry)
    if verbose:
        print(f"saving metadata to {meta_file_name}")
    upload_dataframe(
        bucket,
        mpa_all.drop(columns="geometry"),
        meta_file_name,
        project_id=project_id,
        verbose=verbose,
    )


def download_protected_seas(
    url: str = PROTECTED_SEAS_URL,
    bucket: str = BUCKET,
    filename: str = PROTECTED_SEAS_FILE_NAME,
    archive_filename: str = ARCHIVE_PROTECTED_SEAS_FILE_NAME,
    project: str = PROJECT,
    verbose: bool = True,
) -> None:
    """
    Downloads Protected Seas data from the provided URL, processes it into a DataFrame,
    and uploads both a current version and an archived version to Google Cloud Storage.

    Parameters:
    ----------
    url : str
        The URL to fetch the Protected Seas data from.
    bucket : str
        GCS bucket name where the data will be saved.
    filename : str
        Blob name for the current, active version of the data.
    archive_filename : str
        Blob name for the archived version of the data.
    project : str
        Google Cloud project ID used for authentication during upload.
    verbose : bool, optional
        If True, prints progress and status messages. Default is True.
    """
    response = requests.get(url)
    response.raise_for_status()

    data = pd.DataFrame(response.json())

    data["includes_multi_jurisdictional_areas"] = data["includes_multi_jurisdictional_areas"].map(
        {"t": True, "f": False}
    )
    data = data.drop_duplicates()

    if verbose:
        print(f"saving Protected Seas to gs://{bucket}/{archive_filename}")
    upload_dataframe(bucket, data, archive_filename, project_id=project, verbose=verbose)
    duplicate_blob(bucket, archive_filename, filename, verbose=True)


def download_and_process_protected_planet_pas(
    wdpa_url: str = WDPA_URL,
    terrestrial_pa_file_name: str = WDPA_TERRESTRIAL_FILE_NAME,
    marine_pa_file_name: str = WDPA_MARINE_FILE_NAME,
    meta_file_name: str = WDPA_META_FILE_NAME,
    tolerance: list | tuple = TOLERANCES[0],
    verbose: bool = True,
    bucket: str = BUCKET,
    project_id: str = PROJECT,
    batch_size=1000,
    n_jobs=-1,
):
    def unpack_pas_to_parquet(pa_dir, verbose=True):
        def unpack_in_subprocess(zip_stem, zip_path, dir, shp, layer_name, verbose=True):
            if verbose:
                print("running subprocess to unpack shapefile into a parquet file")
            out_path = f"{dir}/{zip_stem}_{layer_name}.parquet"
            script = textwrap.dedent(f"""
                import os, glob, geopandas as gpd, gc

                # Read directly from the zip and write to parquet
                gdf = gpd.read_file(f"zip://{zip_path}!{shp}")
                gdf.to_parquet("{out_path}")

                # Clean up GeoDataFrame memory
                gdf = gpd.GeoDataFrame()
                del gdf
                gc.collect()
            """)
            subprocess.run([sys.executable, "-c", script], check=True)
            if verbose:
                print("subprocess completed")

        def unpack_parquet(zip_stem, zip_path, dir, shp, layer_name, verbose=True):
            """unpacks a single shapefile into a parquet"""

            out_path = os.path.join(dir, f"{zip_stem}_{layer_name}.parquet")
            if verbose:
                logger.info({"message": f"Converting {zip_stem}: {layer_name} to {out_path}"})
            try:
                unpack_in_subprocess(zip_stem, zip_path, dir, shp, layer_name, verbose=True)
            except Exception as e:
                logger.warning({"message": f"Error processing {layer_name}: {e}"})
            finally:
                gc.collect()
                pa.default_memory_pool().release_unused()
                show_mem("after garbage collection")
                show_container_mem("after garbage collection")

        # Define params for unpacking
        for zip_path in glob.glob(os.path.join(pa_dir, "*.zip")):
            zip_stem = os.path.splitext(os.path.basename(zip_path))[0]
            with zipfile.ZipFile(zip_path) as z:
                for shp in [n for n in z.namelist() if n.lower().endswith(".shp")]:
                    _ = unpack_parquet(
                        zip_stem,
                        zip_path,
                        pa_dir,
                        shp,
                        shp.replace(".shp", ""),
                        verbose,
                    )

                # Delete zipped files
                os.remove(zip_path)

    def remove_file_or_folder(path):
        """Delete a file or folder (recursively) if it exists."""
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
                print(f"Deleted folder and its contents: {path}")
            elif os.path.exists(path):
                os.remove(path)
                print(f"Deleted file: {path}")
            else:
                return
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Warning: could not delete {path}: {e}")

    def process_protected_area_geoms(pa_dir, tolerance=0.001, batch_size=1000, n_jobs=-1):
        def stream_parquet_chunks(path, batch_size=1000):
            parquet_file = pq.ParquetFile(path)
            for batch in parquet_file.iter_batches(batch_size=batch_size):
                df = batch.to_pandas()
                df["geometry"] = df["geometry"].apply(wkb.loads)
                gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")
                yield gdf

        def create_buffer(df: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
            def calculate_radius(rep_area: float) -> float:
                return ((rep_area * 1e6) / np.pi) ** 0.5

            df = df.to_crs("ESRI:54009")
            df["geometry"] = df.apply(
                lambda row: row.geometry.buffer(calculate_radius(row["REP_AREA"])),
                axis=1,
            )
            return df.to_crs("EPSG:4326").copy()

        def buffer_if_point(row, crs):
            g = row.geometry
            if isinstance(g, (Point, MultiPoint)) and row.REP_AREA > 0:
                # build a 1-row GeoDataFrame with the same CRS
                row_gdf = gpd.GeoDataFrame(
                    row.to_frame().T,
                    geometry="geometry",
                    crs=crs,  # 1-row DataFrame
                )
                buffed = create_buffer(row_gdf)  # your existing function
                return buffed.geometry.iloc[0]
            return g

        def simplify_chunk(chunk, tolerance=0.001):
            try:
                chunk["bbox"] = chunk.geometry.apply(lambda g: g.bounds if g is not None else None)
                chunk = choose_pa_area(chunk)
                crs = chunk.crs
                chunk["geometry"] = chunk.apply(lambda r: buffer_if_point(r, crs), axis=1)
                chunk = chunk.loc[chunk.geometry.is_valid]
                chunk.geometry = chunk.geometry.simplify(
                    tolerance=tolerance, preserve_topology=True
                )
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

        def process_one_file(p, results, tolerance=0.001, batch_size=1000, n_jobs=-1):
            try:
                parquet_file = pq.ParquetFile(p)
                total_rows = parquet_file.metadata.num_rows
                est_batches = int(np.ceil(total_rows / batch_size))
                logger.info(
                    {"message": f"Processing {p}: {total_rows} rows, ~{est_batches} batches"}
                )

                results = Parallel(n_jobs=n_jobs, backend="loky", timeout=600)(
                    delayed(simplify_chunk)(
                        chunk,
                        tolerance,
                    )
                    for chunk in tqdm(
                        stream_parquet_chunks(p, batch_size=batch_size), total=est_batches
                    )
                )

                logger.info({"message": f"Completed parallel processing for {p}"})
                return pd.concat([r for r in results if r is not None], ignore_index=True)

            except Exception as e:
                tb = traceback.format_exc()
                logger.error(
                    {
                        "message": f"process_one_file failed for {p}: {type(e).__name__}: {e}",
                        "traceback": tb,
                    }
                )
                print(tb)
                raise

        results = []
        parquet_files = glob.glob(os.path.join(pa_dir, "*.parquet"))
        if not parquet_files:
            raise FileNotFoundError(f"No parquet files found in {pa_dir}")

        for i, p in enumerate(parquet_files):
            try:
                if verbose:
                    print(f"{p}: {i + 1} of {len(parquet_files)}")

                st = datetime.datetime.now()
                result = process_one_file(p, results, tolerance, batch_size, n_jobs)
                results.append(result)
                result = pd.DataFrame()
                fn = datetime.datetime.now()

                if verbose:
                    print(f"Processed {p} in {(fn - st).total_seconds() / 60:.2f} minutes")
                show_mem("After processing")
                show_container_mem("After processing")
            except Exception as e:
                logger.error(
                    {
                        "message": f"Error processing parquet files: {type(e).__name__}: {e}",
                        "traceback": traceback.format_exc(),
                    }
                )
                raise
            finally:
                gc.collect()

        # Combine results
        return pd.concat([r for r in results if r is not None], ignore_index=True)

    print(f"Visible CPUs: {os.cpu_count()}")
    show_mem("Start")
    show_container_mem("Start")

    tmp_dir = "/tmp"
    os.makedirs(tmp_dir, exist_ok=True)

    base_zip_path = os.path.join(tmp_dir, "wdpa.zip")
    pa_dir = os.path.join(tmp_dir, "wdpa")

    if verbose:
        print(f"downloading {wdpa_url}")
    _ = download_file_with_progress(wdpa_url, base_zip_path)
    show_mem("After download")
    show_container_mem("After download")

    if verbose:
        print(f"unzipping {base_zip_path}")
    _ = unzip_file(base_zip_path, pa_dir)
    show_mem("After unzipping")
    show_container_mem("After unzipping")

    if verbose:
        print("unpacking PA shapefiles into parquet files")
    unpack_pas_to_parquet(pa_dir, verbose=verbose)
    show_mem("After unpacking")
    show_container_mem("After unpacking")

    if verbose:
        print(f"deleting {base_zip_path}")
    remove_file_or_folder(base_zip_path)
    show_mem(f"After deleting {base_zip_path}")
    show_container_mem(f"After deleting {base_zip_path}")

    if verbose:
        print("processing and simplifying protected area geometries")
    df = process_protected_area_geoms(
        pa_dir, tolerance=tolerance, batch_size=batch_size, n_jobs=n_jobs
    )

    if verbose:
        print(f"deleting {pa_dir}")
    remove_file_or_folder(pa_dir)

    if df is None:
        logger.error({"message": "process_protected_area_geoms returned None"})
        raise ValueError("Error: process_protected_area_geoms returned None")

    if verbose:
        print(f"saving wdpa metadata to {meta_file_name}")
    try:
        upload_dataframe(
            bucket,
            df.drop(columns="geometry"),
            meta_file_name,
            project_id=project_id,
            verbose=verbose,
        )
    except Exception as e:
        logger.error({"message": "Error saving metadata", "error": str(e)})

    try:
        ter_out_fn = terrestrial_pa_file_name.replace(".geojson", f"_{tolerance}.geojson")
        if verbose:
            print(f"saving and duplicating terrestrial PAs to {ter_out_fn}")
        upload_gdf(bucket, df[df["MARINE"].eq("0")], ter_out_fn)
        duplicate_blob(bucket, ter_out_fn, f"archive/{ter_out_fn}", verbose=verbose)

        mar_out_fn = marine_pa_file_name.replace(".geojson", f"_{tolerance}.geojson")
        if verbose:
            print(f"saving and duplicating marine PAs to {mar_out_fn}")
        upload_gdf(bucket, df[df["MARINE"].isin(["1", "2"])], mar_out_fn)
        duplicate_blob(bucket, mar_out_fn, f"archive/{mar_out_fn}", verbose=verbose)
    except Exception as e:
        logger.error({"message": "Error saving simplified PAs", "error": str(e)})

    if verbose:
        print("Cleaning up")
    df = pd.DataFrame()
    del df


def download_protected_planet_global(
    current_filename: str,
    archive_filename: str,
    project_id: str = PROJECT,
    url: str = WDPA_GLOBAL_LEVEL_URL,
    bucket: str = BUCKET,
    verbose: bool = True,
) -> None:
    """
    Downloads the Global Protected Planet statistics CSV from the specified URL,
    uploads it to Google Cloud Storage, and stores both an archived and current version.

    Parameters:
    ----------
    current_filename : str
        GCS blob name for the primary/current version of the data.
    archive_filename : str
        GCS blob name for the archived version of the data.
    project_id : str, optional
        Google Cloud project ID used for authentication. Defaults to `PROJECT`.
    url : str, optional
        URL to download the global statistics CSV. Defaults to `WDPA_GLOBAL_LEVEL_URL`.
    bucket : str, optional
        GCS bucket name where the file will be saved. Defaults to `BUCKET`.
    verbose : bool, optional
        If True, prints progress messages. Default is True.
    """
    response = requests.get(url)
    response.raise_for_status()
    data = pd.read_csv(BytesIO(response.content))

    if verbose:
        print(f"saving Global Protected Planet statistics to to gs://{bucket}/{archive_filename}")
    upload_dataframe(bucket, data, archive_filename, project_id=project_id, verbose=True)
    duplicate_blob(bucket, archive_filename, current_filename, verbose=True)


def download_protected_planet_country(
    current_filename: str,
    archive_filename: str,
    pp_api_key: str,
    bucket: str = BUCKET,
    project: str = PROJECT,
    url: str = WDPA_API_URL,
    per_page: int = 50,
    verbose: bool = True,
) -> None:
    """
    Downloads country-level statistics from the Protected Planet API,
     compiles all paginated results, and uploads the data to Google Cloud Storage
     as both a current and archived file.

    Parameters:
    ----------
    current_filename : str
        GCS blob name for the latest, actively used version of the data.
    archive_filename : str
        GCS blob name for the archived backup copy of the data.
    pp_api_key : str
        Protected Planet API token for authenticated requests.
    bucket : str, optional
        Name of the GCS bucket to upload data to. Defaults to `BUCKET`.
    project : str, optional
        Google Cloud project ID used during upload. Defaults to `PROJECT`.
    url : str, optional
        Base URL of the Protected Planet API. Defaults to `WDPA_API_URL`.
    per_page : int, optional
        Number of results to fetch per API page. Default is 50.
    verbose : bool, optional
        If True, prints progress messages. Default is True.

    """

    def fetch_data(params):
        response = requests.get(f"{url}/countries", params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("countries", [])

    page = 1
    params = {"token": pp_api_key, "per_page": per_page, "page": page}
    all_areas = []

    results = fetch_data(params)
    while results:
        if verbose:
            print(f"Fetching page {page}...")

        all_areas.extend(results)
        page += 1
        params = {"token": pp_api_key, "per_page": per_page, "page": page}
        results = fetch_data(params)

    if verbose:
        print(f"Uploading {len(all_areas)} protected areas to gs://{bucket}/{archive_filename}")

    upload_dataframe(
        bucket, pd.DataFrame(all_areas), archive_filename, project_id=project, verbose=True
    )
    duplicate_blob(bucket, archive_filename, current_filename, verbose=True)


def download_protected_planet(
    wdpa_global_level_file_name: str = WDPA_GLOBAL_LEVEL_FILE_NAME,
    archive_wdpa_global_level_file_name: str = ARCHIVE_WDPA_GLOBAL_LEVEL_FILE_NAME,
    wdpa_country_level_file_name: str = WDPA_COUNTRY_LEVEL_FILE_NAME,
    archive_wdpa_country_level_file_name: str = ARCHIVE_WDPA_COUNTRY_LEVEL_FILE_NAME,
    pp_api_key: str = PP_API_KEY,
    project_id: str = PROJECT,
    wdpa_global_url: str = WDPA_GLOBAL_LEVEL_URL,
    api_url: str = WDPA_API_URL,
    bucket: str = BUCKET,
    verbose: bool = True,
) -> None:
    """
    Downloads and processes data from Protected Planet, including:
    - Terrestrial and Marine protected areas
    - Global-level protected area statistics
    - Country-level protected area statistics

    All datasets are stored in Google Cloud Storage with both current and archived versions.

    Parameters:
    ----------
    wdpa_global_level_file_name : str
        GCS blob name for the current global statistics file.
    archive_wdpa_global_level_file_name : str
        GCS blob name for the archived global statistics file.
    wdpa_country_level_file_name : str
        GCS blob name for the current country statistics file.
    archive_wdpa_country_level_file_name : str
        GCS blob name for the archived country statistics file.
    pp_api_key : str
        Protected Planet API token for accessing country-level stats.
    project_id : str
        Google Cloud project ID used for uploads.
    wdpa_global_url : str
        URL for the global statistics CSV.
    wdpa_url : str
        URL for the WDPA ZIP file.
    api_url : str
        URL for the Protected Planet API (used for country-level stats).
    terrestrial_pa_file_name : str
        Root of GCS blob name for terrestrial protected areas.
    marine_pa_file_name : str
        Root of GCS blob name for marine protected areas.
    tolerances: list
        Tolerances to simplify geometries by for further processing.
    bucket : str
        Name of the GCS bucket to upload all files to.
    verbose : bool, optional
        If True, prints progress messages. Default is True.

    """

    # download wdpa global stats
    download_protected_planet_global(
        wdpa_global_level_file_name,
        archive_wdpa_global_level_file_name,
        project_id=project_id,
        url=wdpa_global_url,
        bucket=bucket,
    )

    # download wdpa country stats
    download_protected_planet_country(
        wdpa_country_level_file_name,
        archive_wdpa_country_level_file_name,
        pp_api_key,
        bucket=bucket,
        project=project_id,
        url=api_url,
        per_page=50,
        verbose=verbose,
    )
