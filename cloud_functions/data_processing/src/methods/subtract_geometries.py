import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from joblib import Parallel, delayed
from rasterio.features import rasterize, shapes
from rasterio.windows import Window, from_bounds, intersection
from shapely import MultiPolygon
from shapely.geometry import box, shape
from shapely.validation import make_valid
from tqdm.auto import tqdm

from src.core.commons import add_tolerance_suffix
from src.core.params import (
    ARCHIVE_CONSERVATION_BUILDER_HABITAT_DATA_PATTERN,
    BUCKET,
    BUFFERED_MARINE_LOCATIONS_FILE_NAME,
    CONSERVATION_BUILDER_HABITAT_DATA_PATTERN,
    HABITAT_BY_LOCATION_FILE_PATTERN,
    TOLERANCE,
    WDPA_WITH_BUFFERED_SEAS_FILE_NAME,
)
from src.core.processors import filter_protected_planet
from src.utils.gcp import (
    download_file_from_gcs,
    read_json_df,  # Reads a .json or .geojson file from GCS and returns a DataFrame or GeoDataFrame
    read_parquet_from_gcs,  # Reads a .parquet file from GCS and returns a GeoDataFrame
    upload_gdf,  # Saves a GeoDataFrame to GCS as a GeoJSON or Parquet
)
from src.utils.geo import robust_unary_union
from src.utils.logger import Logger

logger = Logger()


def process_country(country_area: gpd.GeoDataFrame, country_pa: gpd.GeoDataFrame):
    """
    Subtracts protected areas from total area for a country.

    Parameters
    ----------
    country_pa : gpd.GeoDataFrame
        GeoDataFrame with protected areas for a country.
    country_area : gpd.GeoDataFrame
        GeoDataFrame with total area for a country.

    Returns
    -------
        GeoDataFrame with protected areas subtracted from total area for a country.
    """
    if country_pa.empty:
        # If no protected areas, return original boundary
        return country_area
    else:
        # If protected areas found, return original boundary with protected areas removed
        pa_union = country_pa.geometry.union_all()
        country_area.geometry = country_area.geometry.difference(pa_union)
        return country_area


def process_country_habitat(
    country_area: gpd.GeoDataFrame, country_pa: gpd.GeoDataFrame, habitat: gpd.GeoDataFrame
):
    """
    Returns the unprotected habitat within a country.

    The habitat near the country is dissolved first and clipped to the country
    boundary once, rather than clipped feature by feature. Every clip pays for the
    country's full vertex count, so on a dense archipelagic boundary that ordering,
    not the number of habitat features, is what dominates the runtime. The
    country's protected areas are then subtracted from the clipped result.

    Parameters
    ----------
    country_area : gpd.GeoDataFrame
        GeoDataFrame with total area for a country.
    country_pa : gpd.GeoDataFrame
        GeoDataFrame with protected areas for a country.
    habitat : gpd.GeoDataFrame
        GeoDataFrame of habitat geometries, in the same CRS as country_area. The
        spatial index is built on first use, so pass one frame across countries
        rather than a per-country slice.

    Returns
    -------
        Single-row GeoDataFrame of unprotected habitat carrying country_area's
        columns, or an empty GeoDataFrame with those columns where the country
        holds none of the habitat.
    """
    country_area = country_area.copy()
    country_geom = country_area.geometry.union_all()

    nearby = habitat.geometry.values[habitat.sindex.query(country_geom, predicate="intersects")]
    if len(nearby) == 0:
        return country_area.iloc[:0]

    habitat_union = robust_unary_union(nearby).intersection(country_geom)

    if not country_pa.empty:
        habitat_union = habitat_union.difference(robust_unary_union(country_pa.geometry.values))

    if habitat_union.is_empty:
        return country_area.iloc[:0]

    country_area.geometry = [habitat_union]
    return country_area


