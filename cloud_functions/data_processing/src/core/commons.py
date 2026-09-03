import io
import json
import os
import tempfile
import time
import traceback
import zipfile
from functools import cache
from io import BytesIO

import fiona
import fsspec
import gcsfs
import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from joblib import Parallel, delayed
from rasterio.mask import mask
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon
from shapely.ops import unary_union
from shapely.validation import make_valid
from skytruth_shared_datasets import Catalog
from tqdm.auto import tqdm

from src.core.params import (
    BUCKET,
    CHUNK_SIZE,
    MARINE_TOLERANCE,
    MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    MPATLAS_FILE_NAME,
    MPATLAS_GLOBAL_FILE_NAME,
    NEAR_SHORE_BUFFER_KM,
    NEAR_SHORE_IHO_FILE_NAME,
    REGIONS_FILE_NAME,
    RELATED_COUNTRIES_FILE_NAME,
    WDPA_GLOBAL_LEVEL_FILE_NAME,
    WDPA_MARINE_FILE_NAME,
)
from src.core.processors import clean_geometries
from src.utils.gcp import (
    download_zip_to_gcs,
    duplicate_blob,
    read_dataframe,
    read_json_df,
    read_json_from_gcs,
    read_parquet_from_gcs,
)
from src.utils.geo import (
    buffer_km,
    compute_pixel_area_map_km2,
)
from src.utils.logger import Logger

logger = Logger()

SLACK_ALERTS_WEBHOOK = os.environ.get("SLACK_ALERTS_WEBHOOK", "")
MEDI_MRGID = [4280, 3315, 3351, 4279, 3322, 3324, 3346, 3369, 3386, 3314, 3363]

# TODO: We currently do not buffer the Arctic Ocean or Southern Ocean because
# of complexities in buffering in polar regions and regions that wrap around.
# The current buffer exists to catch mangroves and saltmarshes that the IHO
# coastline misses, and neither occurs in the Arctic. If needed in the future
# we will have to add complexity to the buffering method
UNBUFFERED_MRGID = {1906, 1907}  # Arctic Ocean


def stitch_mediterannean(iho):
    iho = iho.copy()

    medi = iho[iho["MRGID"].isin(MEDI_MRGID)].dissolve().reset_index(drop=True)

    # Recompute the geometry-derived fields from the dissolved polygon
    bounds = medi.total_bounds  # (minx, miny, maxx, maxy) in the layer CRS (4326)
    centroid = medi.to_crs(epsg=6933).geometry.centroid.to_crs(epsg=4326).iloc[0]

    medi["NAME"] = "Mediterranean Region"
    medi["ID"] = None
    medi["MRGID"] = "MEDI"
    medi["Longitude"] = centroid.x
    medi["Latitude"] = centroid.y
    medi["min_X"], medi["min_Y"], medi["max_X"], medi["max_Y"] = bounds
    medi["area"] = medi.to_crs(epsg=6933).geometry.area.iloc[0] / 1e6

    iho["MRGID"] = iho["MRGID"].astype(str)
    iho = pd.concat((iho, medi), axis=0, ignore_index=True)

    return iho


def _subtract_neighbors(idx, geom, neighbor_geoms):
    """Subtract a buffered region's neighboring (unbuffered) regions from it."""
    return idx, geom.difference(unary_union(neighbor_geoms))


