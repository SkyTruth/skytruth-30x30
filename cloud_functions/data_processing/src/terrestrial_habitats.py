import os
import datetime
import pandas as pd
import geopandas as gpd
import requests
from shapely.geometry import box, Point, MultiPoint
from shapely.ops import unary_union
from tqdm.auto import tqdm
import math
import numpy as np
import rasterio
from shapely.geometry import mapping, Polygon, MultiPolygon, GeometryCollection
from shapely.validation import make_valid

from rasterio.mask import mask
from rasterio.transform import rowcol

from commons import load_regions

from params import (
    COUNTRY_HABITATS_SUBTABLE_FILENAME,
    GADM_ZIPFILE_NAME,
    PROCESSED_BIOME_RASTER_PATH,
    WDPA_FILE_NAME,
)

from utils.gcp import (
    read_zipped_gpkg_from_gcs,
    upload_dataframe,
    load_gdb_layer_from_gcs,
)

from utils.geo import compute_pixel_area_map_km2


verbose = True
PP_API_KEY = os.getenv("PP_API_KEY", "")
BUCKET = os.getenv("BUCKET", "")
PROJECT = os.getenv("PROJECT", "")

GLOBAL_MARINE_AREA_KM2 = 361000000
GLOBAL_TERRESTRIAL_AREA_KM2 = 134954835


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


def compute_land_cover_area_km2(
    raster_path, polygons_gdf, land_cover_classes, id_col="WDPAID", max_pixels=5e7
):
    """
    Computes land cover area (in km²) by class for each polygon.

    Parameters
    ----------
    raster_path : str
        Path to the reprojected raster (in equal-area CRS, e.g., EPSG:6933).
    polygons_gdf : GeoDataFrame
        Polygons (must be reprojected to match raster CRS).
    id_col : str
        Column name in polygons_gdf to use as identifier.

    Returns
    -------
    list of dicts
        Each dict contains polygon ID and area per land cover class in km².
    """

    def get_cover_areas(src, geom, identifier, id_col):
        out_image, out_transform = rasterio.mask(src, geom, crop=True)

        if np.all(out_image[0] <= 0):
            return None

        # Compute area per pixel using latitude-varying resolution
        pixel_area_map = compute_pixel_area_map_km2(
            out_transform, width=out_image.shape[2], height=out_image.shape[1]
        )

        cover_areas = {}
        for value in np.unique(out_image[0]):
            if value <= 0:
                continue
            mask_value = out_image[0] == value
            area_sum = pixel_area_map[mask_value].sum()
            cover_areas[land_cover_classes.get(int(value), f"class_{value}")] = area_sum

        return {id_col: identifier, **cover_areas}

    results = []

    with rasterio.open(raster_path) as src:
        for _, row in polygons_gdf.iterrows():
            try:
                estimated_pixels = estimate_masked_pixel_count(src, row.geometry)
                if estimated_pixels < max_pixels:
                    tile_geoms = [row.geometry]
                else:
                    print(f"Tiling WDPAID {row[id_col]} (~{int(estimated_pixels):,} pixels)")
                    tile_geoms = tile_geometry(row.geometry, src.transform)
                    print(f"generated {len(tile_geoms)} tiles")

                for tile in tile_geoms:
                    entry = get_cover_areas(src, [mapping(tile)], row[id_col], id_col)
                    if entry is not None:
                        results.append(entry)

            except Exception as e:
                print(f"Error with polygon {row[id_col]}: {e}")

    return results


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


