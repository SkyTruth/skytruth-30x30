import datetime
import pandas as pd
import geopandas as gpd
import rasterio
from shapely.geometry import box, mapping
from shapely.ops import unary_union
from shapely.strtree import STRtree
from tqdm.auto import tqdm
from pathlib import Path
from typing import Tuple, Dict, Callable
from google.cloud import storage
import threading
import concurrent.futures

from src.core.commons import (
    load_marine_regions,
    safe_union,
    download_and_duplicate_zipfile,
    get_cover_areas,
)

from src.core.land_cover_params import (
    reclass_function,
    BIOME_RASTER_PATH,
    LAND_COVER_CLASSES,
    terrestrial_tolerance,
)

from src.core.params import (
    CHUNK_SIZE,
    GADM_EEZ_UNION_FILE_NAME,
    HABITATS_URL,
    HABITATS_ZIP_FILE_NAME,
    ARCHIVE_HABITATS_FILE_NAME,
    MANGROVES_ZIPFILE_NAME,
    MANGROVES_BY_COUNTRY_FILE_NAME,
    SEAMOUNTS_URL,
    SEAMOUNTS_ZIPFILE_NAME,
    ARCHIVE_SEAMOUNTS_FILE_NAME,
    GLOBAL_MANGROVE_AREA_FILE_NAME,
    PROCESSED_BIOME_RASTER_PATH,
    GADM_ZIPFILE_NAME,
    GADM_FILE_NAME,
    COUNTRY_TERRESTRIAL_HABITATS_FILE_NAME,
    EEZ_FILE_NAME,
    EEZ_PARAMS,
    BUCKET,
    PROJECT,
)

from src.core.processors import clean_geometries

from src.utils.gcp import (
    load_zipped_shapefile_from_gcs,
    upload_dataframe,
    upload_gdf,
    save_json_to_gcs,
    upload_file_to_gcs,
    read_zipped_gpkg_from_gcs,
    read_json_df,
    download_file_from_gcs,
)

from src.utils.geo import tile_geometry, fill_polygon_holes


def process_gadm_geoms(
    gadm_file_name: str = GADM_FILE_NAME,
    gadm_zipfile_name: str = GADM_ZIPFILE_NAME,
    bucket: str = BUCKET,
    tolerances: list = [0.001, 0.0001],
    verbose: bool = True,
):
    if verbose:
        print(f"loading gadm gpkg from {gadm_zipfile_name}")
    countires, sub_countries = (
        read_zipped_gpkg_from_gcs(bucket, gadm_zipfile_name, layer=["ADM_0", "ADM_1"])[["GID_0", "geometry"]]
        .rename(columns={"GID_0": "location"})
        .pipe(clean_geometries)
    )

    for tolerance in tolerances:
        df = gadm.copy()

        if tolerance is not None:
            if verbose:
                print(f"simplifying geometries with tolerance {tolerance}")
            df["geometry"] = df["geometry"].simplify(tolerance=tolerance)

        df = df.pipe(clean_geometries)

        out_fn = gadm_file_name.replace(".geojson", f"_{tolerance}.geojson")
        if verbose:
            print(f"uploading simplified GADM countries to {out_fn}")
        upload_gdf(bucket, df, out_fn)

    return gadm


def process_eez_geoms(
    eez_file_name: str = EEZ_FILE_NAME,
    eez_params: dict = EEZ_PARAMS,
    bucket: str = BUCKET,
    tolerances: float = [0.001, 0.0001],
    verbose: bool = True,
):
    if verbose:
        print("loading eezs from")

    eez = (
        load_marine_regions(eez_params, bucket)[["ISO_TER1", "geometry"]]
        .rename(columns={"ISO_TER1": "location"})
        .pipe(clean_geometries)
    )

    for tolerance in tolerances:
        df = eez.copy()
        if tolerance is not None:
            if verbose:
                print(f"simplifying geometries with tolerance {tolerance}")
            df["geometry"] = df["geometry"].simplify(tolerance=tolerance)

        if verbose:
            print("dissolving by country")
        df = df.dissolve("location").reset_index().copy()
        df = df.pipe(clean_geometries)

        out_fn = eez_file_name.replace(".geojson", f"_{tolerance}.geojson")
        if verbose:
            print(f"uploading simplified GADM countries to {out_fn}")
        upload_gdf(bucket, df, out_fn)

    return eez