def process_buffered_iho(iho, km=NEAR_SHORE_BUFFER_KM, n_jobs=-1):
    """
    buffers IHO regions and clips them to neighboring IHO bounds
    """

    invalid = ~iho.geometry.is_valid
    if invalid.any():
        names = ", ".join(iho.loc[invalid, "NAME"].astype(str))
        logger.warning({"message": f"repairing invalid IHO geometries: {names}"})
        iho = iho.copy()
        iho["geometry"] = iho.geometry.make_valid()

    logger.info({"message": f"buffering IHO sea areas by {km} km"})

    def _buffer_km(geom):
        return buffer_km(geom, km=km, src_crs=iho.crs)

    # See UNBUFFERED_MRGID: these are passed through untouched, so they are neither
    # buffered nor clipped against their neighbours.
    buffered_rows = ~iho["MRGID"].isin(UNBUFFERED_MRGID)

    if not buffered_rows.all():
        skipped = iho.loc[~buffered_rows, "NAME"].tolist()
        logger.info({"message": f"leaving IHO sea areas unbuffered: {', '.join(skipped)}"})

    iho_buffer = iho.copy()
    iho_buffer.loc[buffered_rows, "geometry"] = iho_buffer.loc[
        buffered_rows, "geometry"
    ].progress_apply(_buffer_km)

    invalid = ~iho_buffer.geometry.is_valid
    if invalid.any():
        names = ", ".join(iho_buffer.loc[invalid, "NAME"].astype(str))
        raise ValueError(f"invalid geometries in buffered IHO areas: {names}")

    iho_sindex = iho.sindex
    geometries = iho.geometry.to_numpy()
    mrgids = iho["MRGID"].to_numpy()

    logger.info({"message": "clipping bounds to neighboring IHO sea areas"})
    jobs = []
    for idx, geom in iho_buffer.loc[buffered_rows].geometry.items():
        positions = iho_sindex.query(geom, predicate="intersects")
        positions = positions[mrgids[positions] != iho_buffer.at[idx, "MRGID"]]

        if positions.size:
            jobs.append((idx, geom, list(geometries[positions])))

    clipped = Parallel(n_jobs=n_jobs, backend="loky", return_as="generator_unordered")(
        delayed(_subtract_neighbors)(idx, geom, neighbor_geoms)
        for idx, geom, neighbor_geoms in jobs
    )

    for idx, geom in tqdm(clipped, total=len(jobs), desc="clipping"):
        iho_buffer.at[idx, "geometry"] = geom

    return iho_buffer


@cache
def _load_iho_regions_cached(buffer=False):
    """Memoized loader. The returned frame is shared by all callers"""
    if not buffer:
        logger.info({"message": "fetching iho-world-seas from SkyTruth shared-datasets"})
        ref = Catalog.load().fetch("iho-world-seas", "fgb", access="public")
        water_bodies = gpd.read_file(ref.cache_path)

    else:
        if not gcsfs.GCSFileSystem().exists(f"{BUCKET}/{NEAR_SHORE_IHO_FILE_NAME}"):
            raise FileNotFoundError(
                f"gs://{BUCKET}/{NEAR_SHORE_IHO_FILE_NAME} not found. Run METHOD "
                "process_near_shore_iho to build the near-shore IHO layer before loading it."
            )

        logger.info(
            {"message": f"loading near-shore IHO from gs://{BUCKET}/{NEAR_SHORE_IHO_FILE_NAME}"}
        )

        water_bodies = read_parquet_from_gcs(BUCKET, NEAR_SHORE_IHO_FILE_NAME)

    logger.info({"message": "stitching IHO regions to form Mediterranean"})
    water_bodies = stitch_mediterannean(water_bodies)
    water_bodies["location"] = water_bodies["MRGID"].astype(str)
    water_bodies["geometry"] = water_bodies["geometry"].make_valid()

    return water_bodies


def load_iho_regions(buffer=False):
    """Load IHO regions, or the saved near-shore layer when ``buffer`` is True."""
    return _load_iho_regions_cached(buffer=buffer).copy()


def load_marine_regions(params: dict, bucket: str = BUCKET):
    zipfile_name = params["zipfile_name"]
    shp_filename = f"{params['name'].rsplit('.', 1)[0]}/{params['shapefile_name']}"

    gcs_zip_path = f"gs://{bucket}/{zipfile_name}"
    shp_base_name = shp_filename.rsplit(".", 1)[0]

    with fsspec.open(gcs_zip_path, mode="rb") as f:
        zip_bytes = f.read()
        with (
            zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf,
            tempfile.NamedTemporaryFile(suffix=".zip") as tmp_zip_file,
        ):
            with zipfile.ZipFile(tmp_zip_file.name, mode="w") as new_zip:
                for file in zf.namelist():
                    if file.startswith(shp_base_name):
                        new_zip.writestr(file, zf.read(file))

            # Build the correct path into the .shp file inside the zip
            internal_shp_path = shp_base_name + ".shp"
            zip_path = f"zip://{tmp_zip_file.name}!{internal_shp_path}"
            gdf = gpd.read_file(zip_path).pipe(clean_geometries)

    return gdf


