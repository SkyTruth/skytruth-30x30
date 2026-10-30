from functools import partial
from typing import Any

import geopandas as gpd
import pandas as pd

from src.core.commons import add_tolerance_suffix, read_mpatlas_from_gcs
from src.core.map_params import (
    COUNTRIES_TILESET_FILE,
    COUNTRIES_TILESET_ID,
    COUNTRIES_TILESET_NAME,
    EEZ_TILESET_FILE,
    EEZ_TILESET_ID,
    EEZ_TILESET_NAME,
    MARINE_REGIONS_TILESET_FILE,
    MARINE_REGIONS_TILESET_ID,
    MARINE_REGIONS_TILESET_NAME,
    MPATLAS_TILESET_ARCHIVE_FILE,
    MPATLAS_TILESET_FILE,
    MPATLAS_TILESET_ID,
    MPATLAST_TILESET_NAME,
    PMTILES_BUCKET,
    TERRESTRIAL_REGIONS_TILESET_FILE,
    TERRESTRIAL_REGIONS_TILESET_ID,
    TERRESTRIAL_REGIONS_TILESET_NAME,
)
from src.core.params import (
    BUCKET,
    EEZ_FILE_NAME,
    EEZ_MULTIPLE_SOV_FILE_NAME,
    GADM_FILE_NAME,
    LOCATIONS_TRANSLATED_FILE_NAME,
    MARINE_HABITAT_PARAMS,
    MPATLAS_FILE_NAME,
    REGIONS_FILE_NAME,
    RELATED_COUNTRIES_FILE_NAME,
    TOLERANCE,
    UNEP_POINT_AREA_KM2,
)
from src.core.processors import add_translations
from src.core.retry_params import METHOD_RETRY_CONFIGS, ScheduleRetry
from src.methods.static_processes import (
    _find_unep_layer_paths,
    _load_habitat_geometry,
    _simplify_habitat_geometry,
)
from src.utils.gcp import load_zipped_shapefile_from_gcs, read_dataframe, read_json_from_gcs
from src.utils.logger import Logger
from src.utils.tileset_pipelines.vector_pmtiles_pipeline import (
    VectorPMTilesetConfig,
    run_vector_pmtiles_pipeline,
)
from src.utils.tileset_pipelines.vector_tile_pipeline import (
    MBTilesetConfig,
    run_vector_tileset_pipeline,
)

logger = Logger()


def mpatlas_process(gdf: gpd.GeoDataFrame, ctx: dict[str, Any]):
    gdf = gdf.rename(
        columns={
            "designation": "designatio",
            "establishment_stage": "establishm",
            "country": "location_i",
            "zone_id": "zone_id",
            "protection_mpaguide_level": "protection",
            "implemented_date": "year",
        }
    )

    # Create a new bucketed column based on the protection value, returning only
    # 1. fully or highly or
    # 2. less or unknown
    gdf["protecti_1"] = gdf["protection"].apply(
        lambda x: "fully or highly" if x in ["full", "high"] else "less or unknown"
    )

    keep = [
        "designatio",
        "establishm",
        "location_i",
        "zone_id",
        "name",
        "protection",
        "protecti_1",
        "wdpa_id",
        "wdpa_pid",
        "year",
        "geometry",
    ]

    # simplify geometry to match same simplification of Protected Areas
    gdf["geometry"] = gdf["geometry"].simplify(TOLERANCE)
    gdf["geometry"] = gdf["geometry"].make_valid()

    gdf.drop(columns=list(set(gdf.columns) - set(keep)), inplace=True)

    return gdf


def create_and_update_mpatlas_tileset(
    source_bucket: str = BUCKET,
    source_file: str = MPATLAS_FILE_NAME,
    output_bucket: str = PMTILES_BUCKET,
    output_blob: str = MPATLAS_TILESET_FILE,
    archive_bucket: str = BUCKET,
    archive_blob: str = MPATLAS_TILESET_ARCHIVE_FILE,
    layer_name: str = MPATLAS_TILESET_ID,
    display_name: str = MPATLAST_TILESET_NAME,
    method: str = "update_mpatlas_tileset",
    verbose: bool = False,
    *,
    keep_temp: bool = False,
):
    try:
        if verbose:
            logger.info({"message": f"Creating and updating {display_name} tileset..."})

        config = VectorPMTilesetConfig(
            source_bucket=source_bucket,
            source_file=source_file,
            output_bucket=output_bucket,
            output_blob=output_blob,
            archive_bucket=archive_bucket,
            archive_blob=archive_blob,
            layer_name=layer_name,
            display_name=display_name,
            verbose=verbose,
            keep_temp=keep_temp,
        )

        return run_vector_pmtiles_pipeline(
            config, process=mpatlas_process, read_source=read_mpatlas_from_gcs
        )
    except Exception as e:
        logger.error(
            {
                "message": f"Error creating and updating {display_name} tileset",
                "error": str(e),
            }
        )
        retry_cfg = METHOD_RETRY_CONFIGS.get(method)
        if retry_cfg:
            raise ScheduleRetry(
                delay_seconds=retry_cfg["delay_seconds"],
                max_retries=retry_cfg["max_retries"],
                message=f"{display_name} tileset update failed: {e}",
            ) from e
        raise


