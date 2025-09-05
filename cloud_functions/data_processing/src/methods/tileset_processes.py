from pathlib import Path
from typing import Any

import pandas as pd

from src.core.map_params import (
    COUNTRIES_TILESET_FILE,
    COUNTRIES_TILESET_ID,
    COUNTRIES_TILESET_NAME,
    COUNTRIES_TOLERANCE,
    EEZ_TILESET_FILE,
    EEZ_TILESET_ID,
    EEZ_TILESET_NAME,
    EEZ_TOLERANCE,
    MARINE_REGIONS_TILESET_FILE,
    MARINE_REGIONS_TILESET_ID,
    MARINE_REGIONS_TILESET_NAME,
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
    REGIONS_FILE_NAME,
    RELATED_COUNTRIES_FILE_NAME,
)
from src.core.processors import add_translations
from src.utils.gcp import read_dataframe, read_json_df, read_json_from_gcs
from src.utils.logger import Logger
from src.utils.mbtile_pipeline import TilesetConfig, run_tileset_pipeline

logger = Logger()


def eez_process(temp_dir: Path, ctx: dict[str, Any]):
    verbose = ctx["verbose"]
    bucket = ctx["bucket"]
    source_file: str = ctx["source_file"]
    tolerance: int | str = ctx["tolerance"]

    if verbose:
        print("Downloading source EEZ file from GCS...")

    input_file = source_file.replace(".geojson", f"_{tolerance}.geojson")
    eez_df = read_json_df(bucket, input_file, verbose=verbose)
    eez_df.drop(columns=["MRGID", "AREA_KM2"], errors="ignore", inplace=True)
    eez_df["geometry"] = eez_df["geometry"].make_valid()
    geojson_local = temp_dir / ctx["local_geojson"]
    eez_df.to_file(geojson_local, driver="GeoJSON")


def create_and_update_eez_tileset(
    bucket: str = BUCKET,
    source_file: str = EEZ_MULTIPLE_SOV_FILE_NAME,
    tileset_file: str = EEZ_TILESET_FILE,
    verbose: bool = False,
    *,
    keep_temp: bool = False,
):
    try:
        if verbose:
            print("Creating and updating EEZ tileset...")

        cfg = TilesetConfig(
            bucket=bucket,
            tileset_blob_name=tileset_file,
            tileset_id=EEZ_TILESET_ID,
            display_name=EEZ_TILESET_NAME,
            local_geojson_name="eez.geojson",
            local_mbtiles_name=f"{EEZ_TILESET_ID}.mbtiles",
            source_file=source_file,
            verbose=verbose,
            keep_temp=keep_temp,
            extra={
                "tolerance": EEZ_TOLERANCE,
            },
        )

        return run_tileset_pipeline(cfg, process=eez_process)

    except Exception as excep:
        logger.error({"message": "Error creating and updating EEZ tileset", "error": str(excep)})
        raise excep


def create_and_update_marine_regions_tileset(
    bucket: str = BUCKET,
    source_file: str = EEZ_FILE_NAME,
    tileset_file: str = MARINE_REGIONS_TILESET_FILE,
    tileset_id: str = MARINE_REGIONS_TILESET_ID,
    display_name: str = MARINE_REGIONS_TILESET_NAME,
    verbose: bool = False,
    *,
    keep_temp: bool = False,
):
    try:
        if verbose:
            print("Creating and updating EEZ tileset...")

        cfg = TilesetConfig(
            bucket=bucket,
            tileset_blob_name=tileset_file,
            tileset_id=tileset_id,
            display_name=display_name,
            local_geojson_name="marine_regions.geojson",
            local_mbtiles_name=f"{tileset_id}.mbtiles",
            source_file=source_file,
            verbose=verbose,
            keep_temp=keep_temp,
            extra={
                "tolerance": EEZ_TOLERANCE,
                "translation_file": LOCATIONS_TRANSLATED_FILE_NAME,
                "regions_file": REGIONS_FILE_NAME,
            },
        )

        return run_tileset_pipeline(cfg, process=marine_regions_process)
    except Exception as excep:
        logger.error(
            {"message": "Error creating and updating Marine Region tileset", "error": str(excep)}
        )
        raise excep


