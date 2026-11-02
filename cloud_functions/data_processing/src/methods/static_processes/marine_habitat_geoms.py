import gc

import geopandas as gpd
import numpy as np
import shapely
from joblib import Parallel, delayed
from tqdm.auto import tqdm

from src.core.commons import add_tolerance_suffix, safe_union
from src.core.params import (
    BUCKET,
    BUFFERED_MARINE_LOCATIONS_FILE_NAME,
    GLOBAL_HABITAT_AREA_FILE_PATTERN,
    HABITAT_BY_LOCATION_FILE_PATTERN,
    HABITAT_PROCESSING_PARAMS,
    PROJECT,
    TOLERANCE,
    UNEP_POINT_AREA_KM2,
)
from src.methods.static_processes.marine_habitat_sources import _load_habitat_geometry
from src.utils.gcp import read_parquet_from_gcs, save_json_to_gcs, upload_gdf
from src.utils.geo import fast_union_area_km2, get_area_km2
from src.utils.logger import Logger

logger = Logger()


def _clip_and_union_habitat(
    location: str,
    parts: np.ndarray,
    location_geom,
    batch_size: int,
) -> dict | None:
    """Clip a location's habitat parts to its boundary and dissolve them into one geometry.

    Returns one row of the shared by-location schema, or None when the location holds
    no habitat.
    """
    clipped = shapely.intersection(parts, location_geom)
    clipped = clipped[~shapely.is_missing(clipped) & ~shapely.is_empty(clipped)]
    if len(clipped) == 0:
        return None

    habitat_geom = safe_union(
        gpd.GeoSeries(clipped), batch_size=batch_size, simplify_tolerance=None
    )
    if habitat_geom is None or habitat_geom.is_empty:
        return None

    return {
        "location": location,
        "n_habitat_polygons": int(len(clipped)),
        "bbox": location_geom.bounds,
        "area_km2": get_area_km2(habitat_geom),
        "geometry": habitat_geom,
    }


def process_marine_habitat_geoms(
    habitats: str | list[str] | None = None,
    habitat_params: dict = HABITAT_PROCESSING_PARAMS,
    marine_locations_file_name: str = BUFFERED_MARINE_LOCATIONS_FILE_NAME,
    by_location_file_pattern: str = HABITAT_BY_LOCATION_FILE_PATTERN,
    global_area_file_pattern: str = GLOBAL_HABITAT_AREA_FILE_PATTERN,
    fallback_area_km2: float = UNEP_POINT_AREA_KM2,
    bucket: str = BUCKET,
    project: str = PROJECT,
    verbose: bool = True,
    tolerance: float = TOLERANCE,
    simplify_tolerance: float = TOLERANCE,
    batch_size: int = 3000,
    n_jobs: int = -1,
) -> None:
    """Turn downloaded habitat sources into per-location geometries and a global area.
    Each location's habitat is clipped to its boundary before being dissolved.

    Parameters:
    ----------
    habitats : str | list[str] | None
        Habitat key(s) from habitat_params to process. None processes all of them.
    habitat_params : dict
        Habitat key -> {"file_name", "source", "overlaps", ...} config.
    marine_locations_file_name : str
        GCS blob of the buffered marine locations - the land/EEZ union, the near-shore
        IHO sea areas and the high seas - to dissolve by.
    by_location_file_pattern : str
        Template for the dissolved per-location blob name.
    global_area_file_pattern : str
        Template for the global area JSON blob name.
    fallback_area_km2 : float
        Area assigned to UNEP-WCMC points with no reported area.
    bucket : str
        GCS bucket to read from and write to.
    project : str
        GCP project used for uploads.
    verbose : bool
        If True, logs progress.
    tolerance : float
        Which simplification of the location boundaries to read (file suffix only).
    simplify_tolerance : float
        Simplification applied to the habitat geometry before dissolving.
    batch_size : int
        Batch size passed to safe_union.
    n_jobs : int
        Worker count for the per-location clip and dissolve. -1 uses every core.
    """
    if habitats is None:
        habitats = list(habitat_params.keys())
    elif isinstance(habitats, str):
        habitats = [habitats]

    unknown = set(habitats) - set(habitat_params.keys())
    if unknown:
        raise ValueError(f"unknown marine habitat(s): {sorted(unknown, key=repr)}")

    if verbose:
        logger.info({"message": "loading marine locations"})
    regions = read_parquet_from_gcs(
        bucket, add_tolerance_suffix(marine_locations_file_name, tolerance), verbose=verbose
    )
    location_geoms = (
        regions.dropna(subset=["location"])
        .drop_duplicates(subset=["location"])
        .set_index("location")
        .geometry.sort_index()
    )

    for habitat in habitats:
        params = habitat_params[habitat]
        geometry = _load_habitat_geometry(habitat, params, bucket, fallback_area_km2, verbose)

        if geometry.crs is not None and geometry.crs != regions.crs:
            geometry = geometry.to_crs(regions.crs)

        if verbose:
            logger.info({"message": f"exploding, simplifying and validating {habitat} geometry"})
        geometry = geometry.explode(index_parts=False, ignore_index=True)
        geometry["geometry"] = shapely.make_valid(
            shapely.simplify(geometry.geometry.values, simplify_tolerance)
        )
        geometry = geometry[~geometry.geometry.is_empty & geometry.geometry.notna()]

        if verbose:
            logger.info({"message": f"computing global {habitat} area"})
        if len(geometry) == 0:
            global_area_km2 = 0.0
        elif params["overlaps"]:
            global_area_km2 = fast_union_area_km2(list(geometry.geometry.values), n_jobs)
        else:
            global_area_km2 = float(geometry.geometry.to_crs("EPSG:6933").area.sum() / 1e6)

        save_json_to_gcs(
            bucket,
            {"global_area_km2": global_area_km2},
            global_area_file_pattern.format(habitat=habitat),
            project,
            verbose,
        )

        if verbose:
            logger.info({"message": f"dissolving {habitat} by location"})
        geometry_sindex = geometry.sindex

        jobs = []
        for location, location_geom in location_geoms.items():
            if location_geom is None or location_geom.is_empty:
                continue
            indices = geometry_sindex.query(location_geom, predicate="intersects")
            if len(indices) == 0:
                continue
            jobs.append((location, geometry.geometry.values[indices], location_geom))

        results = Parallel(n_jobs=n_jobs, backend="loky")(
            delayed(_clip_and_union_habitat)(location, parts, location_geom, batch_size)
            for location, parts, location_geom in tqdm(jobs)
        )

        habitat_by_location = gpd.GeoDataFrame(
            [{**result, "habitat": habitat} for result in results if result is not None],
            columns=[
                "location",
                "n_habitat_polygons",
                "bbox",
                "area_km2",
                "geometry",
                "habitat",
            ],
            geometry="geometry",
            crs="EPSG:4326",
        )

        upload_gdf(
            bucket,
            habitat_by_location,
            by_location_file_pattern.format(habitat=habitat),
            project_id=project,
            verbose=verbose,
            timeout=600,
        )

        del geometry, habitat_by_location
        gc.collect()