def generate_total_area_minus_pa(
    total_area_file: str,
    pa_file: str,
    out_file: str,
    archive_out_file: str,
    tolerance: float,
    bucket: str = BUCKET,
    verbose: bool = True,
):
    """
    Subtracts protected areas from the corresponding terrestrial or marine boundaries;
    saves the output as a zipped shapefile to GCS.

    Parameters
    ----------
    bucket : str
        GCS bucket name.
    total_area_file : str
        Filename of total area geojson (GADM or EEZ).
    pa_file : str
        Filename of protected area geojson (PA or MPA).
    is_processed : bool
        Whether the protected areas GeoDataFrame is already processed and dissolved by country.
    out_file : str
        Filename for output zipped file.
    tolerance : float
        Tolerance value used in simplification.
    verbose : bool, optional
        Whether to print verbose logs, by default True.

    Returns
    -------
        GeoDataFrame saved to GCS as a Parquet.
    """

    # Total areas: GADM (terrestrial) or EEZ (marine)
    total_area = read_json_df(
        bucket_name=bucket,
        filename=add_tolerance_suffix(total_area_file, tolerance),
        verbose=verbose,
    )
    total_area = total_area[["location", "geometry"]]

    # Get list of unique country codes
    countries = total_area["location"].unique().tolist()

    # Protected areas: PA (terrestrial) or MPA (marine)
    pa_file = add_tolerance_suffix(pa_file, tolerance)
    read_pa = read_parquet_from_gcs if pa_file.endswith(".parquet") else read_json_df
    pa = read_pa(
        bucket_name=bucket,
        filename=pa_file,
        verbose=verbose,
    ).pipe(filter_protected_planet)

    # Create one row per country
    pa["ISO3"] = pa["ISO3"].str.split(";")
    pa = pa.explode("ISO3")
    pa["ISO3"] = pa["ISO3"].str.strip()

    # Keep only polygon records and make the geometries valid
    pa = pa[pa.geometry.geom_type.isin(["MultiPolygon", "Polygon"])].copy()
    pa.geometry = pa.geometry.make_valid()

    # Subtract geometries
    if verbose:
        logger.info({"message": "Subtracting protected areas from total areas..."})
    results = Parallel(n_jobs=-1, backend="loky")(
        delayed(process_country)(
            total_area[total_area["location"] == country].reset_index(),
            pa[pa["ISO3"] == country].reset_index(),
        )
        for country in tqdm(countries)
    )

    total_area_minus_pa = pd.concat(results).reset_index(drop=True)
    if verbose:
        logger.info({"message": f"Output file has {len(total_area_minus_pa)} rows."})

    # Save to GCS
    upload_gdf(
        bucket_name=bucket,
        gdf=total_area_minus_pa,
        destination_blob_name=out_file,
    )

    # Save to archive
    upload_gdf(
        bucket_name=bucket,
        gdf=total_area_minus_pa,
        destination_blob_name=archive_out_file,
    )


def generate_habitat_minus_pa(
    habitat: str,
    total_area_file=BUFFERED_MARINE_LOCATIONS_FILE_NAME,
    pa_file=WDPA_WITH_BUFFERED_SEAS_FILE_NAME,
    tolerance=TOLERANCE,
    bucket: str = BUCKET,
    n_jobs: int = -1,
    verbose: bool = True,
):
    """
    Subtracts protected areas from the habitat lying inside each country's boundaries;
    saves the output to GCS as a Parquet.

    The counterpart of ``generate_total_area_minus_pa``: same inputs and the same
    per-country fan-out, but each row is a country's unprotected *habitat* rather than
    its unprotected area. Countries holding none of the habitat are dropped rather than
    written as empty rows, so the output is usually far shorter than the location list.

    Parameters
    ----------
    habitat : str
        Habitat key.
    total_area_file : str
        Filename of the buffered marine locations parquet.
    pa_file : str
        Filename of the protected areas parquet written by a buffered
        ``generate_iho_pa_intersections`` run: both estates, carrying a row per PA per
        near-shore sea area it lies in. Coastal habitats are often designated inside PAs
        that WDPA flags MARINE=0, hence both estates rather than the marine one alone.
    tolerance : float
        Tolerance value used in simplification.
    bucket : str
        GCS bucket name.
    verbose : bool, optional
        Whether to print verbose logs, by default True.

    Returns
    -------
        GeoDataFrame saved to GCS as a Parquet, one row per country holding habitat.
    """

    habitat_gdf = read_parquet_from_gcs(
        bucket_name=bucket,
        filename=HABITAT_BY_LOCATION_FILE_PATTERN.format(habitat=habitat),
        verbose=verbose,
    )

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
    pa = read_parquet_from_gcs(
        bucket_name=bucket,
        filename=add_tolerance_suffix(pa_file, tolerance),
        verbose=verbose,
    ).pipe(filter_protected_planet)

    # Create one row per country
    pa["ISO3"] = pa["ISO3"].str.split(";")
    pa = pa.explode("ISO3")
    pa["ISO3"] = pa["ISO3"].str.strip()

    # Keep only polygon records and make the geometries valid
    pa = pa[pa.geometry.geom_type.isin(["MultiPolygon", "Polygon"])].copy()
    pa.geometry = pa.geometry.make_valid()

    # Build the habitat index once here rather than once per country inside the workers
    habitat_gdf.sindex.query(box(0, 0, 0, 0))

    # Subtract geometries
    if verbose:
        logger.info({"message": "Subtracting protected areas from habitat areas..."})
    results = Parallel(n_jobs=n_jobs, backend="threading")(
        delayed(process_country_habitat)(
            total_area[total_area["location"] == country].reset_index(drop=True),
            pa[pa["ISO3"] == country].reset_index(drop=True),
            habitat_gdf,
        )
        for country in tqdm(countries)
    )

    populated = [result for result in results if not result.empty]
    habitat_minus_pa = (
        pd.concat(populated).reset_index(drop=True) if populated else total_area.iloc[:0]
    )
    if verbose:
        logger.info({"message": f"Output file has {len(habitat_minus_pa)} rows."})

    # Save to GCS
    out_file = CONSERVATION_BUILDER_HABITAT_DATA_PATTERN.format(habitat=habitat)
    archive_out_file = ARCHIVE_CONSERVATION_BUILDER_HABITAT_DATA_PATTERN.format(habitat=habitat)

    upload_gdf(
        bucket_name=bucket,
        gdf=habitat_minus_pa,
        destination_blob_name=out_file,
    )

    upload_gdf(
        bucket_name=bucket,
        gdf=habitat_minus_pa,
        destination_blob_name=archive_out_file,
    )


