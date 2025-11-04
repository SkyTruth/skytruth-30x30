import datetime
import math

import geopandas as gpd
import pandas as pd
import rasterio
import requests
from rasterio.transform import rowcol
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon, box, mapping
from shapely.ops import unary_union
from shapely.validation import make_valid
from tqdm.auto import tqdm

from src.core.commons import get_cover_areas
from src.core.land_cover_params import LAND_COVER_CLASSES, terrestrial_tolerance
from src.core.params import (
    BUCKET,
    COUNTRY_TERRESTRIAL_HABITATS_FILE_NAME,
    GADM_FILE_NAME,
    PA_TERRESTRIAL_HABITATS_FILE_NAME,
    PROCESSED_BIOME_RASTER_PATH,
    PROJECT,
    WDPA_TERRESTRIAL_FILE_NAME,
)
from src.utils.gcp import download_file_from_gcs, read_dataframe, read_json_df, upload_dataframe
from src.utils.geo import tile_geometry


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


def generate_raster_tile_gdf(
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


def generate_terrestrial_biome_stats_pa(
    land_cover_classes: dict = LAND_COVER_CLASSES,
    pa_stats_filename: str = PA_TERRESTRIAL_HABITATS_FILE_NAME,
    raster_path: str = PROCESSED_BIOME_RASTER_PATH,
    gadm_file_name: str = GADM_FILE_NAME,
    terrestrial_pa_file_name: str = WDPA_TERRESTRIAL_FILE_NAME,
    bucket: str = BUCKET,
    project: str = PROJECT,
    country_col="ISO3",
    tile_size_pixels=8192,
    verbose: bool = True,
    tolerance: float = terrestrial_tolerance,
):
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
                g for g in geom.geoms if isinstance(g, Polygon | MultiPolygon) and not g.is_empty
            ]
        return []  # Point, LineString, etc.

    terrestrial_pa_file_name = terrestrial_pa_file_name.replace(".geojson", f"_{tolerance}.geojson")
    gadm_file_name = gadm_file_name.replace(".geojson", f"_{tolerance}.geojson")

    if verbose:
        print(f"loading GADM geometries from {gadm_file_name}")

    gadm = read_json_df(bucket, gadm_file_name, verbose=verbose)

    if verbose:
        print("loading protected areas (this may take a few minutes)")

    terrestrial_pas = read_json_df(bucket, terrestrial_pa_file_name, verbose=verbose)
    terrestrial_pas["geometry"] = terrestrial_pas.make_valid()

    if verbose:
        print(f"downloading raster from {raster_path}")
    local_raster_path = raster_path.split("/")[-1]
    download_file_from_gcs(bucket, raster_path, local_raster_path, verbose=False)

    if verbose:
        print("calculating terrestrial habitat area within PAs")
    pa_stats = []
    with rasterio.open(local_raster_path) as src:
        for country in tqdm(gadm["location"].unique()):
            st = datetime.datetime.now()

            # get country boundary and PAs in country
            country_poly = gadm[gadm["location"] == country].iloc[0]["geometry"]
            polygons_gdf = terrestrial_pas[terrestrial_pas[country_col] == country]

            # tile country
            tile_geoms = [
                make_valid(tile)
                for tile in tile_geometry(
                    country_poly, src.transform, tile_size_pixels=tile_size_pixels
                )
            ]

            # clip PAs to tiles, dissolve, and extract valid polygons of unique PA area
            clipped_geoms = clip_geoms(tile_geoms, polygons_gdf)
            clean_geoms = []
            for geom in clipped_geoms:
                clean_parts = extract_valid_polygons(geom)
                clean_geoms.extend(clean_parts)

            # get area of each land cover type inside of PAs per tile
            results = []
            for tile in clean_geoms:
                entry = get_cover_areas(
                    src, [mapping(tile)], country, "country", land_cover_classes
                )
                if entry is not None:
                    results.append(entry)

            # get country total land cover within PAs
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

    # upload PA land cover type areas (km2) per country
    upload_dataframe(
        bucket,
        pa_stats,
        pa_stats_filename,
        project_id=project,
        verbose=verbose,
    )

    return pa_stats


def process_terrestrial_habitats(
    combined_regions,
    pa_stats_filename: str = PA_TERRESTRIAL_HABITATS_FILE_NAME,
    country_stats_filename: str = COUNTRY_TERRESTRIAL_HABITATS_FILE_NAME,
    bucket: str = BUCKET,
    verbose: bool = True,
):
    def get_group_stats(df, loc, relations):
        df_group = df if loc == "GLOB" else df[df["country"].isin(relations[loc])]

        out = df_group[[c for c in df_group.columns if c != "country"]].sum().to_dict()
        out["location"] = loc

        return out

    if verbose:
        print(f"loading country habitat stats from {country_stats_filename}")
    country_stats = read_dataframe(bucket, country_stats_filename, verbose=verbose)
    country_stats = country_stats.apply(pd.to_numeric, errors="ignore")

    if verbose:
        print(f"loading country habitat stats from {pa_stats_filename}")
    pa_stats = read_dataframe(bucket, pa_stats_filename, verbose=verbose)
    pa_stats = pa_stats.apply(pd.to_numeric, errors="ignore")

    # wrap up pa stats by sovereign country
    grouped_pa_stats = pd.DataFrame(
        [get_group_stats(pa_stats, reg, combined_regions) for reg in combined_regions]
    )

    # wrap up country stats by sovereign country
    grouped_cnt_stats = pd.DataFrame(
        [get_group_stats(country_stats, reg, combined_regions) for reg in combined_regions]
    )

    # calculate percent land cover within PA of total land cover per country
    cnt = (
        pd.melt(
            grouped_cnt_stats.rename(columns={"total": "total_land_area", "country": "location"}),
            id_vars="location",  # Keep 'location' as identifier
            var_name="habitat",  # Name of the new column for cover type
            value_name="total_area",  # Name of the values column (optional)
        )
        .sort_values(["location", "habitat"])
        .reset_index(drop=True)
    )

    pa = (
        pd.melt(
            grouped_pa_stats.rename(columns={"total": "total_land_area", "country": "location"}),
            id_vars="location",  # Keep 'location' as identifier
            var_name="habitat",  # Name of the new column for cover type
            value_name="protected_area",  # Name of the values column (optional)
        )
        .sort_values(["location", "habitat"])
        .reset_index(drop=True)
    )

    pa["environment"] = "terrestrial"

    terrestrial_habitats = pd.merge(
        pa[["location", "habitat", "environment", "protected_area"]],
        cnt[["location", "habitat", "total_area"]],
        on=["location", "habitat"],
        how="right",
    )

    return terrestrial_habitats