def load_regions(
    bucket: str = BUCKET,
    related_countries_file_name: str = RELATED_COUNTRIES_FILE_NAME,
    regions_file_name: str = REGIONS_FILE_NAME,
    verbose: bool = True,
):
    # Load related countries and regions
    related_countries = read_json_from_gcs(bucket, related_countries_file_name, verbose=verbose)
    regions = read_json_from_gcs(bucket, regions_file_name, verbose=verbose)

    combined_regions = related_countries | regions
    combined_regions["GLOB"] = []

    parent_country = {}
    for cnt in combined_regions:
        if len(cnt) == 3:
            for c in combined_regions[cnt]:
                parent_country[c] = cnt

    return combined_regions, parent_country


def download_and_duplicate_zipfile(
    url: str,
    bucket: str,
    blob_name: str,
    archive_blob_name: str,
    chunk_size: int = CHUNK_SIZE,
    verbose: bool = True,
) -> None:
    """
    Downloads a ZIP file from a URL and stores it in Google Cloud Storage,
    then creates a duplicate of the uploaded blob within the same GCS bucket.

    Parameters:
    ----------
    url : str
        Public or authenticated URL pointing to the ZIP file to download.
    bucket : str
        Name of the GCS bucket where the file will be stored.
    blob_name : str
        Name of the target blob to be created as a duplicate.
    archive_blob_name : str
        Name of the original blob that receives the downloaded ZIP content.
    chunk_size : int, optional
        Size (in bytes) of each chunk used during the download/upload process.
    verbose : bool, optional
        If True, prints progress messages. Default is True.

    """

    if verbose:
        print(f"downloading {url} to gs://{bucket}/{archive_blob_name}")
    download_zip_to_gcs(url, bucket, archive_blob_name, chunk_size=chunk_size, verbose=verbose)
    duplicate_blob(bucket, archive_blob_name, blob_name, verbose=True)


def add_tolerance_suffix(filename: str, tolerance) -> str:
    """Insert a simplification-tolerance suffix before the file extension.

    e.g. ("static/iho_sea_areas_processed.parquet", 0.0001) ->
    "static/iho_sea_areas_processed_0.0001.parquet". Format-agnostic: works for
    any extension, so the file format can change without touching call sites.
    """
    stem, ext = os.path.splitext(filename)
    return f"{stem}_{tolerance}{ext}"


def safe_union(df, batch_size=1000, simplify_tolerance=1000):
    parts = []
    for i in range(0, len(df), batch_size):
        chunk = df.iloc[i : i + batch_size]
        if simplify_tolerance is None:
            parts.append(make_valid(unary_union(chunk.geometry)))
        else:
            parts.append(
                make_valid(
                    unary_union(chunk.geometry).simplify(
                        simplify_tolerance, preserve_topology=False
                    )
                )
            )
    return unary_union(parts)


def get_cover_areas(src, geom, identifier, id_col, land_cover_classes, include_zero: bool = False):
    out_image, out_transform = mask(src, geom, crop=True, filled=False)
    valid_mask = ~out_image.mask[0]

    if not valid_mask.any():
        return None
    # Default short-circuit treats 0 as "no class" (terrestrial reclass output);
    # callers with binary 0/1 rasters (e.g., climate-resilient corals) must pass
    # include_zero=True so zero-valued pixels are counted as a real class.
    if not include_zero and np.all(out_image[0] <= 0):
        return None

    # Compute area per pixel using latitude-varying resolution. Pass the raster
    # CRS so the area map is correct for both geographic rasters (terrestrial
    # habitats) and EPSG:3857 Pseudo-Mercator rasters (climate-resilient corals).
    pixel_area_map = compute_pixel_area_map_km2(
        out_transform, width=out_image.shape[2], height=out_image.shape[1], crs=src.crs
    )

    cover_areas = {"total": pixel_area_map[valid_mask].sum()}
    for value in np.unique(out_image[0].compressed()):
        mask_value = (out_image[0].data == value) & valid_mask
        area_sum = pixel_area_map[mask_value].sum()
        cover_areas[land_cover_classes.get(int(value), f"class_{value}")] = area_sum

    return {id_col: identifier, **cover_areas}


