import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from joblib import Parallel, delayed
from rasterio.features import rasterize, shapes
from rasterio.windows import from_bounds
from shapely import MultiPolygon
from shapely.geometry import shape
from shapely.validation import make_valid
from tqdm.auto import tqdm

from src.core.commons import add_tolerance_suffix
from src.core.params import (
    ARCHIVE_CONSERVATION_BUILDER_HABITAT_DATA_PATTERN,
    BUCKET,
    CONSERVATION_BUILDER_HABITAT_DATA_PATTERN,
    TOLERANCE,
)
from src.methods.subtract_geometries.io import load_pa_by_location, upload_with_archive
from src.utils.gcp import (
    download_file_from_gcs,
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
