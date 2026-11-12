import struct

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import shapely
from joblib import Parallel, delayed
from rasterio.features import rasterize, shapes
from rasterio.windows import Window, from_bounds
from rasterio.windows import bounds as window_bounds
from rasterio.windows import transform as window_transform
from shapely import MultiPolygon
from shapely.geometry import box, shape
from shapely.validation import make_valid
from tqdm.auto import tqdm

from src.core.commons import add_tolerance_suffix
from src.core.params import (
    ARCHIVE_CONSERVATION_BUILDER_HABITAT_DATA_PATTERN,
    ARCHIVE_CONSERVATION_BUILDER_HABITAT_TILES_DIR_PATTERN,
    BUCKET,
    CONSERVATION_BUILDER_HABITAT_DATA_PATTERN,
    CONSERVATION_BUILDER_HABITAT_TILES_DIR_PATTERN,
    TOLERANCE,
)
from src.methods.subtract_geometries.io import load_pa_by_location, upload_with_archive
from src.utils.gcp import (
    delete_stale_blobs,
    download_file_from_gcs,
    read_geo_df,  # Reads a .parquet, .json or .geojson file from GCS and returns a GeoDataFrame
    read_parquet_from_gcs,  # Reads a .parquet file from GCS and returns a GeoDataFrame
)
from src.utils.geo import robust_unary_union, tile_geometry
from src.utils.logger import Logger

logger = Logger()


def process_poly_raster_habitat(
    src, raster_crs, tile_geom, pas, empty, location, class_map, connectivity=4
):
    window = from_bounds(*tile_geom.bounds, transform=src.transform)
    window = window.round_offsets().round_lengths().crop(src.height, src.width)
    habitat = src.read(1, window=window, masked=True)
    transform = src.window_transform(window)

    if habitat.size == 0:
        return empty

    # clip raster to the boundary on the grid.
    unprotected = ~np.ma.getmaskarray(habitat) & rasterize(
        [tile_geom],
        out_shape=habitat.shape,
        transform=transform,
        all_touched=False,
        dtype="uint8",
    ).astype(bool)

    if not pas.empty:
        unprotected &= ~rasterize(
            pas.to_crs(raster_crs).geometry.apply(make_valid).values,
            out_shape=habitat.shape,
            transform=transform,
            all_touched=False,
            dtype="uint8",
        ).astype(bool)

    rows = []
    for value, habitat_name in class_map.items():
        class_mask = unprotected & (habitat.data == value)
        if not class_mask.any():
            continue
        parts = [
            shape(geom)
            for geom, _ in shapes(
                class_mask.astype("uint8"),
                mask=class_mask,
                transform=transform,
                connectivity=connectivity,
            )
        ]
        rows.append(
            {"location": location, "habitat": habitat_name, "geometry": MultiPolygon(parts)}
        )

    if not rows:
        return empty

    return gpd.GeoDataFrame(rows, geometry="geometry", crs=raster_crs).to_crs("EPSG:4326")


def process_country_raster_habitat(
    country_area: gpd.GeoDataFrame,
    country_pa: gpd.GeoDataFrame,
    raster_path: str,
    class_map: dict,
    connectivity: int = 4,
    tile_size_pixels: int = 8192,
):
    """
    Returns the unprotected habitat within a country, polygonized from a raster.

    The raster counterpart of ``process_country_habitat``. The country boundary and
    its protected areas are burned onto the raster's own grid and removed there
    rather than differenced as vectors, so the unprotected extent covers the same
    pixels the published habitat stats are computed over, and the union and
    difference that dominate the vector path are never run.

    The country is split into tiles first and each is read on its own, since a
    country whose territories span many longitudes has a bounding box covering most
    of the raster. Each tile yields its own rows rather than being stitched back
    together: within a tile the polygons ``shapes`` returns never share an edge, so
    they assemble into a MultiPolygon directly, but polygons from adjoining tiles do,
    and a MultiPolygon holding those is invalid. ``update_cb`` subdivides on the way
    into PostGIS anyway, so nothing downstream wants one geometry per country.

    Parameters
    ----------
    country_area : gpd.GeoDataFrame
        Single-country GeoDataFrame in EPSG:4326 carrying a "location" column.
    country_pa : gpd.GeoDataFrame
        The country's protected areas, in EPSG:4326.
    raster_path : str
        Local path to the habitat raster.
    class_map : dict
        Maps raster pixel value to habitat name.
    connectivity : int
        Passed to ``shapes``. 4 keeps regions meeting at a corner separate; 8
        merges them into a self-touching ring PostGIS rejects as invalid.
    tile_size_pixels : int
        Tile edge length in raster pixels, bounding how much is read at once.

    Returns
    -------
        GeoDataFrame in EPSG:4326 with one row per class per tile holding that
        class, columns ["location", "habitat", "geometry"], or an empty
        GeoDataFrame with those columns where the country holds none of them.
    """
    empty = gpd.GeoDataFrame({"location": [], "habitat": []}, geometry=[], crs="EPSG:4326")
    location = country_area["location"].iloc[0]

    with rasterio.open(raster_path) as src:
        raster_crs = src.crs
        country_geom = robust_unary_union(
            country_area.to_crs(raster_crs).geometry.apply(make_valid).values
        )
        tile_geoms = tile_geometry(country_geom, src.transform, tile_size_pixels=tile_size_pixels)

        rows = []
        for tile_geom in tile_geoms:
            tile_rows = process_poly_raster_habitat(
                src, raster_crs, tile_geom, country_pa, empty, location, class_map, connectivity
            )
            if not tile_rows.empty:
                rows.append(tile_rows)

    if not rows:
        return empty

    return pd.concat(rows).reset_index(drop=True)


