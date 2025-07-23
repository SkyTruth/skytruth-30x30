import fsspec
import os
import io
import tempfile
import zipfile
import geopandas as gpd
import numpy as np
from rasterio.mask import mask
from shapely.geometry import Polygon, MultiPolygon, GeometryCollection
from shapely.ops import unary_union

from utils.gcp import read_json_from_gcs, download_zip_to_gcs, duplicate_blob
from utils.geo import compute_pixel_area_map_km2
from utils.processors import clean_geometries

from params import (
    RELATED_COUNTRIES_FILE_NAME,
    REGIONS_FILE_NAME,
    CHUNK_SIZE,
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