def eez_process(gdf: gpd.GeoDataFrame, ctx: dict[str, Any]):
    gdf.drop(columns=["MRGID", "AREA_KM2"], errors="ignore", inplace=True)
    return gdf


def create_and_update_eez_tileset(
    bucket: str = BUCKET,
    source_file: str = EEZ_MULTIPLE_SOV_FILE_NAME,
    tileset_file: str = EEZ_TILESET_FILE,
    tileset_id: str = EEZ_TILESET_ID,
    display_name: str = EEZ_TILESET_NAME,
    tolerance: float = TOLERANCE,
    verbose: bool = False,
    *,
    keep_temp: bool = False,
):
    try:
        if verbose:
            logger.info({"message": "Creating and updating EEZ tileset..."})

        cfg = MBTilesetConfig(
            bucket=bucket,
            tileset_blob_name=tileset_file,
            tileset_id=tileset_id,
            display_name=display_name,
            local_geojson_name="eez.geojson",
            local_mbtiles_name=f"{tileset_id}.mbtiles",
            source_file=add_tolerance_suffix(source_file, tolerance),
            verbose=verbose,
            keep_temp=keep_temp,
        )

        return run_vector_tileset_pipeline(cfg, process=eez_process)

    except Exception as excep:
        logger.error({"message": "Error creating and updating EEZ tileset", "error": str(excep)})
        raise excep


def create_and_update_marine_regions_tileset(
    bucket: str = BUCKET,
    source_file: str = EEZ_FILE_NAME,
    tileset_file: str = MARINE_REGIONS_TILESET_FILE,
    tileset_id: str = MARINE_REGIONS_TILESET_ID,
    display_name: str = MARINE_REGIONS_TILESET_NAME,
    tolerance: float = TOLERANCE,
    verbose: bool = False,
    *,
    keep_temp: bool = False,
):
    try:
        if verbose:
            logger.info({"message": "Creating and updating EEZ tileset..."})

        cfg = MBTilesetConfig(
            bucket=bucket,
            tileset_blob_name=tileset_file,
            tileset_id=tileset_id,
            display_name=display_name,
            local_geojson_name="marine_regions.geojson",
            local_mbtiles_name=f"{tileset_id}.mbtiles",
            source_file=add_tolerance_suffix(source_file, tolerance),
            verbose=verbose,
            keep_temp=keep_temp,
            extra={
                "translation_file": LOCATIONS_TRANSLATED_FILE_NAME,
                "regions_file": REGIONS_FILE_NAME,
            },
        )

        return run_vector_tileset_pipeline(cfg, process=marine_regions_process)
    except Exception as excep:
        logger.error(
            {"message": "Error creating and updating Marine Region tileset", "error": str(excep)}
        )
        raise excep


def marine_regions_process(gdf: gpd.GeoDataFrame, ctx: dict[str, Any]):
    verbose = ctx["verbose"]
    bucket = ctx["bucket"]
    translation_file: str = ctx["translation_file"]
    regions_file: str = ctx["regions_file"]

    translations_df = read_dataframe(bucket, translation_file, verbose=verbose)
    regions = read_json_from_gcs(bucket, regions_file, verbose)

    iso_to_region = {iso: region_id for region_id, iso_list in regions.items() for iso in iso_list}
    gdf["region_id"] = gdf["location"].map(iso_to_region)

    region_gdf = (
        gdf.dissolve(by="region_id", as_index=False)
        .drop(
            columns=[
                "MRGID",
                "AREA_KM2",
                "has_shared_marine_area",
                "index",
                "code",
                "location",
            ],
            errors="ignore",
        )
        .pipe(add_translations, translations_df, "region_id", "code")
        .drop(columns="code")
        .dropna(subset=["region_id"])
    )

    return region_gdf