def preprocess_terrestrial_habitats_by_country(
    bucket: str = BUCKET,
    gadm_zipfile_name: str = GADM_ZIPFILE_NAME,
    land_cover_classes: dict = LAND_COVER_CLASSES,
    processed_biome_raster_path="../data_processing_tests/processed_biome_raster.tif",
    country_habitats_subtable_filename: str = COUNTRY_HABITATS_SUBTABLE_FILENAME,
    tile_width: int = 1000,
    tile_height: int = 1000,
    project: str = PROJECT,
):
    """
    Processes terrestrial habitat area summaries for each country based on a
    raster of biome classifications.

    This function reads administrative boundaries from a zipped GeoPackage (GADM),
    generates a grid of tiles over a preprocessed biome classification raster,
    intersects those tiles with country geometries, computes the area of each
    land cover class per country, and uploads a summarized table to Google Cloud Storage.

    Parameters
    ----------
    bucket : str
        The GCS bucket name to read from and upload to.
    gadm_zipfile_name : str
        The filename of the zipped GADM GeoPackage in the bucket.
    land_cover_classes : dict
        A dictionary mapping class IDs to descriptive names for land cover.
    processed_biome_raster_path : str
        Local path to the processed biome raster (GeoTIFF format).
    country_habitats_subtable_filename : str
        The name to use when uploading the final CSV summary table.
    tile_width : int
        Width (in pixels) of each raster tile for spatial partitioning.
    tile_height : int
        Height (in pixels) of each raster tile for spatial partitioning.
    project : str
        GCP project ID for the upload operation.

    Returns
    -------
    None
        The function uploads a DataFrame as a CSV to the specified GCS bucket.
        No object is returned.
    """

    def per_country(
        country,
        gadm,
        boundary_polys,
        processed_biome_raster_path,
        land_cover_classes,
        id_col="tile_id",
        country_col="GID_0",
    ):
        country_pas = gadm[gadm[country_col] == cnt][["GID_0", "geometry"]]

        overlap = gpd.sjoin(boundary_polys, country_pas, how="inner", predicate="intersects")
        overlap = overlap.rename(columns={"geometry": "tile_geom"})
        overlap["country_geom"] = country_pas.loc[overlap["index_right"], "geometry"].values
        overlap["country_geom"] = overlap.apply(
            lambda row: row["country_geom"].intersection(row["tile_geom"]), axis=1
        )
        grouped = (
            overlap.groupby(["tile_id", "row", "col"])
            .country_geom.apply(unary_union)
            .reset_index()
            .rename(columns={"country_geom": "geometry"})
        )
        country_geom_dissolved = gpd.GeoDataFrame(grouped, geometry="geometry", crs=country_pas.crs)
        res = compute_land_cover_area_km2(
            processed_biome_raster_path,
            country_geom_dissolved,
            land_cover_classes,
            id_col=id_col,
            max_pixels=5e7,
        )
        res = pd.DataFrame(res).drop(columns=id_col).sum().to_dict()
        res["country"] = country
        return res

    if verbose:
        print("loading gadm")
    gadm = read_zipped_gpkg_from_gcs(bucket, gadm_zipfile_name)

    if verbose:
        print("creating boundary polygons")
    boundary_polys = generate_raster_tiles(
        processed_biome_raster_path, tile_width=tile_width, tile_height=tile_height
    )

    start_time = datetime.datetime.now()
    country_habitats_subtable = []
    for cnt in tqdm(list(sorted(set(gadm["GID_0"])))):
        start = datetime.datetime.now()
        country_habitats_subtable.append(
            per_country(cnt, gadm, boundary_polys, processed_biome_raster_path, land_cover_classes)
        )
        end = datetime.datetime.now()
        if verbose:
            print(f"processed {cnt} in {(end - start).total_seconds():0.1f} seconds")

    end_time = datetime.datetime.now()
    if verbose:
        print(
            f"processed all countries in "
            f"{(end_time - start_time).total_seconds() / 60:0.2f} minutes"
        )

    upload_dataframe(
        bucket,
        pd.DataFrame(country_habitats_subtable),
        country_habitats_subtable_filename,
        project_id=project,
        verbose=verbose,
    )


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


def create_terrestrial_subtable(
    wdpa,
    processed_biome_raster_path=PROCESSED_BIOME_RASTER_PATH,
    land_cover_classes: dict = LAND_COVER_CLASSES,
    verbose: bool = True,
):
    def per_country(country, wdpa_terr, raster_path, land_cover_classes):
        gdf = wdpa_terr[wdpa_terr["PARENT_ISO3"] == country].copy()
        res = compute_land_cover_area_km2(raster_path, gdf, land_cover_classes)
        res = pd.DataFrame(res).drop(columns="WDPAID").sum().to_dict()
        res["country"] = country
        return res

    # TODO:
    # 1. update biome path (done!)
    # 2. Add step that generated processed_biome_raster (done!)
    # 3. convert output to correct format (one row per land cover class, group by region)
    # 4. get country habitat area
    # 5. Dissolve overlapping PAs
    # 6. Some of the PARENT_ISO3 are multiple separated by semicolon - count for both?
    # 7. Also related to PARENT_ISO3 - should we use ISO3 instead? Is it right that the
    #         PAs with ISO3 of ATA have PARENT_ISO3 of AUS? (I think this is handled with
    #         the ISO* format but we should switch to ISO3 and wrap like the other stats)

    if verbose:
        print("clipping and validifying terrestrial protected areas")
    wdpa_terr = wdpa[wdpa["MARINE"].isin(["0", "1"])].copy()
    wdpa_terr = wdpa_terr[
        ~wdpa_terr.geometry.apply(lambda geom: isinstance(geom, (Point, MultiPoint)))
    ]
    wdpa_terr["geometry"] = wdpa_terr["geometry"].make_valid()

    raster_path = "land_cover_raster.tif"
    if verbose:
        print(f"downloading land cover raster to {raster_path}")

    download_file(processed_biome_raster_path, raster_path)

    if verbose:
        print("creating terrestrial habitats subtable")

    terrestrial_habitats_subtable = []
    start_time = datetime.datetime.now()
    for cnt in tqdm(list(sorted(set(wdpa_terr["PARENT_ISO3"])))):
        start = datetime.datetime.now()
        terrestrial_habitats_subtable.append(
            per_country(cnt, wdpa_terr, raster_path, land_cover_classes)
        )
        end = datetime.datetime.now()
        if verbose:
            print(f"processed {cnt} in {(end - start).total_seconds():0.1f} seconds")

    end_time = datetime.datetime.now()
    if verbose:
        print(
            f"processed all countries in "
            f"{(end_time - start_time).total_seconds() / 60:0.2f} minutes"
        )

    return terrestrial_habitats_subtable


