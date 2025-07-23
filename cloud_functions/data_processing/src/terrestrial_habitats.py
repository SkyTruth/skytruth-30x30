import os
import datetime
import pandas as pd
import geopandas as gpd
import requests
from shapely.geometry import box
from shapely.ops import unary_union
from tqdm.auto import tqdm
import math
import numpy as np
import rasterio
from shapely.geometry import mapping, Polygon, MultiPolygon, GeometryCollection
from shapely.validation import make_valid

from rasterio.mask import mask
from rasterio.transform import rowcol

from params import (
    COUNTRY_TERRESTRIAL_HABITATS_FILE_NAME,
    GADM_FILE_NAME,
    PA_TERRESTRIAL_HABITATS_FILE_NAME,
    PROCESSED_BIOME_RASTER_PATH,
    WDPA_TERRESTRIAL_FILE_NAME,
)

from utils.gcp import (
    download_file_from_gcs,
    upload_dataframe,
    read_json_df,
)

from utils.geo import compute_pixel_area_map_km2


verbose = True
PP_API_KEY = os.getenv("PP_API_KEY", "")
BUCKET = os.getenv("BUCKET", "")
PROJECT = os.getenv("PROJECT", "")

LAND_COVER_CLASSES = {
    1: "Forest",
    2: "Savanna",
    3: "Shrubland",
    4: "Grassland",
    5: "Wetlands/open water",
    6: "Rocky/mountains",
    7: "Desert",
    8: "Artificial",
    255: "Other",
}


def download_file(url, destination):
    response = requests.get(url, stream=True)
    response.raise_for_status()

    with open(destination, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)


def estimate_masked_pixel_count(src, geom):
    # Get bounding box of the geometry
    bounds = geom.bounds  # (minx, miny, maxx, maxy)

    # Convert bounds to pixel indices
    row_min, col_min = rowcol(src.transform, bounds[0], bounds[3], op=round)  # minx, maxy
    row_max, col_max = rowcol(src.transform, bounds[2], bounds[1], op=round)  # maxx, miny

    # Calculate width and height in pixels
    width = abs(col_max - col_min)
    height = abs(row_max - row_min)

    return width * height


def tile_geometry(geom, transform, tile_size_pixels=1000):
    """
    Splits the geometry’s bounding box into smaller square tiles
    and intersects them with the geometry.

    Parameters
    ----------
    geom : shapely.Geometry
        Input polygon.
    transform : Affine
        Raster affine transform.
    tile_size_pixels : int
        Number of pixels per tile edge (e.g., 1000x1000 pixels).

    Returns
    -------
    List[shapely.Geometry]
        List of clipped tile geometries.
    """
    res_x, res_y = transform.a, -transform.e
    bounds = geom.bounds
    xmin, ymin, xmax, ymax = bounds

    tiles = []
    x = xmin
    while x < xmax:
        y = ymin
        while y < ymax:
            tile = box(x, y, x + res_x * tile_size_pixels, y + res_y * tile_size_pixels)
            clipped = geom.intersection(tile)
            if not clipped.is_empty:
                tiles.append(clipped)
            y += res_y * tile_size_pixels
        x += res_x * tile_size_pixels

    return tiles


def generate_raster_tiles(
    raster_path: str, tile_width: int = 1000, tile_height: int = 1000
) -> gpd.GeoDataFrame:
    """
    Generates a GeoDataFrame of polygons representing raster tiles.

    Parameters
    ----------
    raster_path : str
        Path to the raster file.
    tile_width : int
        Width of each tile in pixels.
    tile_height : int
        Height of each tile in pixels.

    Returns
    -------
    gpd.GeoDataFrame
        GeoDataFrame of tile polygons with their spatial extent.
    """

    with rasterio.open(raster_path) as src:
        transform = src.transform
        width = src.width
        height = src.height
        crs = src.crs

    n_cols = math.ceil(width / tile_width)
    n_rows = math.ceil(height / tile_height)

    records = []
    for row in range(n_rows):
        for col in range(n_cols):
            x0 = col * tile_width
            y0 = row * tile_height

            # convert pixel coords to spatial coords
            x_left, y_top = transform * (x0, y0)
            x_right, y_bottom = transform * (
                min(x0 + tile_width, width),
                min(y0 + tile_height, height),
            )

            tile_geom = box(x_left, y_bottom, x_right, y_top)

            records.append(
                {"tile_id": row * n_cols + col, "row": row, "col": col, "geometry": tile_geom}
            )
    return gpd.GeoDataFrame(records, crs=crs)