def load_mpatlas_country(
    bucket: str = BUCKET, mpatlas_country_level_file_name: str = MPATLAS_COUNTRY_LEVEL_FILE_NAME
):
    df = read_dataframe(bucket, mpatlas_country_level_file_name).copy()

    df["wdpa_marine_km2"] = df["wdpa_marine_km2"].replace("", np.nan)
    df["wdpa_marine_km2"] = df["wdpa_marine_km2"].apply(pd.to_numeric, errors="coerce")

    return df


def load_mpatlas_global(
    bucket: str = BUCKET, mpatlas_global_file_name: str = MPATLAS_GLOBAL_FILE_NAME
):
    mpatlas_global = read_json_from_gcs(bucket, mpatlas_global_file_name)

    row = {k: v for k, v in mpatlas_global.items() if not isinstance(v, (dict, list))}
    for entry in mpatlas_global["mpaguide_status"]["total"]:
        key = entry["key"]
        row[f"mpaguide_total_{key}_km2"] = entry["km2"]
        row[f"mpaguide_total_{key}_percent"] = entry["percent"]
    return pd.DataFrame([row])


def load_wdpa_global(
    bucket: str = BUCKET, wdpa_global_level_file_name: str = WDPA_GLOBAL_LEVEL_FILE_NAME
):
    wdpa_global = read_dataframe(bucket, wdpa_global_level_file_name)
    wdpa_global = wdpa_global[wdpa_global["value"] != ""]
    wdpa_global["value"] = wdpa_global["value"].astype(float)

    return wdpa_global


def get_wdpa_global_value(wdpa_global: pd.DataFrame, stat_name: str) -> float:
    return float(wdpa_global[wdpa_global["type"] == stat_name].iloc[0]["value"])


def compute_global_area(wdpa_global: pd.DataFrame, environment: str) -> float:
    """
    Total global area in km² for an environment ("marine" or "terrestrial").

    Protected Planet only publishes the protected area and the percentage of the
    globe it covers, so the total is back-calculated from those two values.
    """
    wdpa_env = "ocean" if environment == "marine" else "land"

    protected_area = get_wdpa_global_value(wdpa_global, f"total_{wdpa_env}_area_oecms_pas")
    coverage = get_wdpa_global_value(wdpa_global, f"total_{wdpa_env}_oecms_pas_coverage_percentage")

    return protected_area / (coverage / 100) if coverage else None


def read_mpatlas_from_gcs(
    bucket: str = BUCKET, filename: str = MPATLAS_FILE_NAME
) -> gpd.GeoDataFrame:
    """
    Reads a GeoJSON file from GCS and preserves the top-level 'id' field
    as zone_id

    Parameters
    ----------
    bucket : str
        The name of the GCS bucket.
    filename : str
        Path to the GeoJSON file in the bucket.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame that includes top-level 'id' and all properties.
    """
    fs = gcsfs.GCSFileSystem()
    with fs.open(f"gs://{bucket}/{filename}", "rb") as f:
        raw_bytes = f.read()

    # Open the GeoJSON from in-memory bytes
    with fiona.open(BytesIO(raw_bytes), driver="GeoJSON") as src:
        features = list(src)

        # Extract top-level 'id' and merge with properties
        for feature in features:
            feature["properties"]["zone_id"] = feature.get("id")

        gdf = gpd.GeoDataFrame.from_features(features)
        gdf.set_crs(src.crs, inplace=True)

    return gdf


def _polygonal_parts(geom):
    """The polygonal content of an intersection result, or None if it has none.

    An intersection is whatever GEOS returns: the overlapping polygon, a line or
    point where the two geometries only touch, or a GeometryCollection of both
    when a multipart feature does each at once. Only polygonal content has area
    to contribute, and it has to survive that mixed case rather than being
    thrown out with the dangling bits.
    """
    if geom is None or geom.is_empty:
        return None

    if isinstance(geom, (Polygon, MultiPolygon)):
        return geom

    if isinstance(geom, GeometryCollection):
        parts = [
            part
            for part in geom.geoms
            if isinstance(part, (Polygon, MultiPolygon)) and not part.is_empty
        ]

        return unary_union(parts) if parts else None

    # A line or point intersection: the two geometries touch but do not overlap.
    return None


