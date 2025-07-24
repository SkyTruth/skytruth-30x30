import fsspec
import os
import io
from io import BytesIO
import requests
import gcsfs
import fiona
import tempfile
import zipfile
import geopandas as gpd
import numpy as np
import pandas as pd
from rasterio.mask import mask
from shapely.geometry import Polygon, MultiPolygon, GeometryCollection
from shapely.ops import unary_union

from utils.gcp import (
    download_zip_to_gcs,
    duplicate_blob,
    read_dataframe,
    read_json_from_gcs,
    save_file_bucket,
)
from utils.geo import compute_pixel_area_map_km2
from utils.processors import clean_geometries

from params import (
    RELATED_COUNTRIES_FILE_NAME,
    REGIONS_FILE_NAME,
    CHUNK_SIZE,
    MPATLAS_COUNTRY_LEVEL_FILE_NAME,
    WDPA_GLOBAL_LEVEL_FILE_NAME,
    MPATLAS_URL,
    MPATLAS_FILE_NAME,
    ARCHIVE_MPATLAS_FILE_NAME,
)


verbose = True
PP_API_KEY = os.getenv("PP_API_KEY", "")
BUCKET = os.getenv("BUCKET", "")
PROJECT = os.getenv("PROJECT", "")


def adjust_eez_sovereign(eez, parent_country):
    def eez_location(row, parent_country):
        loc = row["ISO_TER1"] if isinstance(row["ISO_TER1"], str) else row["ISO_SOV1"]
        return parent_country[loc] if loc in parent_country else loc

    eez_adj = eez[["GEONAME", "ISO_TER1", "ISO_SOV1", "AREA_KM2", "geometry"]]
    eez_adj["location"] = eez_adj.apply(eez_location, axis=1, args=(parent_country,))

    return eez_adj


def load_marine_regions(params: dict, bucket: str = BUCKET):
    zipfile_name = params["zipfile_name"]
    shp_filename = f"{params['name'].rsplit('.',1)[0]}/{params['shapefile_name']}"

    gcs_zip_path = f"gs://{bucket}/{zipfile_name}"
    shp_base_name = shp_filename.rsplit(".", 1)[0]

    with fsspec.open(gcs_zip_path, mode="rb") as f:
        zip_bytes = f.read()
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            with tempfile.NamedTemporaryFile(suffix=".zip") as tmp_zip_file:
                with zipfile.ZipFile(tmp_zip_file.name, mode="w") as new_zip:
                    for file in zf.namelist():
                        if file.startswith(shp_base_name):
                            new_zip.writestr(file, zf.read(file))

                # Build the correct path into the .shp file inside the zip
                internal_shp_path = shp_base_name + ".shp"
                zip_path = f"zip://{tmp_zip_file.name}!{internal_shp_path}"
                gdf = gpd.read_file(zip_path).pipe(clean_geometries)

    return gdf


def extract_polygons(geom):
    if isinstance(geom, (Polygon, MultiPolygon)):
        return geom
    elif isinstance(geom, GeometryCollection):
        polys = [g for g in geom.geoms if isinstance(g, (Polygon, MultiPolygon))]
        return MultiPolygon(polys) if polys else None
    else:
        return None


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


def safe_union(df, batch_size=1000, simplify_tolerance=1000):
    parts = []
    for i in range(0, len(df), batch_size):
        chunk = df.iloc[i : i + batch_size]
        if simplify_tolerance is None:
            parts.append(unary_union(chunk.geometry))
        else:
            parts.append(
                unary_union(chunk.geometry).simplify(simplify_tolerance, preserve_topology=False)
            )
    return unary_union(parts)


def get_cover_areas(src, geom, identifier, id_col, land_cover_classes):
    out_image, out_transform = mask(src, geom, crop=True, filled=False)
    valid_mask = ~out_image.mask[0]

    if np.all(out_image[0] <= 0):
        return None

    # Compute area per pixel using latitude-varying resolution
    pixel_area_map = compute_pixel_area_map_km2(
        out_transform, width=out_image.shape[2], height=out_image.shape[1]
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


def load_wdpa_global(
    bucket: str = BUCKET, wdpa_global_level_file_name: str = WDPA_GLOBAL_LEVEL_FILE_NAME
):
    wdpa_global = read_dataframe(bucket, wdpa_global_level_file_name)
    wdpa_global = wdpa_global[wdpa_global["value"] != ""]
    wdpa_global["value"] = wdpa_global["value"].astype(float)

    return wdpa_global


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


def download_mpatlas_zone(
    url: str = MPATLAS_URL,
    bucket: str = BUCKET,
    filename: str = MPATLAS_FILE_NAME,
    archive_filename: str = ARCHIVE_MPATLAS_FILE_NAME,
    verbose: bool = True,
) -> None:
    """
    Downloads the MPAtlas Zone Assessment dataset from a specified URL,
    saves it to a Google Cloud Storage bucket, and duplicates the blob.

    Parameters:
    ----------
    url : str
        URL of the MPAtlas Zone Assessment file to download.
    bucket : str
        Name of the GCS bucket where the file should be stored.
    filename : str
        GCS blob name for the primary reference copy of the file.
    archive_filename : str
        GCS blob name for the archived/original version of the file.
    verbose : bool, optional
        If True, prints progress messages. Default is True.
    """
    if verbose:
        print(f"downloading MPAtlas Zone Assessment from {url}")

    response = requests.get(url)
    response.raise_for_status()

    if verbose:
        print(f"saving MPAtlas Zone Assessment to gs://{bucket}/{archive_filename}")
    save_file_bucket(
        response.content,
        response.headers.get("Content-Type"),
        archive_filename,
        bucket,
        verbose=verbose,
    )
    duplicate_blob(bucket, archive_filename, filename, verbose=True)