def marine_regions_process(temp_dir: Path, ctx: dict[str, Any]):
    verbose = ctx["verbose"]
    bucket = ctx["bucket"]
    source_file: str = ctx["source_file"]
    tolerance: int | str = ctx["tolerance"]
    translation_file: str = ctx["translation_file"]
    regions_file: str = ctx["regions_file"]

    if verbose:
        print("Downloading source Marine Regions file from GCS...")

    input_file = source_file.replace(".geojson", f"_{tolerance}.geojson")
    eez_df = read_json_df(bucket, input_file, verbose=verbose)

    translations_df = read_dataframe(bucket, translation_file, verbose=verbose)
    regions = read_json_from_gcs(bucket, regions_file, verbose)

    iso_to_region = {iso: region_id for region_id, iso_list in regions.items() for iso in iso_list}

    eez_df["region_id"] = eez_df["location"].map(iso_to_region)
    region_gdf = (
        eez_df.dissolve(by="region_id", as_index=False)
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

    region_gdf["geometry"] = region_gdf["geometry"].make_valid()
    geojson_local = temp_dir / ctx["local_geojson"]
    region_gdf.to_file(geojson_local, driver="GeoJSON")


def create_and_update_country_tileset(
    bucket: str = BUCKET,
    source_file: str = GADM_FILE_NAME,
    tileset_file: str = COUNTRIES_TILESET_FILE,
    tileset_id: str = COUNTRIES_TILESET_ID,
    display_name: str = COUNTRIES_TILESET_NAME,
    verbose: bool = False,
    *,
    keep_temp: bool = False,
):
    try:
        if verbose:
            print("Creating and updating Country tileset...")

        cfg = TilesetConfig(
            bucket=bucket,
            tileset_blob_name=tileset_file,
            tileset_id=tileset_id,
            display_name=display_name,
            local_geojson_name="countries.geojson",
            local_mbtiles_name=f"{tileset_id}.mbtiles",
            source_file=source_file,
            verbose=verbose,
            keep_temp=keep_temp,
            extra={
                "tolerance": COUNTRIES_TOLERANCE,
                "translation_file": LOCATIONS_TRANSLATED_FILE_NAME,
                "related_countries_file": RELATED_COUNTRIES_FILE_NAME,
            },
        )

        return run_tileset_pipeline(cfg, process=countries_process)
    except Exception as excep:
        logger.error(
            {"message": "Error creating and updating Countries tileset", "error": str(excep)}
        )
        raise excep


def countries_process(temp_dir: Path, ctx: dict[str, Any]):
    verbose = ctx["verbose"]
    bucket = ctx["bucket"]
    source_file: str = ctx["source_file"]
    related_countries_file: str = ctx["related_countries_file"]
    tolerance: int | str = ctx["tolerance"]
    translation_file: str = ctx["translation_file"]

    if verbose:
        print("Downloading source GADM file from GCS...")

    input_file = source_file.replace(".geojson", f"_{tolerance}.geojson")
    gadm_gdf = read_json_df(bucket, input_file, verbose=verbose)

    translations_df = read_dataframe(bucket, translation_file, verbose=verbose)
    related_countries = read_json_from_gcs(bucket, related_countries_file, verbose)

    country_to_sov = {}

    for iso_sov, iso_list in related_countries.items():
        if iso_sov.endswith("*"):
            for iso in iso_list:
                country_to_sov.setdefault(iso, []).append(iso_sov)

    sovs = gadm_gdf["location"].map(lambda loc: country_to_sov.get(loc, []))

    # Map sovereigns to country
    for idx in range(3):
        gadm_gdf[f"ISO_SOV{idx + 1}"] = sovs.map(
            lambda sov, idx=idx: sov[idx] if idx < len(sov) else pd.NA
        ).astype("string")

    gadm_gdf = gadm_gdf.pipe(add_translations, translations_df, "location", "code").drop(
        columns="code"
    )

    gadm_gdf["geometry"] = gadm_gdf["geometry"].make_valid()
    geojson_local = temp_dir / ctx["local_geojson"]
    gadm_gdf.to_file(geojson_local, driver="GeoJSON")


def create_and_update_terrestrial_regions_tileset(
    bucket: str = BUCKET,
    source_file: str = GADM_FILE_NAME,
    tileset_file: str = TERRESTRIAL_REGIONS_TILESET_FILE,
    tileset_id: str = TERRESTRIAL_REGIONS_TILESET_ID,
    display_name: str = TERRESTRIAL_REGIONS_TILESET_NAME,
    verbose: bool = False,
    *,
    keep_temp: bool = False,
):
    try:
        if verbose:
            print("Creating and updating Terrestrial Regions tileset...")

        cfg = TilesetConfig(
            bucket=bucket,
            tileset_blob_name=tileset_file,
            tileset_id=tileset_id,
            display_name=display_name,
            local_geojson_name="terrestrial_regions.geojson",
            local_mbtiles_name=f"{tileset_id}.mbtiles",
            source_file=source_file,
            verbose=verbose,
            keep_temp=keep_temp,
            extra={
                "tolerance": COUNTRIES_TOLERANCE,
                "translation_file": LOCATIONS_TRANSLATED_FILE_NAME,
                "regions_file": REGIONS_FILE_NAME,
            },
        )

        return run_tileset_pipeline(cfg, process=terrestrial_regions_process)
    except Exception as excep:
        logger.error(
            {
                "message": "Error creating and updating Terrestrial Regions tileset",
                "error": str(excep),
            }
        )
        raise excep


def terrestrial_regions_process(temp_dir: Path, ctx: dict[str, Any]):
    verbose = ctx["verbose"]
    bucket = ctx["bucket"]
    source_file: str = ctx["source_file"]
    regions_file: str = ctx["regions_file"]
    tolerance: int | str = ctx["tolerance"]
    translation_file: str = ctx["translation_file"]

    if verbose:
        print("Downloading source GADM file from GCS...")

    input_file = source_file.replace(".geojson", f"_{tolerance}.geojson")
    gadm_gdf = read_json_df(bucket, input_file, verbose=verbose)

    translations_df = read_dataframe(bucket, translation_file, verbose=verbose)
    regions = read_json_from_gcs(bucket, regions_file, verbose)

    iso_to_region = {iso: region_id for region_id, iso_list in regions.items() for iso in iso_list}

    gadm_gdf["region_id"] = gadm_gdf["location"].map(iso_to_region)
    region_gdf = (
        gadm_gdf.dissolve(by="region_id", as_index=False)
        .drop(
            columns=[
                "location",
            ],
        )
        .pipe(add_translations, translations_df, "region_id", "code")
        .drop(columns="code")
        .dropna(subset=["region_id"])
    )

    region_gdf["geometry"] = region_gdf["geometry"].make_valid()
    geojson_local = temp_dir / ctx["local_geojson"]
    region_gdf.to_file(geojson_local, driver="GeoJSON")


def create_and_update_protected_area_tileset(
    bucket: str,
    source_file: str,
    tileset_file: str,
    tileset_id: str,
    display_name: str,
    tolerance: float,
    verbose: bool = False,
    *,
    keep_temp: bool = False,
):
    try:
        if verbose:
            print(f"Creating and updating {display_name} tileset...")

        cfg = TilesetConfig(
            bucket=bucket,
            tileset_blob_name=tileset_file,
            tileset_id=tileset_id,
            display_name=display_name,
            local_geojson_name="terrestrial_regions.geojson",
            local_mbtiles_name=f"{tileset_id}.mbtiles",
            source_file=source_file,
            verbose=verbose,
            keep_temp=keep_temp,
            extra={
                "tolerance": COUNTRIES_TOLERANCE,
            },
        )

        return run_tileset_pipeline(
            cfg,
            process=protected_area_process,
            upload_mapbox=lambda a, b: print("MAPBOXING..."),
        )
    except Exception as excep:
        logger.error(
            {
                "message": "Error creating and updating Terrestrial Regions tileset",
                "error": str(excep),
            }
        )
        raise excep


def protected_area_process(temp_dir: Path, ctx: dict[str, Any]):
    verbose = ctx["verbose"]
    bucket = ctx["bucket"]
    source_file: str = ctx["source_file"]
    regions_file: str = ctx["regions_file"]
    tolerance: int | str = ctx["tolerance"]
    translation_file: str = ctx["translation_file"]

    if verbose:
        print("Downloading source GADM file from GCS...")

    input_file = source_file.replace(".geojson", f"_{tolerance}.geojson")
    gadm_gdf = read_json_df(bucket, input_file, verbose=verbose)

    translations_df = read_dataframe(bucket, translation_file, verbose=verbose)
    regions = read_json_from_gcs(bucket, regions_file, verbose)

    iso_to_region = {iso: region_id for region_id, iso_list in regions.items() for iso in iso_list}

    gadm_gdf["region_id"] = gadm_gdf["location"].map(iso_to_region)
    region_gdf = (
        gadm_gdf.dissolve(by="region_id", as_index=False)
        .drop(
            columns=[
                "location",
            ],
        )
        .pipe(add_translations, translations_df, "region_id", "code")
        .drop(columns="code")
        .dropna(subset=["region_id"])
    )

    region_gdf["geometry"] = region_gdf["geometry"].make_valid()
    geojson_local = temp_dir / ctx["local_geojson"]
    region_gdf.to_file(geojson_local, driver="GeoJSON")
