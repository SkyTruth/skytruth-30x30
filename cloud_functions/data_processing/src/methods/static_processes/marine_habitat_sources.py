import fnmatch
import gc
import zipfile

import fsspec
import geopandas as gpd
import numpy as np
import pandas as pd

from src.core.commons import download_and_duplicate_zipfile
from src.core.params import (
    BUCKET,
    CHUNK_SIZE,
    MARINE_HABITAT_PARAMS,
    UNEP_POINT_AREA_KM2,
)
from src.core.processors import clean_geometries
from src.utils.gcp import (
    load_zipped_shapefile_from_gcs,
    read_gzipped_gpkg_from_gcs,
)
from src.utils.geo import buffer_km, unwrap_antimeridian
from src.utils.logger import Logger

logger = Logger()


def download_marine_habitats(
    habitats: str | list[str] | None = None,
    marine_habitat_params: dict = MARINE_HABITAT_PARAMS,
    bucket: str = BUCKET,
    chunk_size: int = CHUNK_SIZE,
    verbose: bool = True,
) -> None:
    """
    Downloads marine habitat source datasets and uploads them to GCS as both
    current and archived versions.

    Parameters:
    ----------
    habitats : str | list[str] | None
        Habitat key(s) from marine_habitat_params to download. None
        downloads all of them.
    marine_habitat_params : dict
        Habitat key -> {"url", "file_name", "archive_file_name"} config.
    bucket : str
        Name of the GCS bucket where all files will be uploaded.
    chunk_size : int, optional
        Size in bytes of each chunk used during download.
    verbose : bool, optional
        If True, prints progress messages. Default is True.
    """
    if habitats is None:
        habitats = list(marine_habitat_params)
    elif isinstance(habitats, str):
        habitats = [habitats]

    unknown = set(habitats) - set(marine_habitat_params)
    if unknown:
        raise ValueError(f"unknown marine habitat(s): {sorted(unknown, key=repr)}")

    for habitat in habitats:
        download = marine_habitat_params[habitat]
        if verbose:
            logger.info({"message": f"downloading {habitat} from {download['url']}"})
        download_and_duplicate_zipfile(
            download["url"],
            bucket,
            download["file_name"],
            download["archive_file_name"],
            chunk_size=chunk_size,
            verbose=verbose,
        )


def _find_unep_layer_paths(bucket: str, zipfile_name: str) -> tuple[str, str]:
    """
    Locate the point and polygon shapefiles inside a UNEP-WCMC download.
    """
    with (
        fsspec.open(f"gs://{bucket}/{zipfile_name}", mode="rb") as remote_zip,
        zipfile.ZipFile(remote_zip) as zf,
    ):
        names = zf.namelist()

    def match_layer(pattern: str) -> str:
        matches = [name for name in names if fnmatch.fnmatch(name, pattern)]
        if len(matches) != 1:
            raise ValueError(
                f"expected exactly one layer matching {pattern} in {zipfile_name}, "
                f"found {len(matches)}: {matches}"
            )
        return matches[0]

    return match_layer("*/01_Data/*_Pt_*.shp"), match_layer("*/01_Data/*_Py_*.shp")


def _buffer_unep_points(
    points: gpd.GeoDataFrame,
    fallback_area_km2: float = UNEP_POINT_AREA_KM2,
) -> gpd.GeoDataFrame:
    """Convert a UNEP-WCMC point layer into polygons by buffering each point.

    Where a reported area is recorded, the radius is derived (r = sqrt(area/pi));
    where it is not, the point is buffered so that the area equals
    fallback_area_km2 (default 1 km²).
    """
    points = points.explode(index_parts=False).reset_index(drop=True)

    reported_area_km2 = pd.to_numeric(points["REP_AREA_K"], errors="coerce")
    area_km2 = reported_area_km2.where(reported_area_km2 > 0, fallback_area_km2)

    # Buffer points
    buffered = points.to_crs("EPSG:6933")
    buffered["geometry"] = buffered.geometry.buffer(np.sqrt(area_km2 / np.pi) * 1000)
    buffered = buffered.to_crs(points.crs)

    wrapped = buffered.geometry.bounds.eval("maxx - minx") > 180
    if wrapped.any():
        buffered.loc[wrapped, "geometry"] = [
            buffer_km(point, km=radius_km)
            for point, radius_km in zip(
                points.geometry[wrapped], np.sqrt(area_km2[wrapped] / np.pi), strict=True
            )
        ]

    buffered["rep_area_km2"] = reported_area_km2
    return buffered


def _load_habitat_geometry(
    habitat: str,
    params: dict,
    bucket: str,
    fallback_area_km2: float,
    verbose: bool,
) -> gpd.GeoDataFrame:
    """Read one habitat's source and return a single frame ready to dissolve.

    * gpkg: a single gzipped GeoPackage of polygons (Global Mangrove Watch).
    * shapefile: one polygon shapefile inside a zip, named by ``shapefile_name``
      (ZSL seamounts). Its antimeridian crossings are split before dissolving.
    * wcmc: a UNEP-WCMC zip holding a point and a polygon shapefile. The points are
      buffered into polygons (see _buffer_unep_points) and merged with the polygon
      layer.
    """
    file_name = params["file_name"]

    if params["source"] == "gpkg":
        if verbose:
            logger.info({"message": f"loading {habitat} from {file_name}"})
        return read_gzipped_gpkg_from_gcs(bucket, file_name, columns=[], verbose=verbose)

    if params["source"] == "shapefile":
        if verbose:
            logger.info({"message": f"loading {habitat} from {file_name}"})
        geometry = load_zipped_shapefile_from_gcs(
            file_name, bucket, internal_shapefile_path=params["shapefile_name"]
        ).pipe(clean_geometries)
        geometry["geometry"] = geometry.geometry.apply(unwrap_antimeridian)
        return geometry[["geometry"]]

    if verbose:
        logger.info({"message": f"locating {habitat} layers in {file_name}"})
    point_layer, polygon_layer = _find_unep_layer_paths(bucket, file_name)

    if verbose:
        logger.info({"message": f"loading {habitat} point layer {point_layer}"})
    points = load_zipped_shapefile_from_gcs(file_name, bucket, internal_shapefile_path=point_layer)

    if verbose:
        logger.info({"message": f"buffering {len(points)} {habitat} point records"})
    buffered_points = _buffer_unep_points(points, fallback_area_km2=fallback_area_km2)

    if verbose:
        logger.info({"message": f"loading {habitat} polygon layer {polygon_layer}"})
    polygons = load_zipped_shapefile_from_gcs(
        file_name, bucket, internal_shapefile_path=polygon_layer
    ).pipe(clean_geometries)
    polygons["rep_area_km2"] = pd.to_numeric(polygons.get("REP_AREA_K"), errors="coerce")

    columns = ["rep_area_km2", "geometry"]
    buffered_points["source"] = "point"
    polygons["source"] = "polygon"
    merged = gpd.GeoDataFrame(
        pd.concat(
            [buffered_points[["source", *columns]], polygons[["source", *columns]]],
            ignore_index=True,
        ),
        geometry="geometry",
        crs=polygons.crs,
    ).pipe(clean_geometries)

    del points, buffered_points, polygons
    gc.collect()

    return merged