def create_and_update_country_tileset(
    bucket: str = BUCKET,
    source_file: str = GADM_FILE_NAME,
    tileset_file: str = COUNTRIES_TILESET_FILE,
    tileset_id: str = COUNTRIES_TILESET_ID,
    display_name: str = COUNTRIES_TILESET_NAME,
    tolerance: float = TOLERANCE,
    verbose: bool = False,
    *,
    keep_temp: bool = False,
):
    try:
        if verbose:
            logger.info({"message": "Creating and updating Country tileset..."})

        cfg = MBTilesetConfig(
            bucket=bucket,
            tileset_blob_name=tileset_file,
            tileset_id=tileset_id,
            display_name=display_name,
            local_geojson_name="countries.geojson",
            local_mbtiles_name=f"{tileset_id}.mbtiles",
            source_file=add_tolerance_suffix(source_file, tolerance),
            verbose=verbose,
            keep_temp=keep_temp,
            extra={
                "translation_file": LOCATIONS_TRANSLATED_FILE_NAME,
                "related_countries_file": RELATED_COUNTRIES_FILE_NAME,
            },
        )

        return run_vector_tileset_pipeline(cfg, process=countries_process)
    except Exception as excep:
        logger.error(
            {"message": "Error creating and updating Countries tileset", "error": str(excep)}
        )
        raise excep


def countries_process(gdf: gpd.GeoDataFrame, ctx: dict[str, Any]):
    verbose = ctx["verbose"]
    bucket = ctx["bucket"]
    related_countries_file: str = ctx["related_countries_file"]
    translation_file: str = ctx["translation_file"]

    translations_df = read_dataframe(bucket, translation_file, verbose=verbose)
    related_countries = read_json_from_gcs(bucket, related_countries_file, verbose)

    country_to_sov = {}
    for iso_sov, iso_list in related_countries.items():
        if iso_sov.endswith("*"):
            for iso in iso_list:
                country_to_sov.setdefault(iso, []).append(iso_sov)

    sovs = gdf["location"].map(lambda loc: country_to_sov.get(loc, []))

    # Map sovereigns to country
    for idx in range(3):
        gdf[f"ISO_SOV{idx + 1}"] = sovs.map(
            lambda sov, idx=idx: sov[idx] if idx < len(sov) else pd.NA
        ).astype("string")

    gdf = gdf.pipe(add_translations, translations_df, "location", "code").drop(columns="code")

    return gdf


def create_and_update_terrestrial_regions_tileset(
    bucket: str = BUCKET,
    source_file: str = GADM_FILE_NAME,
    tileset_file: str = TERRESTRIAL_REGIONS_TILESET_FILE,
    tileset_id: str = TERRESTRIAL_REGIONS_TILESET_ID,
    display_name: str = TERRESTRIAL_REGIONS_TILESET_NAME,
    tolerance: float = TOLERANCE,
    verbose: bool = False,
    *,
    keep_temp: bool = False,
):
    try:
        if verbose:
            logger.info({"message": "Creating and updating Terrestrial Regions tileset..."})

        cfg = MBTilesetConfig(
            bucket=bucket,
            tileset_blob_name=tileset_file,
            tileset_id=tileset_id,
            display_name=display_name,
            local_geojson_name="terrestrial_regions.geojson",
            local_mbtiles_name=f"{tileset_id}.mbtiles",
            source_file=add_tolerance_suffix(source_file, tolerance),
            verbose=verbose,
            keep_temp=keep_temp,
            extra={
                "translation_file": LOCATIONS_TRANSLATED_FILE_NAME,
                "regions_file": REGIONS_FILE_NAME,
            },
        )

        return run_vector_tileset_pipeline(cfg, process=terrestrial_regions_process)
    except Exception as excep:
        logger.error(
            {
                "message": "Error creating and updating Terrestrial Regions tileset",
                "error": str(excep),
            }
        )
        raise excep


def terrestrial_regions_process(gdf: gpd.GeoDataFrame, ctx: dict[str, Any]):
    verbose = ctx["verbose"]
    bucket = ctx["bucket"]
    regions_file: str = ctx["regions_file"]
    translation_file: str = ctx["translation_file"]

    translations_df = read_dataframe(bucket, translation_file, verbose=verbose)
    regions = read_json_from_gcs(bucket, regions_file, verbose)

    iso_to_region = {iso: region_id for region_id, iso_list in regions.items() for iso in iso_list}
    gdf["region_id"] = gdf["location"].map(iso_to_region)

    region_gdf = (
        gdf.dissolve(by="region_id", as_index=False)
        .drop(
            columns=[
                "location",
            ],
        )
        .pipe(add_translations, translations_df, "region_id", "code")
        .drop(columns="code")
        .dropna(subset=["region_id"])
    )

    return region_gdf