def process_eez_gadm_unions(
    gadm_eez_union_file_name: str = GADM_EEZ_UNION_FILE_NAME,
    eez_file_name: str = EEZ_FILE_NAME,
    gadm_file_name: str = GADM_FILE_NAME,
    tolerance: float = 0.0001,
    bucket: str = BUCKET,
    verbose: bool = True,
):
    eez_file_name = eez_file_name.replace(".geojson", f"_{tolerance}.geojson")
    gadm_file_name = gadm_file_name.replace(".geojson", f"_{tolerance}.geojson")
    gadm_eez_union_file_name = gadm_eez_union_file_name.replace(".geojson", f"_{tolerance}.geojson")

    eez = read_json_df(bucket, eez_file_name, verbose=verbose)
    gadm = read_json_df(bucket, gadm_file_name, verbose=verbose).to_crs(eez.crs)

    print("getting eez/gadm unions")
    eez_gadm_union = []
    for loc in tqdm(eez["location"].dropna().unique()):
        geom = fill_polygon_holes(
            unary_union(
                [
                    gadm[gadm["location"] == loc].iloc[0]["geometry"],
                    eez[eez["location"] == loc].iloc[0]["geometry"],
                ]
            )
        )
        eez_gadm_union.append({"location": loc, "geometry": geom})

    eez_gadm_union = gpd.GeoDataFrame(eez_gadm_union, geometry="geometry", crs=eez.crs)

    if verbose:
        print(f"uploading GADM/eez union geometries to {gadm_eez_union_file_name}")
    upload_gdf(bucket, eez_gadm_union, gadm_eez_union_file_name)


def download_marine_habitats(
    habitats_url: str = HABITATS_URL,
    habitats_file_name: str = HABITATS_ZIP_FILE_NAME,
    archive_habitats_file_name: str = ARCHIVE_HABITATS_FILE_NAME,
    seamounts_url: str = SEAMOUNTS_URL,
    seamounts_zipfile_name: str = SEAMOUNTS_ZIPFILE_NAME,
    archive_seamounts_file_name: str = ARCHIVE_SEAMOUNTS_FILE_NAME,
    bucket: str = BUCKET,
    chunk_size: int = CHUNK_SIZE,
    verbose: bool = True,
) -> None:
    """
    Downloads marine habitat-related datasets (habitats and seamounts) and uploads them to GCS
    as both current and archived versions.

    Parameters:
    ----------
    habitats_url : str
        URL to download the general habitat ZIP file.
    habitats_file_name : str
        GCS blob name for the current habitat dataset.
    archive_habitats_file_name : str
        GCS blob name for the archived habitat dataset.
    seamounts_url : str
        URL to download the seamounts ZIP file.
    seamounts_zipfile_name : str
        GCS blob name for the current seamounts dataset.
    archive_seamounts_file_name : str
        GCS blob name for the archived seamounts dataset.
    bucket : str
        Name of the GCS bucket where all files will be uploaded.
    chunk_size : int, optional
        Size in bytes of each chunk used during download.
    verbose : bool, optional
        If True, prints progress messages. Default is True.
    """
    # download habitats
    download_and_duplicate_zipfile(
        habitats_url,
        bucket,
        habitats_file_name,
        archive_habitats_file_name,
        chunk_size=chunk_size,
        verbose=verbose,
    )

    # download mangroves
    # TODO: Add this

    # download seamounts
    download_and_duplicate_zipfile(
        seamounts_url,
        bucket,
        seamounts_zipfile_name,
        archive_seamounts_file_name,
        chunk_size=chunk_size,
        verbose=verbose,
    )


def process_mangroves(
    mangroves_by_country_file_name: str = MANGROVES_BY_COUNTRY_FILE_NAME,
    mangroves_zipfile_name: str = MANGROVES_ZIPFILE_NAME,
    gadm_eez_union_file_name: dict = GADM_EEZ_UNION_FILE_NAME,
    global_mangrove_area_file_name: str = GLOBAL_MANGROVE_AREA_FILE_NAME,
    bucket: str = BUCKET,
    project: str = PROJECT,
    verbose: bool = True,
    tolerance=0.001,
    batch_size=3000,
):
    # Pre-process - this should be done only when a new
    # country_union_reproj or mangrove is downloaded

    tqdm.pandas()

    if verbose:
        print("loading mangroves")
    mangrove = load_zipped_shapefile_from_gcs(mangroves_zipfile_name, bucket).pipe(clean_geometries)
    mangrove["index"] = range(len(mangrove))

    if verbose:
        print("loading eezs/gadm union")

    gadm_eez_union_file_name = gadm_eez_union_file_name.replace(".geojson", f"_{tolerance}.geojson")
    gadm_eez_union = read_json_df(bucket, gadm_eez_union_file_name, verbose=verbose)

    if verbose:
        print("re-projecting mangroves for global area calculation")
    mangrove_reproj = mangrove.to_crs("EPSG:6933").pipe(clean_geometries)

    if verbose:
        print(f"saving global mangrove area to gs://{bucket}/{global_mangrove_area_file_name}")
    mangrove_reproj["area_km2"] = mangrove_reproj.geometry.area / 1e6
    global_mangrove_area = mangrove_reproj["area_km2"].sum()

    save_json_to_gcs(
        bucket,
        {"global_area_km2": global_mangrove_area},
        global_mangrove_area_file_name,
        project,
        verbose,
    )

    if verbose:
        print("generating mangrove polygons by country")
    mangroves_by_country = []
    for cnt in tqdm(list(sorted(set(gadm_eez_union["location"].dropna())))):
        country_geom = gadm_eez_union[gadm_eez_union["location"] == cnt].iloc[0].geometry

        # clip mangroves to country bounding box
        xmin, ymin, xmax, ymax = country_geom.bounds
        mangroves_clipped = mangrove[mangrove.intersects(box(xmin, ymin, xmax, ymax))]

        # Build STRtree index
        mangrove_geoms = list(mangroves_clipped.geometry)
        tree = STRtree(mangrove_geoms)

        indices = tree.query(country_geom, predicate="intersects")
        country_mangroves = mangroves_clipped.iloc[indices].copy().buffer(0)
        if len(country_mangroves) > 0:
            mangrove_geom = safe_union(
                country_mangroves, batch_size=batch_size, simplify_tolerance=tolerance
            )
            mangroves_by_country.append(
                {
                    "country": cnt,
                    "n_mangrove_polygons": len(country_mangroves),
                    "bbox": country_geom.bounds,
                    "mangrove_area_km2": country_mangroves.to_crs("EPSG:6933").area.sum() / 1e6,
                    "geometry": mangrove_geom,
                }
            )

    mangroves_by_country = gpd.GeoDataFrame(
        mangroves_by_country, geometry="geometry", crs="EPSG:4326"
    )
    upload_gdf(
        bucket, mangroves_by_country, mangroves_by_country_file_name, project, True, timeout=600
    )