def generate_raster_habitat_minus_pa(
    habitat_file_name: str,
    habitats: tuple,
    total_area_file: str,
    pa_file: str,
    tolerance=TOLERANCE,
    bucket: str = BUCKET,
    n_jobs: int = -1,
    verbose: bool = True,
):
    """
    Subtracts protected areas from the raster habitat lying inside each country's
    boundaries; saves one Parquet per habitat class to GCS.

    The raster counterpart of ``generate_habitat_minus_pa``: same inputs and the same
    per-country fan-out, but the habitat comes from a raster and the protected areas are
    removed on its grid rather than differenced as vectors. Each class gets its own file
    because ``update_cb`` loads only a location and a geometry into each table.

    Parameters
    ----------
    habitat_file_name : str
        GCS path of the habitat raster.
    habitats : tuple
        Every class the raster encodes, in pixel value order: the first name is the
        class stored as 0, the second as 1, and so on. Each is written to its own file.
    total_area_file : str
        Filename of the locations parquet the habitat is attributed to.
    pa_file : str
        Filename of the protected areas parquet to subtract, carrying an ISO3 column.
    tolerance : float
        Tolerance value used in simplification.
    bucket : str
        GCS bucket name.
    n_jobs : int
        Number of workers in the per-country fan-out.
    verbose : bool, optional
        Whether to print verbose logs, by default True.

    Returns
    -------
        One GeoDataFrame per name in ``habitats`` saved to GCS as a Parquet, each with
        one row per country holding that class.
    """
    class_map = dict(enumerate(habitats))

    local_raster = habitat_file_name.split("/")[-1]
    download_file_from_gcs(bucket, habitat_file_name, local_raster, verbose=verbose)

    # Total areas: the land/EEZ union plus the buffered IHO sea areas
    total_area = read_parquet_from_gcs(
        bucket_name=bucket,
        filename=add_tolerance_suffix(total_area_file, tolerance),
        verbose=verbose,
    )
    total_area = total_area[["location", "geometry"]]

    # Get list of unique country codes
    countries = total_area["location"].unique().tolist()

    # Protected areas: the marine and terrestrial protected areas intersecting eezs and
    # buffered IHO seas
    pa = load_pa_by_location(
        read_parquet_from_gcs, pa_file, tolerance, bucket=bucket, verbose=verbose
    )

    # Subtract geometries
    if verbose:
        logger.info({"message": "Subtracting protected areas from habitat areas..."})
    results = tqdm(
        Parallel(n_jobs=n_jobs, backend="threading", return_as="generator_unordered")(
            delayed(process_country_raster_habitat)(
                total_area[total_area["location"] == country].reset_index(drop=True),
                pa[pa["ISO3"] == country].reset_index(drop=True),
                local_raster,
                class_map,
            )
            for country in countries
        ),
        total=len(countries),
    )

    # Countries holding none of the habitat come back empty; concat needs them dropped
    populated = [result for result in results if not result.empty]
    habitat_minus_pa = (
        pd.concat(populated).reset_index(drop=True)
        if populated
        else gpd.GeoDataFrame({"location": [], "habitat": []}, geometry=[], crs="EPSG:4326")
    )

    # One file per class: update_cb loads only a location and a geometry per table, so
    # the classes cannot share one.
    for habitat in class_map.values():
        rows = habitat_minus_pa[habitat_minus_pa["habitat"] == habitat]
        if verbose:
            logger.info({"message": f"{habitat} file has {len(rows)} rows."})

        upload_with_archive(
            rows,
            CONSERVATION_BUILDER_HABITAT_DATA_PATTERN.format(habitat=habitat),
            ARCHIVE_CONSERVATION_BUILDER_HABITAT_DATA_PATTERN.format(habitat=habitat),
            bucket=bucket,
        )


