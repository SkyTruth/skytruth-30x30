import os
import datetime
import pandas as pd
import geopandas as gpd
from shapely.geometry import box, Point, MultiPoint, Polygon, MultiPolygon
from shapely.ops import unary_union
from shapely.validation import make_valid
from tqdm.auto import tqdm
import math
import numpy as np
import rasterio
from shapely.geometry import mapping
from rasterio.transform import rowcol

from src.commons import load_marine_regions, adjust_eez_sovereign, extract_polygons
from src.params import (
    EEZ_LAND_UNION_PARAMS,
    MANGROVES_BY_COUNTRY_FILE_NAME,
    GADM_ZIPFILE_NAME,
    GLOBAL_MANGROVE_AREA_FILE_NAME,
)

from src.utils.gcp import (
    load_zipped_shapefile_from_gcs,
    read_json_from_gcs,
    read_json_df,
    read_zipped_gpkg_from_gcs,
)

from src.utils.processors import clean_geometries
from src.utils.geo import compute_pixel_area_map_km2


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


def create_seamounts_subtable(
    seamounts_zipfile_name,
    seamounts_shapefile_name,
    bucket,
    eez_params,
    parent_country,
    marine_protected_areas,
    combined_regions,
    verbose,
):
    def get_group_stats(df_eez, df_pa, loc, relations, global_seamount_area, hs_seamount_area):
        if loc == "GLOB":
            df_pa_group = df_pa[["PEAKID", "AREA2D"]].drop_duplicates()
            total_area = global_seamount_area
        else:
            df_pa_group = df_pa[df_pa["location"].isin(relations[loc])][
                ["PEAKID", "AREA2D"]
            ].drop_duplicates()
            if loc == "ABNJ":
                total_area = hs_seamount_area
            else:
                df_eez_group = df_eez[df_eez["location"].isin(relations[loc])][
                    ["PEAKID", "AREA2D"]
                ].drop_duplicates()
                total_area = df_eez_group["AREA2D"].sum()

        protected_area = min(df_pa_group["AREA2D"].sum(), total_area)

        return {
            "location": loc,
            "habitat": "seamounts",
            "environment": "marine",
            "protected_area": protected_area,
            "total_area": total_area,
            # "percent_protected": 100 * protected_area / total_area if total_area > 0 else np.nan,
        }

    if verbose:
        print("loading seamounts")

    seamounts = load_zipped_shapefile_from_gcs(
        seamounts_zipfile_name, bucket, internal_shapefile_path=seamounts_shapefile_name
    )

    if verbose:
        print("loading eezs")
    eez = load_marine_regions(eez_params, bucket)
    eez = adjust_eez_sovereign(eez, parent_country)

    if verbose:
        print("spatially joining seamounts with eezs and marine protected areas")

    global_seamount_area = seamounts["AREA2D"].sum()

    eez_joined = gpd.sjoin(
        seamounts[["PEAKID", "AREA2D", "geometry"]],
        eez[["GEONAME", "location", "geometry"]],
        how="left",
        predicate="intersects",
    )
    high_seas_seamounts = eez_joined[eez_joined["index_right"].isna()]
    eez_seamounts = eez_joined[eez_joined["index_right"].notna()]

    marine_pa_joined = gpd.sjoin(
        seamounts[["PEAKID", "AREA2D", "geometry"]],
        marine_protected_areas[["wdpa_id", "location", "geometry"]],
        how="left",
        predicate="intersects",
    )
    marine_pa_seamounts = marine_pa_joined[marine_pa_joined["index_right"].notna()]

    global_seamount_area = seamounts["AREA2D"].sum()
    hs_seamount_area = high_seas_seamounts["AREA2D"].sum()

    return pd.DataFrame(
        [
            get_group_stats(
                eez_seamounts,
                marine_pa_seamounts,
                cnt,
                combined_regions,
                global_seamount_area,
                hs_seamount_area,
            )
            for cnt in combined_regions
        ]
    )