def intersect_with_iho(
    features: gpd.GeoDataFrame,
    keep_cols: list[str],
    buffer: bool = False,
    with_geometry: bool = True,
) -> gpd.GeoDataFrame | pd.DataFrame:
    """One row per (feature, IHO sea area) pair the feature intersects.

    Parameters
    ----------
    features : gpd.GeoDataFrame
        Features to assign to sea areas — protected areas, MPAtlas zones, etc.
        Must be in the IHO CRS (EPSG:4326).
    keep_cols : list[str]
        Column(s) of ``features`` to carry through onto the pairs. Everything
        else is dropped; callers either merge their own attributes back on or
        ask for them here.
    buffer : bool
        Join against the near-shore buffered sea areas rather than the
        published IHO boundaries. See ``load_iho_regions``.
    with_geometry : bool
        Also return each pair's intersection: the feature clipped to that one
        sea. A point feature has no area to clip, so it keeps its membership
        with a null geometry; an areal feature with no polygonal intersection
        merely touched the sea boundary and that pair is dropped as a clipping
        artifact. Callers measuring area filter on ``geometry.notna()``, though
        ``union_all``, ``difference`` and ``dissolve`` all ignore nulls.

    Returns
    -------
    gpd.GeoDataFrame | pd.DataFrame
        ``[*keep_cols, "location"]``, plus ``geometry`` when ``with_geometry``.
    """

    # load IHO sea areas, optionally buffered to catch near-shore features
    iho = load_iho_regions(buffer=buffer)[["location", "geometry"]].reset_index(drop=True)

    # keep relevant columns and make geometries valid
    features = features[[*keep_cols, "geometry"]].copy()
    features["geometry"] = features.geometry.make_valid()

    # match features to IHO sea areas by intersection, dropping any that don't intersect
    logger.info({"message": f"matching {len(features)} features to {len(iho)} IHO sea areas"})
    pairs = features.sjoin(iho, predicate="intersects").reset_index(drop=True)
    logger.info({"message": f"found {len(pairs)} feature / IHO sea overlaps"})

    # If clipped geometry is not needed, skip computing the intersections.
    if not with_geometry:
        return pd.DataFrame(pairs[[*keep_cols, "location"]])

    # Identify the point PAs so they are not dropped when they have no polygonal
    # intersection with the sea. Taken before clipping replaces the geometry.
    point_feature = pairs.geom_type.isin(("Point", "MultiPoint"))

    # Clip each feature to the IHO sea area it intersects, reducing each result
    # to its polygonal content.
    seas = gpd.GeoSeries(iho.geometry.loc[pairs["index_right"]].to_numpy(), crs=iho.crs)
    cut = pairs.geometry.intersection(seas, align=False).apply(_polygonal_parts)
    pairs = pairs.set_geometry(cut)

    # Keep pairs that have a polygonal intersection or are point features
    # (which have no area to intersect).
    keep = pairs.geometry.notna() | point_feature

    logger.info(
        {
            "message": (
                f"dropping {int((~keep).sum())} pair(s) touching a sea without overlapping it, "
                f"keeping {int(point_feature.sum())} point pair(s) with no geometry"
            )
        }
    )

    return pairs[keep][[*keep_cols, "location", "geometry"]].reset_index(drop=True)