def generate_location_minus_fhp_mpa(
    mpa_file: str,
    loc_file: str,
    out_file: str,
    archive_out_file: str,
    tolerance: float,
    bucket: str = BUCKET,
    verbose: bool = True,
):
    """
    Differences fully/highly protected MPAs (as defined by MPAtlas) from a location file (such as
    Global EEZs or EEZ + IHO).

    Parameters
    ----------
    bucket : str
        GCS bucket name.
    mpa_file : str
            Filename of MPAtlas area geojson.
    loc_file : str
        Filename of location data geojson.
    out_file
        Filename for output file.
    tolerance : float
        Tolerance value used in simplification.
    verbose : bool, optional
        Whether to print verbose logs, by default True.

    Returns
    -------
        GeoDataFrame of Location with areas intersecting Highly/Fully protected MPAs removed, saved
        to GCS as a Parquet file.
    """

    read_mpa = read_parquet_from_gcs if mpa_file.endswith(".parquet") else read_json_df
    mpa = read_mpa(
        bucket_name=bucket,
        filename=mpa_file,
        verbose=verbose,
    )

    location = read_json_df(
        bucket_name=bucket,
        filename=add_tolerance_suffix(loc_file, tolerance),
        verbose=verbose,
    )

    # Select records where protection_mpaguide_level is full or high
    mpa_fhp = mpa[mpa["protection_mpaguide_level"].isin(["full", "high"])]

    # Keep only polygon / multipolygon records and make the geometries valid
    mpa_fhp = mpa_fhp[mpa_fhp.geometry.geom_type.isin(["MultiPolygon", "Polygon"])].copy()
    mpa_fhp.geometry = mpa_fhp.geometry.make_valid()

    location = location[location.geometry.geom_type.isin(["MultiPolygon", "Polygon"])].copy()
    location.geometry = location.geometry.make_valid()

    if verbose:
        logger.info({"message": "Subtracting fully/highly protected areas from location areas..."})

    # A zone may span multiple countries (e.g. "AUS,NZL"); one row per country
    # so its geometry is subtracted from every location it belongs to
    mpa_fhp["country"] = mpa_fhp["country"].astype(str).str.split(r"[;:,]")
    mpa_fhp = mpa_fhp.explode("country")
    mpa_fhp["country"] = mpa_fhp["country"].str.strip()

    # Difference the mpa_fhp from location; where location["location"] == mpa_fhp["country"]
    mpa_by_country = mpa_fhp.dissolve(by="country")["geometry"]

    location = location.copy()
    location["_mpa"] = location["location"].map(
        mpa_by_country
    )  # is NaN where a country has no FHP MPAS

    has_mpa = location["_mpa"].notna()

    location.loc[has_mpa, "geometry"] = location.loc[has_mpa, "geometry"].difference(
        gpd.GeoSeries(location.loc[has_mpa, "_mpa"], crs=location.crs)
    )
    non_fh_protected_location_area = location.drop(columns="_mpa")

    if verbose:
        logger.info({"message": f"Output file has {len(non_fh_protected_location_area)} rows."})

    # Save to GCS
    upload_gdf(
        bucket_name=bucket,
        gdf=non_fh_protected_location_area,
        destination_blob_name=out_file,
    )

    # Save to archive
    upload_gdf(
        bucket_name=bucket,
        gdf=non_fh_protected_location_area,
        destination_blob_name=archive_out_file,
    )