def reclass_function(ndata: np.ndarray) -> np.ndarray:
    # Apply the value changes
    ndata = np.where(ndata < 200, 1, ndata)  # forest
    ndata = np.where((ndata >= 200) & (ndata < 300), 2, ndata)  # savanna
    ndata = np.where((ndata >= 300) & (ndata < 400), 3, ndata)  # scrub/shrub
    ndata = np.where((ndata >= 400) & (ndata < 500), 4, ndata)  # grassland
    ndata = np.where(ndata == 501, 5, ndata)  # open water - Wetlands/open water
    ndata = np.where(ndata == 505, 5, ndata)  # open water - Wetlands/open water
    ndata = np.where((ndata >= 500) & (ndata < 600), 5, ndata)  # wetlands - Wetlands/open water
    ndata = np.where(ndata == 984, 5, ndata)  # wetlands - Wetlands/open water
    ndata = np.where(ndata == 910, 5, ndata)  # wetlands - Wetlands/open water
    ndata = np.where((ndata >= 600) & (ndata < 800), 6, ndata)  # rocky/mountains
    ndata = np.where((ndata >= 800) & (ndata < 900), 7, ndata)  # desert
    ndata = np.where((ndata >= 1400) & (ndata < 1500), 8, ndata)  # ag/urban - Artificial

    # Ensure the ndata is within the 8-bit range

    return np.clip(ndata, 0, 255).astype(np.uint8)


def get_cover_areas(src, geom, identifier, id_col, land_cover_classes=LAND_COVER_CLASSES):
    out_image, out_transform = mask(src, geom, crop=True)

    if np.all(out_image[0] <= 0):
        return None

    # Compute area per pixel using latitude-varying resolution
    pixel_area_map = compute_pixel_area_map_km2(
        out_transform, width=out_image.shape[2], height=out_image.shape[1]
    )

    cover_areas = {"total": pixel_area_map.sum()}
    for value in np.unique(out_image[0]):
        if value <= 0:
            continue
        mask_value = out_image[0] == value
        area_sum = pixel_area_map[mask_value].sum()
        cover_areas[land_cover_classes.get(int(value), f"class_{value}")] = area_sum

    return {id_col: identifier, **cover_areas}


def generate_terrestrial_biome_stats_country(
    country_stats_filename: str = COUNTRY_TERRESTRIAL_HABITATS_FILE_NAME,
    raster_path: str = PROCESSED_BIOME_RASTER_PATH,
    gadm_file_name: str = GADM_FILE_NAME,
    bucket: str = BUCKET,
    project: str = PROJECT,
    tolerance: float = None,
):
    print("loading and simplifying GADM geometries")
    gadm = read_json_df(bucket, gadm_file_name, verbose=verbose)
    if tolerance is not None:
        gadm["geometry"] = gadm["geometry"].simplify(tolerance=tolerance)

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
                entry = get_cover_areas(src, [mapping(tile)], country, "country")
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