def get_cover_areas(src, geom, identifier, id_col, land_cover_classes=LAND_COVER_CLASSES):
    out_image, out_transform = mask(src, geom, crop=True)

    if np.all(out_image[0] <= 0):
        return None

    # Compute area per pixel using latitude-varying resolution
    pixel_area_map = compute_pixel_area_map_km2(
        out_transform, width=out_image.shape[2], height=out_image.shape[1]
    )

    cover_areas = {}
    for value in np.unique(out_image[0]):
        if value <= 0:
            continue
        mask_value = out_image[0] == value
        area_sum = pixel_area_map[mask_value].sum()
        cover_areas[land_cover_classes.get(int(value), f"class_{value}")] = area_sum

    return {id_col: identifier, **cover_areas}


def generate_terrestrial_biome_stats_country(
    raster_path: str = PROCESSED_BIOME_RASTER_PATH,
    gadm_zipfile_name: str = GADM_ZIPFILE_NAME,
    bucket: str = BUCKET,
    tolerance: float = 0.001,
):
    def get_group_stats(df, loc, relations):
        if loc == "GLOB":
            df_group = df
        else:
            df_group = df[df["country"].isin(relations[loc])]

        out = df_group[[c for c in df_group.columns if c != "country"]].sum().to_dict()
        out["location"] = loc

        return out

    combined_regions, _ = load_regions()

    print("loading and simplifying GADM geometries")
    gadm = read_zipped_gpkg_from_gcs(bucket, gadm_zipfile_name)
    gadm["geometry"] = gadm["geometry"].simplify(tolerance=tolerance)

    country_stats = []
    with rasterio.open(raster_path) as src:
        for country in tqdm(gadm["GID_0"].unique()):
            country_poly = gadm[gadm["GID_0"] == country].iloc[0]["geometry"]
            tile_geoms = tile_geometry(country_poly, src.transform)
            print(f"generated {len(tile_geoms)} tiles within {country}")

            results = []
            for tile in tile_geoms:
                entry = get_cover_areas(src, [mapping(tile)], country, "country")
                if entry is not None:
                    results.append(entry)

            results = pd.DataFrame(results)
            cs = results[[c for c in results.columns if c != "country"]].agg("sum").to_dict()
            cs["country"] = country

            country_stats.append(cs)

    country_stats = pd.DataFrame(country_stats)

    grouped_cnt_stats = pd.DataFrame(
        [get_group_stats(country_stats, reg, combined_regions) for reg in combined_regions]
    )

    return grouped_cnt_stats


def generate_terrestrial_biome_stats_pa(
    combined_regions,
    raster_path: str = PROCESSED_BIOME_RASTER_PATH,
    gadm_zipfile_name: str = GADM_ZIPFILE_NAME,
    wdpa_file_name: str = WDPA_FILE_NAME,
    bucket: str = BUCKET,
    tolerance: float = 0.001,
    country_col="ISO3",
    tile_size_pixels=8192,
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

    print("loading and simplifying GADM geometries")
    gadm = read_zipped_gpkg_from_gcs(bucket, gadm_zipfile_name)
    gadm["geometry"] = gadm["geometry"].simplify(tolerance=tolerance)

    print("loading PAs")
    wdpa = load_gdb_layer_from_gcs(wdpa_file_name, bucket)
    wdpa = wdpa[wdpa["MARINE"].isin(["0", "1"])]
    wdpa = wdpa[~wdpa.geometry.apply(lambda geom: isinstance(geom, (Point, MultiPoint)))]
    wdpa["geometry"] = wdpa["geometry"].make_valid()

    pa_stats = []
    with rasterio.open(raster_path) as src:
        for country in tqdm(gadm["GID_0"].unique()):
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
            print(f"generated {len(clipped_geoms)} tiles within {country}'s PAs")

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

    pa_stats = pd.DataFrame(pa_stats)

    grouped_pa_stats = pd.DataFrame(
        [get_group_stats(pa_stats, reg, combined_regions) for reg in combined_regions]
    )

    return grouped_pa_stats