def create_and_update_protected_area_tileset(
    source_file: str,
    output_blob: str,
    archive_blob: str,
    layer_name: str,
    display_name: str,
    tolerance: float,
    method: str,
    source_bucket: str = BUCKET,
    output_bucket: str = PMTILES_BUCKET,
    archive_bucket: str = BUCKET,
    verbose: bool = False,
    *,
    keep_temp: bool = False,
):
    try:
        if verbose:
            logger.info({"message": f"Creating and updating {display_name} tileset..."})

        config = VectorPMTilesetConfig(
            source_bucket=source_bucket,
            source_file=add_tolerance_suffix(source_file, tolerance),
            output_bucket=output_bucket,
            output_blob=output_blob,
            archive_bucket=archive_bucket,
            archive_blob=archive_blob,
            layer_name=layer_name,
            display_name=display_name,
            verbose=verbose,
            keep_temp=keep_temp,
        )

        return run_vector_pmtiles_pipeline(config, process=protected_area_process)
    except Exception as e:
        logger.error(
            {
                "message": f"Error creating and updating {display_name} tileset",
                "error": str(e),
            }
        )
        retry_cfg = METHOD_RETRY_CONFIGS.get(method)
        if retry_cfg:
            raise ScheduleRetry(
                delay_seconds=retry_cfg["delay_seconds"],
                max_retries=retry_cfg["max_retries"],
                message=f"{display_name} tileset update failed: {e}",
            ) from e
        raise


def protected_area_process(gdf: gpd.GeoDataFrame, ctx: dict[str, Any]):
    properties = ["GIS_AREA", "NAME", "PA_DEF", "ISO3", "WDPAID", "WDPA_PID", "geometry"]
    gdf.drop(columns=list(set(gdf.columns) - set(properties)), inplace=True)

    return gdf


def create_and_update_marine_habitat_tileset(
    habitat: str,
    output_blob: str,
    archive_blob: str,
    layer_name: str,
    display_name: str,
    method: str,
    habitat_params: dict = MARINE_HABITAT_PARAMS,
    fallback_area_km2: float = UNEP_POINT_AREA_KM2,
    source_bucket: str = BUCKET,
    output_bucket: str = PMTILES_BUCKET,
    archive_bucket: str = BUCKET,
    verbose: bool = False,
    *,
    keep_temp: bool = False,
):
    """Publish one marine habitat's downloaded source extent as vector PMTiles."""
    try:
        if verbose:
            logger.info({"message": f"Creating and updating {display_name} tileset..."})

        params = habitat_params[habitat]

        config = VectorPMTilesetConfig(
            source_bucket=source_bucket,
            source_file=params["file_name"],
            output_bucket=output_bucket,
            output_blob=output_blob,
            archive_bucket=archive_bucket,
            archive_blob=archive_blob,
            layer_name=layer_name,
            display_name=display_name,
            verbose=verbose,
            keep_temp=keep_temp,
            # Use -r1 to keep points at every zoom
            tippecanoe_options=["-r1"],
        )

        return run_vector_pmtiles_pipeline(
            config,
            read_source=partial(
                read_marine_habitat,
                layer_name=layer_name,
                habitat=habitat,
                params=params,
                fallback_area_km2=fallback_area_km2,
                verbose=verbose,
            ),
        )
    except Exception as e:
        logger.error(
            {
                "message": f"Error creating and updating {display_name} tileset",
                "error": str(e),
            }
        )
        retry_cfg = METHOD_RETRY_CONFIGS.get(method)
        if retry_cfg:
            raise ScheduleRetry(
                delay_seconds=retry_cfg["delay_seconds"],
                max_retries=retry_cfg["max_retries"],
                message=f"{display_name} tileset update failed: {e}",
            ) from e
        raise


def read_marine_habitat(
    bucket: str,
    source_file: str,
    *,
    layer_name: str,
    habitat: str,
    params: dict,
    fallback_area_km2: float,
    verbose: bool,
) -> gpd.GeoDataFrame | dict[str, gpd.GeoDataFrame]:
    """Read a marine habitat source (same as habitat statistics),
    including UNEP-WCMC point records buffered into circles.

    A UNEP-WCMC source also gets a {layer_name}_points layer of the point records'
    locations, since their buffered circles are too small to see when zoomed out.
    """
    gdf = _load_habitat_geometry(habitat, params, bucket, fallback_area_km2, verbose)
    gdf = _simplify_habitat_geometry(gdf, "EPSG:4326", TOLERANCE)
    polygons = gdf[["geometry"]]

    if params["source"] != "wcmc":
        return polygons

    file_name = params["file_name"]
    point_layer, _ = _find_unep_layer_paths(bucket, file_name)
    points = load_zipped_shapefile_from_gcs(file_name, bucket, internal_shapefile_path=point_layer)
    points = points.to_crs("EPSG:4326").explode(index_parts=False, ignore_index=True)
    points = points[points.geometry.notna() & ~points.geometry.is_empty]

    return {layer_name: polygons, f"{layer_name}_points": points[["geometry"]]}