def process_terrestrial_biome_raster(
    biome_raster_path: Path = BIOME_RASTER_PATH,
    processed_biome_raster_path: Path = PROCESSED_BIOME_RASTER_PATH,
    func: Callable = reclass_function,
    f_args: Tuple = (),
    f_kwargs: Dict = {},
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
        print(f"downloading {biome_raster_path} to {local_biome_raster_path}")
    client = storage.Client()
    bucket = client.bucket(bucket)
    blob = bucket.blob(biome_raster_path)
    blob.download_to_filename(local_biome_raster_path)

    fn_out = processed_biome_raster_path.split("/")[-1]

    if verbose:
        print(f"processing raster and saving to {fn_out}")
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
                    result = func(data, *f_args, **f_kwargs)

                    status_message["messages"].append("writing data")
                    with write_lock:
                        dst.write(result, window=window)

                    status_message["messages"].append("success in processing chunk")

                except Exception as e:
                    status_message["diagnostics"]["error"] = e
                finally:
                    return status_message

            # We map the process() function over the list of
            # windows.

            futures = []

            with (
                concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor,
                tqdm(total=len(windows), desc="Computing raster stats", unit="chunk") as p_bar,
            ):
                for idx, window in enumerate(windows):
                    futures.append(executor.submit(process, window))

                results = []
                for f in futures:
                    results.append(f.result())
                    p_bar.update(1)

            dst.build_overviews([2, 4, 8, 16, 32, 64], rasterio.enums.Resampling.mode)
            dst.update_tags(ns="rio_overview", resampling="average")

    if verbose:
        print(f"saving processed raster to {processed_biome_raster_path}")
    upload_file_to_gcs(bucket, fn_out, processed_biome_raster_path)

    if verbose:
        print("finished uploading")


def generate_terrestrial_biome_stats_country(
    land_cover_classes: dict = LAND_COVER_CLASSES,
    country_stats_filename: str = COUNTRY_TERRESTRIAL_HABITATS_FILE_NAME,
    raster_path: str = PROCESSED_BIOME_RASTER_PATH,
    gadm_file_name: str = GADM_FILE_NAME,
    bucket: str = BUCKET,
    project: str = PROJECT,
    tolerance: float = terrestrial_tolerance,
    verbose: bool = True,
):
    gadm_file_name = gadm_file_name.replace(".geojson", f"_{tolerance}.geojson")

    print("loading and simplifying GADM geometries")
    gadm = read_json_df(bucket, gadm_file_name, verbose=verbose)

    if verbose:
        print(f"downloading raster from {raster_path}")
    local_raster_path = raster_path.split("/")[-1]
    download_file_from_gcs(bucket, raster_path, local_raster_path, verbose=False)

    if verbose:
        print("getting country habitat stats")
    country_stats = []
    with rasterio.open(local_raster_path) as src:
        for country in tqdm(gadm["GID_0"].unique()):
            st = datetime.datetime.now()
            country_poly = gadm[gadm["GID_0"] == country].iloc[0]["geometry"]
            tile_geoms = tile_geometry(country_poly, src.transform)

            results = []
            for tile in tile_geoms:
                entry = get_cover_areas(
                    src, [mapping(tile)], country, "country", land_cover_classes
                )
                if entry is not None:
                    results.append(entry)

            results = pd.DataFrame(results)
            cs = results[[c for c in results.columns if c != "country"]].agg("sum").to_dict()
            cs["country"] = country

            country_stats.append(cs)
            fn = datetime.datetime.now()
            if verbose:
                elapsed_seconds = round((fn - st).total_seconds())
                print(
                    f"processed {len(tile_geoms)} tiles within {country}'s PAs "
                    f"in {elapsed_seconds} seconds"
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