def process_country_raster_habitat(
    country_area: gpd.GeoDataFrame,
    country_pa: gpd.GeoDataFrame,
    raster_path: str,
    class_map: dict,
    connectivity: int = 4,
):
    """
    Returns the unprotected habitat within a country, polygonized from a raster.

    The raster counterpart of ``process_country_habitat``. The country boundary and
    its protected areas are burned onto the raster's own grid and removed there
    rather than differenced as vectors, so the unprotected extent covers the same
    pixels the published habitat stats are computed over, and the union and
    difference that dominate the vector path are never run. Only the window
    covering the country is read.

    The polygons ``shapes`` returns tile the masked pixels without overlapping, so
    each class's parts are assembled into one MultiPolygon directly; a union would
    return the same geometry at far greater cost.

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

    Returns
    -------
        GeoDataFrame in EPSG:4326 with one row per class the country holds,
        columns ["location", "habitat", "geometry"], or an empty GeoDataFrame
        with those columns where the country holds none of the habitat.
    """
    empty = gpd.GeoDataFrame({"location": [], "habitat": []}, geometry=[], crs="EPSG:4326")
    location = country_area["location"].iloc[0]

    with rasterio.open(raster_path) as src:
        raster_crs = src.crs
        country_geom = robust_unary_union(
            country_area.to_crs(raster_crs).geometry.apply(make_valid).values
        )
        if not country_geom.intersects(box(*src.bounds)):
            return empty

        window = from_bounds(*country_geom.bounds, transform=src.transform)
        window = intersection(
            window.round_offsets().round_lengths(), Window(0, 0, src.width, src.height)
        )
        habitat = src.read(1, window=window, masked=True)
        transform = src.window_transform(window)

    if habitat.size == 0:
        return empty

    # clip raster to the boundary on the grid.
    unprotected = ~np.ma.getmaskarray(habitat) & rasterize(
        [country_geom],
        out_shape=habitat.shape,
        transform=transform,
        all_touched=False,
        dtype="uint8",
    ).astype(bool)

    if not country_pa.empty:
        unprotected &= ~rasterize(
            country_pa.to_crs(raster_crs).geometry.apply(make_valid).values,
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
    pa = read_parquet_from_gcs(
        bucket_name=bucket,
        filename=add_tolerance_suffix(pa_file, tolerance),
        verbose=verbose,
    ).pipe(filter_protected_planet)

    # Create one row per country
    pa["ISO3"] = pa["ISO3"].str.split(";")
    pa = pa.explode("ISO3")
    pa["ISO3"] = pa["ISO3"].str.strip()

    # Keep only polygon records and make the geometries valid
    pa = pa[pa.geometry.geom_type.isin(["MultiPolygon", "Polygon"])].copy()
    pa.geometry = pa.geometry.make_valid()

    # Subtract geometries
    if verbose:
        logger.info({"message": "Subtracting protected areas from habitat areas..."})
    results = Parallel(n_jobs=n_jobs, backend="threading")(
        delayed(process_country_raster_habitat)(
            total_area[total_area["location"] == country].reset_index(drop=True),
            pa[pa["ISO3"] == country].reset_index(drop=True),
            local_raster,
            class_map,
        )
        for country in tqdm(countries)
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

        out_file = CONSERVATION_BUILDER_HABITAT_DATA_PATTERN.format(habitat=habitat)
        archive_out_file = ARCHIVE_CONSERVATION_BUILDER_HABITAT_DATA_PATTERN.format(habitat=habitat)

        # Save to GCS
        upload_gdf(
            bucket_name=bucket,
            gdf=rows,
            destination_blob_name=out_file,
        )

        # Save to archive
        upload_gdf(
            bucket_name=bucket,
            gdf=rows,
            destination_blob_name=archive_out_file,
        )