def intersect_wdpa_with_iho(
    bucket: str = BUCKET,
    tolerance: float = MARINE_TOLERANCE,
    pa_file_name: str = WDPA_MARINE_FILE_NAME,
    buffer: bool = False,
    with_geometry: bool = False,
) -> pd.DataFrame:
    """One row per (PA, IHO sea) pair the PA overlaps, keyed on WDPA_PID.

    Pass ``pa_file_name`` to read the terrestrial PAs instead of the marine
    ones, and ``buffer`` to join against the near-shore seas. ``PA_DEF`` and
    ``WDPAID`` ride along so consumers can split PAs from OECMs and roll parcels
    up to their parent without re-reading the protected areas file.
    """
    pa_file = add_tolerance_suffix(pa_file_name, tolerance)
    logger.info({"message": f"loading PAs from gs://{bucket}/{pa_file}"})

    keep_cols = ["WDPA_PID", "WDPAID", "PA_DEF"]
    pas = read_json_df(bucket_name=bucket, filename=pa_file)[[*keep_cols, "geometry"]]

    return intersect_with_iho(pas, keep_cols, buffer=buffer, with_geometry=with_geometry)


def intersect_mpatlas_with_iho(
    bucket: str = BUCKET,
    mpa_file_name: str = MPATLAS_FILE_NAME,
    buffer: bool = False,
    with_geometry: bool = False,
) -> pd.DataFrame:
    """One row per (MPAtlas zone, IHO sea) pair the zone overlaps, keyed on zone_id.

    ``protection_mpaguide_level`` rides along because both consumers filter to
    the fully and highly protected zones.
    """
    logger.info({"message": f"loading MPAtlas zones from gs://{bucket}/{mpa_file_name}"})

    keep_cols = ["zone_id", "protection_mpaguide_level"]
    mpa = read_mpatlas_from_gcs(bucket, mpa_file_name)[[*keep_cols, "geometry"]]

    return intersect_with_iho(mpa, keep_cols, buffer=buffer, with_geometry=with_geometry)


def download_file_with_progress(url: str, filename: str, verbose: bool = True):
    """
    Downloads a file from a given URL and displays a progress bar.

    Args:
        url (str): The URL of the file to download.
        filename (str): The local filename to save the downloaded file as.
    """
    try:
        # Send a GET request with stream=True to handle large files efficiently
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Raise an exception for bad status codes

        # Get the total file size from the Content-Length header, default to 0 if not present
        total_size = int(response.headers.get("content-length", 0))

        # Open the local file in binary write mode and create a tqdm progress bar
        with (
            open(filename, "wb") as file,
            tqdm(
                desc=filename, total=total_size, unit="iB", unit_scale=True, unit_divisor=1024
            ) as progress_bar,
        ):
            # Iterate over the content in chunks and write to the file
            for data in response.iter_content(chunk_size=8192):
                size = file.write(data)
                progress_bar.update(size)  # Update the progress bar with the written size
        if verbose:
            print(f"Download of '{filename}' completed successfully.")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(
            {
                "message": "Download error",
                "exception": str(e),
            }
        )
        return False


def unzip_file(base_zip_path, destination_folder):
    with zipfile.ZipFile(base_zip_path, "r") as zip_ref:
        zip_ref.extractall(destination_folder)


def send_slack_alert(webhook_url, text):
    try:
        headers = {"Content-Type": "application/json"}
        payload = {"text": text}
        response = requests.post(webhook_url, headers=headers, data=json.dumps(payload))
        logger.info({"message": "ALERT sent to slack", "alert": text})
        return response.status_code, response.text
    except Exception as e:
        logger.error({"message": "Failed to send slack alert", "alert": text, "exception": e})


class RetryFailed(Exception):
    pass


def retry_and_alert(func, *args, max_retries=1, backoff=10, alert_message="ALERT", **kwargs):
    """
    Retry a function call up to max_retries times.
    Calls alert_func() if provided and all retries fail.
    Returns output of func as well as success (True if
    succeeded, False if reached max_retries)
    """

    for attempt in range(1, max_retries + 2):
        try:
            return func(*args, **kwargs)

        except Exception as e:
            # Final failure
            if attempt == max_retries + 1:
                message = (
                    f"{alert_message}: {func.__name__} failed after {max_retries + 1} attempts"
                )
                logger.error(
                    {
                        "message": message,
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                    }
                )
                raise RetryFailed(f"{message}: {e}") from e
            else:
                logger.warning(
                    {
                        "message": f"Error in {func.__name__} (attempt {attempt}/{max_retries})",
                        "error": str(e),
                    }
                )

                # Backoff before retrying
                time.sleep(backoff)