def create_terrestrial_habitats_subtable(
    combined_regions,
    pa_stats_filename: str = PA_TERRESTRIAL_HABITATS_FILE_NAME,
    country_stats_filename: str = COUNTRY_TERRESTRIAL_HABITATS_FILE_NAME,
    raster_path: str = PROCESSED_BIOME_RASTER_PATH,
    gadm_file_name: str = GADM_FILE_NAME,
    terrestrial_pa_file_name: str = WDPA_TERRESTRIAL_FILE_NAME,
    bucket: str = BUCKET,
    project: str = PROJECT,
    tolerance: float = None,
    country_col="ISO3",
    tile_size_pixels=8192,
    verbose: bool = True,
):
    def get_group_stats(df, loc, relations):
        if loc == "GLOB":
            df_group = df
        else:
            df_group = df[df["country"].isin(relations[loc])]

        out = df_group[[c for c in df_group.columns if c != "country"]].sum().to_dict()
        out["location"] = loc

        return out

    def clip_geoms(tile_geoms, polygons_gdf):
        clipped_geoms = []

        for tile in tile_geoms:
            # Find only polygons in gdf that intersect the tile
            subset = polygons_gdf[polygons_gdf.intersects(tile)]

            if not subset.empty:
                # Union the overlapping geometries
                unioned = unary_union(subset.geometry)

                # Clip the unioned geometry to the tile
                clipped = tile.intersection(unioned)

                clipped_geoms.append(clipped)

        return clipped_geoms

    def extract_valid_polygons(geom):
        """Return list of polygonal geometries from possibly mixed GeometryCollection."""
        if geom.is_empty:
            return []
        if isinstance(geom, (Polygon, MultiPolygon)):
            return [geom]
        if isinstance(geom, GeometryCollection):
            return [
                g for g in geom.geoms if isinstance(g, (Polygon, MultiPolygon)) and not g.is_empty
            ]
        return []  # Point, LineString, etc.

    if verbose:
        print(f"loading and simplifying GADM geometries from {gadm_file_name}")

    gadm = read_json_df(bucket, gadm_file_name, verbose=verbose)
    if tolerance is not None:
        gadm["geometry"] = gadm["geometry"].simplify(tolerance=tolerance)

    if verbose:
        print(f"loading PAs from {terrestrial_pa_file_name}")
    wdpa = read_json_df(bucket, terrestrial_pa_file_name, verbose=verbose)
    if tolerance is not None:
        wdpa["geometry"] = wdpa["geometry"].simplify(tolerance=tolerance)

    if verbose:
        print(f"loading country habitat stats from {country_stats_filename}")
    country_stats = read_json_df(bucket, country_stats_filename, verbose=verbose)

    if verbose:
        print(f"downloading raster from {raster_path}")
    local_raster_path = raster_path.split("/")[-1]
    download_file_from_gcs(bucket, raster_path, local_raster_path, verbose=False)

    if verbose:
        print("calculating terrestrial habitat area within PAs")
    pa_stats = []
    with rasterio.open(raster_path) as src:
        for country in tqdm(gadm["GID_0"].unique()):
            st = datetime.datetime.now()
            country_poly = gadm[gadm["GID_0"] == country].iloc[0]["geometry"]
            polygons_gdf = wdpa[wdpa[country_col] == country].copy()
            polygons_gdf["geometry"] = polygons_gdf["geometry"].make_valid()

            # tile country
            tile_geoms = [
                make_valid(tile)
                for tile in tile_geometry(
                    country_poly, src.transform, tile_size_pixels=tile_size_pixels
                )
            ]

            # clip geometries to tiles
            clipped_geoms = clip_geoms(tile_geoms, polygons_gdf)
            clean_geoms = []
            for geom in clipped_geoms:
                clean_parts = extract_valid_polygons(geom)
                clean_geoms.extend(clean_parts)

            results = []
            for tile in clean_geoms:
                entry = get_cover_areas(src, [mapping(tile)], country, "country")
                if entry is not None:
                    results.append(entry)

            results = pd.DataFrame(results)
            ps = results[[c for c in results.columns if c != "country"]].agg("sum").to_dict()
            ps["country"] = country

            pa_stats.append(ps)
            fn = datetime.datetime.now()
            if verbose:
                elapsed_seconds = round((fn - st).total_seconds())
                print(
                    f"processed {len(clipped_geoms)} tiles within {country}'s PAs "
                    f"in {elapsed_seconds} seconds"
                )

    pa_stats = pd.DataFrame(pa_stats)

    upload_dataframe(
        bucket,
        pa_stats,
        pa_stats_filename,
        project_id=project,
        verbose=verbose,
    )

    grouped_pa_stats = pd.DataFrame(
        [get_group_stats(pa_stats, reg, combined_regions) for reg in combined_regions]
    )

    grouped_cnt_stats = pd.DataFrame(
        [get_group_stats(country_stats, reg, combined_regions) for reg in combined_regions]
    )

    cols = [c for c in grouped_cnt_stats.columns if c != "location"]
    pct = 100 * grouped_pa_stats[cols] / grouped_cnt_stats[cols]
    pct["location"] = grouped_cnt_stats["location"]
    pct = pct[["location"] + cols]

    return pct