# PostGIS raster WKB band flags: 8-bit unsigned pixels, with a nodata value
PT_8BUI = 4
BAND_HAS_NODATA = 0x40


def raster_tile_wkb(pixels, transform, srid, nodata):
    """
    Encodes one band of 8-bit pixels as PostGIS raster WKB.

    PostGIS reads this format directly (``'\\x...'::raster`` or ``ST_RastFromWKB``),
    so loading the tiles needs no GDAL driver enabled in the database.

    Parameters
    ----------
    pixels : np.ndarray
        2D uint8 array of the tile's pixels, row by row from the top.
    transform : Affine
        Affine transform of the tile's top-left pixel.
    srid : int
        EPSG code of the tile's CRS.
    nodata : int
        Pixel value standing for no data.

    Returns
    -------
        The tile as little-endian PostGIS raster WKB bytes.
    """
    height, width = pixels.shape
    header = struct.pack(
        "<BHHddddddiHH",
        1,  # little-endian
        0,  # WKB version
        1,  # number of bands
        transform.a,  # scale x
        transform.e,  # scale y
        transform.c,  # upper-left x
        transform.f,  # upper-left y
        transform.b,  # skew x
        transform.d,  # skew y
        srid,
        width,
        height,
    )
    band = struct.pack("<BB", PT_8BUI | BAND_HAS_NODATA, int(nodata))
    return header + band + np.ascontiguousarray(pixels, dtype="uint8").tobytes()


def process_location_raster_tiles(
    location_area: gpd.GeoDataFrame,
    location_pa: gpd.GeoDataFrame,
    raster_path: str,
    tile_size_pixels: int = 256,
    chunk_size_pixels: int = 8192,
):
    """
    Returns a location's unprotected habitat as PostGIS raster tiles.

    The raster counterpart of ``process_country_raster_habitat`` that skips
    polygonizing: pixels outside the location or inside its protected areas are set
    to nodata on the raster's own grid, and what remains is cut into tiles for a
    PostGIS raster table. The raster is read one chunk at a time and tiles holding
    only nodata are dropped, so oceans and fully protected areas cost no rows.

    Parameters
    ----------
    location_area : gpd.GeoDataFrame
        Single-location GeoDataFrame carrying a "location" column.
    location_pa : gpd.GeoDataFrame
        The location's protected areas.
    raster_path : str
        Path to a single-band uint8 habitat raster with a nodata value.
    tile_size_pixels : int
        Edge length in pixels of each tile written.
    chunk_size_pixels : int
        Edge length in pixels of each read from the raster. A multiple of
        ``tile_size_pixels``, so tiles never straddle two reads.

    Returns
    -------
        GeoDataFrame in the raster's CRS with one row per tile holding any
        unprotected habitat, columns ["location", "rast", "geometry"]: the tile as
        PostGIS raster WKB, and its footprint.
    """
    location = location_area["location"].iloc[0]
    locations, rasts, footprints = [], [], []

    with rasterio.open(raster_path) as src:
        location_geom = robust_unary_union(
            location_area.to_crs(src.crs).geometry.apply(make_valid).values
        )
        pas = location_pa.to_crs(src.crs).geometry.apply(make_valid)
        srid = src.crs.to_epsg()
        nodata = src.nodata

        if location_geom.intersects(box(*src.bounds)):
            shapely.prepare(location_geom)
            full = (
                from_bounds(*location_geom.bounds, transform=src.transform)
                .round_offsets()
                .round_lengths()
                .crop(src.height, src.width)
            )
            row_end = int(full.row_off + full.height)
            col_end = int(full.col_off + full.width)

            for chunk_row in range(int(full.row_off), row_end, chunk_size_pixels):
                for chunk_col in range(int(full.col_off), col_end, chunk_size_pixels):
                    chunk = Window(
                        chunk_col,
                        chunk_row,
                        min(chunk_size_pixels, col_end - chunk_col),
                        min(chunk_size_pixels, row_end - chunk_row),
                    )
                    chunk_box = box(*window_bounds(chunk, src.transform))
                    if not location_geom.intersects(chunk_box):
                        continue

                    chunk_transform = src.window_transform(chunk)
                    pixels = src.read(1, window=chunk)

                    unprotected = rasterize(
                        [location_geom],
                        out_shape=pixels.shape,
                        transform=chunk_transform,
                        all_touched=False,
                        dtype="uint8",
                    ).astype(bool)
                    chunk_pas = pas.values[pas.sindex.query(chunk_box)]
                    if len(chunk_pas):
                        unprotected &= ~rasterize(
                            chunk_pas,
                            out_shape=pixels.shape,
                            transform=chunk_transform,
                            all_touched=False,
                            dtype="uint8",
                        ).astype(bool)
                    pixels[~unprotected] = nodata

                    for row in range(0, pixels.shape[0], tile_size_pixels):
                        for col in range(0, pixels.shape[1], tile_size_pixels):
                            tile = pixels[
                                row : row + tile_size_pixels, col : col + tile_size_pixels
                            ]
                            if (tile == nodata).all():
                                continue
                            tile_window = Window(col, row, tile.shape[1], tile.shape[0])
                            tile_transform = window_transform(tile_window, chunk_transform)
                            locations.append(location)
                            rasts.append(raster_tile_wkb(tile, tile_transform, srid, nodata))
                            footprints.append(box(*window_bounds(tile_window, chunk_transform)))

        return gpd.GeoDataFrame(
            {"location": locations, "rast": rasts}, geometry=footprints, crs=src.crs
        )