def create_mangroves_subtable(
    mpa,
    combined_regions,
    eez_land_union_params: dict = EEZ_LAND_UNION_PARAMS,
    mangroves_by_country_file_name: str = MANGROVES_BY_COUNTRY_FILE_NAME,
    global_mangrove_area_file_name: str = GLOBAL_MANGROVE_AREA_FILE_NAME,
    bucket: str = BUCKET,
    verbose: bool = True,
):
    def get_group_stats(df, loc, relations, global_mangrove_area):
        if loc == "GLOB":
            df_group = df
            total_area = global_mangrove_area
        else:
            df_group = df[df["location"].isin(relations[loc])]

            # Ensure numeric conversion
            total_area = df_group["total_mangrove_area_km2"].sum()

        protected_area = df_group["protected_mangrove_area_km2"].sum()

        return {
            "location": loc,
            "habitat": "mangroves",
            "environment": "marine",
            "protected_area": protected_area,
            "total_area": total_area,
            # "percent_protected": 100 * protected_area / total_area if total_area else None,
        }

    # TODO: using eez/land union instead of eez, which may miss some coastal regions where
    # mangroves are. However, several regions are listed under ISO_TER1 = None, most notably,
    # Alaska, which doesn't matter for mangroves, but there are also tropical areas missing
    # including Hawaii. Need to find a way to stick them together
    if verbose:
        print("loading eez/land union")
    country_union = (
        load_marine_regions(eez_land_union_params, bucket)[["ISO_TER1", "geometry"]]
        .rename(columns={"ISO_TER1": "location"})
        .pipe(clean_geometries)
    )

    if verbose:
        print("loading pre-processed mangroves")
    mangroves_by_country = read_json_df(bucket, mangroves_by_country_file_name, verbose=True).pipe(
        clean_geometries
    )
    global_mangrove_area = read_json_from_gcs(bucket, global_mangrove_area_file_name)["global_area"]

    if verbose:
        print("Updating CRS to EPSG:6933 (equal-area for geometry ops)")
    crs = "EPSG:6933"
    country_union_reproj = country_union.to_crs(crs).pipe(clean_geometries)
    mpa_reproj = mpa.to_crs(crs).pipe(clean_geometries)

    if verbose:
        print("getting protected mangrove area by country")
    protected_mangroves = []
    for cnt in tqdm(list(sorted(set(country_union_reproj["location"].dropna())))):
        country_geom = make_valid(
            extract_polygons(
                unary_union(country_union_reproj[country_union_reproj["location"] == cnt].geometry)
            )
        )

        country_mangroves = mangroves_by_country[mangroves_by_country["country"] == cnt]
        if len(country_mangroves) > 0:
            mangrove_geom = country_mangroves.iloc[0]["geometry"]
            country_mangrove_area_km2 = country_mangroves.iloc[0]["mangrove_area_km2"]

            # Get MPA features in country and clip
            country_pas = mpa_reproj[mpa_reproj["location"] == cnt]
            country_pas = gpd.clip(country_pas, country_geom)
            country_pas = country_pas[
                ~country_pas.geometry.is_empty & country_pas.geometry.is_valid
            ]
            geom_list = [g for g in country_pas.geometry if isinstance(g, (Polygon, MultiPolygon))]

            if not geom_list:
                pa_geom = None
            else:
                pa_geom = make_valid(unary_union(geom_list))
            pa_geom = make_valid(unary_union(country_pas.geometry))

            pa_mangrove_area_km2 = mangrove_geom.intersection(pa_geom).area / 1e6

            protected_mangroves.append(
                {
                    "location": cnt,
                    "total_mangrove_area_km2": country_mangrove_area_km2,
                    "protected_mangrove_area_km2": pa_mangrove_area_km2,
                }
            )

    protected_mangroves = pd.DataFrame(protected_mangroves)
    protected_mangroves["percent_protected"] = (
        100
        * protected_mangroves["protected_mangrove_area_km2"]
        / protected_mangroves["total_mangrove_area_km2"]
    )

    mangrove_habitat = pd.DataFrame(
        [
            stat
            for loc in combined_regions
            if (
                stat := get_group_stats(
                    protected_mangroves, loc, combined_regions, global_mangrove_area
                )
            )
            is not None
        ]
    )

    return mangrove_habitat[mangrove_habitat["total_area"] > 0]


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
    tile_width: int = 1000,
    tile_height: int = 1000,
):
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


def create_terrestrial_subtable(
    wdpa,
    processed_biome_raster_path="../data_processing_tests/processed_biome_raster.tif",
    verbose: bool = True,
    land_cover_classes: dict = LAND_COVER_CLASSES,
):
    def per_country(country, wdpa_terr, processed_biome_raster_path, land_cover_classes):
        gdf = wdpa_terr[wdpa_terr["PARENT_ISO3"] == country].copy()
        res = compute_land_cover_area_km2(processed_biome_raster_path, gdf, land_cover_classes)
        res = pd.DataFrame(res).drop(columns="WDPAID").sum().to_dict()
        res["country"] = country
        return res

    # TODO: 1. update biome path, 2. Add step that generated processed_biome_raster
    # 3. convert output to correct format (one row per land cover class, group by region)
    # 4. get country habitat area, 5. Dissolve overlapping PAs,
    # 6. Some of the PARENT_ISO3 are multiple separated by semicolon - count for both?
    # 7. Also related to PARENT_ISO3 - should we use ISO3 instead? Is it right that the
    # PAs with ISO3 of ATA have PARENT_ISO3 of AUS?

    if verbose:
        print("clipping and validifying terrestrial protected areas")
    wdpa_terr = wdpa[wdpa["MARINE"].isin(["0", "1"])].copy()
    wdpa_terr = wdpa_terr[
        ~wdpa_terr.geometry.apply(lambda geom: isinstance(geom, (Point, MultiPoint)))
    ]
    wdpa_terr["geometry"] = wdpa_terr["geometry"].make_valid()

    if verbose:
        print("creating terrestrial habitats subtable")

    terrestrial_habitats_subtable = []
    start_time = datetime.datetime.now()
    for cnt in tqdm(list(sorted(set(wdpa_terr["PARENT_ISO3"])))):
        start = datetime.datetime.now()
        terrestrial_habitats_subtable.append(
            per_country(cnt, wdpa_terr, processed_biome_raster_path, land_cover_classes)
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