def generate_raster_habitat_tiles(
    habitat: str,
    raster_file_name: str,
    total_area_file: str,
    pa_file: str,
    tolerance=TOLERANCE,
    bucket: str = BUCKET,
    n_jobs: int = 4,
    verbose: bool = True,
):
    """
    Subtracts protected areas from a habitat raster inside each location and saves
    the unprotected pixels to GCS as PostGIS raster tiles, one Parquet per location.

    Each location's file is uploaded as soon as it is done, so only the locations
    in progress are held in memory: the global tiles run to many GB uncompressed.
    Once every location is written, files in the live folder that this run did not
    write, such as those of a location since dropped or left with no unprotected
    habitat, are deleted so the load step never picks them up.

    Parameters
    ----------
    habitat : str
        Habitat name used in the output folder names.
    raster_file_name : str
        GCS path of the single-band uint8 habitat raster.
    total_area_file : str
        Filename of the locations file the habitat is attributed to.
    pa_file : str
        Filename of the protected areas file to subtract, carrying an ISO3 column.
    tolerance : float
        Tolerance value used in simplification.
    bucket : str
        GCS bucket name.
    n_jobs : int
        Number of locations processed at once; each holds its tiles in memory.
    verbose : bool, optional
        Whether to print verbose logs, by default True.

    Returns
    -------
        Names of the live blobs written, one ``{location}.parquet`` per location
        holding unprotected habitat, each also saved to a dated archive folder.
    """
    local_raster = raster_file_name.split("/")[-1]
    download_file_from_gcs(bucket, raster_file_name, local_raster, verbose=verbose)

    total_area = read_geo_df(
        bucket_name=bucket,
        filename=add_tolerance_suffix(total_area_file, tolerance),
        verbose=verbose,
    )
    total_area = total_area[["location", "geometry"]]
    locations = total_area["location"].unique().tolist()

    pa = load_pa_by_location(read_geo_df, pa_file, tolerance, bucket=bucket, verbose=verbose)

    out_dir = CONSERVATION_BUILDER_HABITAT_TILES_DIR_PATTERN.format(habitat=habitat)
    archive_dir = ARCHIVE_CONSERVATION_BUILDER_HABITAT_TILES_DIR_PATTERN.format(habitat=habitat)

    def process_and_upload(location):
        tiles = process_location_raster_tiles(
            total_area[total_area["location"] == location].reset_index(drop=True),
            pa[pa["ISO3"] == location].reset_index(drop=True),
            local_raster,
        )
        if tiles.empty:
            return None
        out_file = f"{out_dir}/{location}.parquet"
        upload_with_archive(tiles, out_file, f"{archive_dir}/{location}.parquet", bucket=bucket)
        return out_file

    if verbose:
        logger.info({"message": f"Tiling unprotected {habitat} for {len(locations)} locations..."})
    results = tqdm(
        Parallel(n_jobs=n_jobs, backend="threading", return_as="generator_unordered")(
            delayed(process_and_upload)(location) for location in locations
        ),
        total=len(locations),
    )
    written = {out_file for out_file in results if out_file is not None}

    delete_stale_blobs(bucket, f"{out_dir}/", written, verbose=verbose)
    return written
