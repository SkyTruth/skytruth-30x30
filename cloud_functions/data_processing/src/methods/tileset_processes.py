import tempfile
from collections.abc import Callable
from dataclasses import dataclass
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
    MAPBOX_TOKEN,
    MAPBOX_USER,
    MARINE_REGIONS_TILESET_FILE,
    MARINE_REGIONS_TILESET_ID,
    MARINE_REGIONS_TILESET_NAME,
)
from src.core.map_processors import generate_mbtiles, upload_to_mapbox
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
from src.utils.gcp import read_dataframe, read_json_df, read_json_from_gcs, upload_file_to_gcs
from src.utils.logger import Logger

logger = Logger()


@dataclass
class TilesetConfig:
    bucket: str
    tileset_blob_name: str
    tileset_id: str
    display_name: str
    mapbox_username: str
    mapbox_token: str
    local_geojson_name: str
    source_file: str
    local_mbtiles_name: str = "tiles.mbtiles"
    verbose: bool = False
    keep_temp: bool = False
    extra: dict[str, Any] = None


Hook = Callable[[Path, dict[str, Any]], None]


def _check_mapbox_credentials():
    if not MAPBOX_USER or not MAPBOX_TOKEN:
        raise ValueError("MAPBOX_USERNAME and MAPBOX_TOKEN environment variables must be set")


def _generate_mbtiles(temp_dir: Path, ctx: dict[str, Any]):
    generate_mbtiles(
        input_file=str(temp_dir / ctx["local_geojson"]),
        output_file=str(temp_dir / ctx["local_mbtiles"]),
        verbose=ctx["verbose"],
    )


def _upload_gcs(temp_dir: Path, ctx: dict[str, Any]):
    upload_file_to_gcs(
        bucket=ctx["bucket"],
        file_name=str(temp_dir / ctx["local_mbtiles"]),
        blob_name=ctx["tileset_blob_name"],
    )


def _upload_mapbox(temp_dir: Path, ctx: dict[str, Any]):
    upload_to_mapbox(
        source=str(temp_dir / ctx["local_mbtiles"]),
        tileset_id=ctx["tileset_id"],
        display_name=ctx["display_name"],
        username=ctx["mapbox_username"],
        token=ctx["mapbox_token"],
        verbose=ctx["verbose"],
    )


def run_tileset_pipeline(
    cfg: TilesetConfig,
    *,
    process: Hook | None = None,
    check_credentials: Callable = _check_mapbox_credentials,
    build_mbtiles: Hook = _generate_mbtiles,
    upload_gcs: Hook = _upload_gcs,
    upload_mapbox: Hook = _upload_mapbox,
) -> dict[str, Any]:
    ctx: dict[str, Any] = {
        "bucket": cfg.bucket,
        "tileset_blob_name": cfg.tileset_blob_name,
        "tileset_id": cfg.tileset_id,
        "display_name": cfg.display_name,
        "mapbox_username": cfg.mapbox_username,
        "mapbox_token": cfg.mapbox_token,
        "local_geojson": cfg.local_geojson_name,
        "local_mbtiles": cfg.local_mbtiles_name,
        "source_file": cfg.source_file,
        "verbose": cfg.verbose,
    }
    if cfg.extra:
        ctx.update(cfg.extra)

    try:
        check_credentials()
        if cfg.verbose:
            print(f"Starting {ctx['display_name']} tileset pipeline...")

        temp_mgr = tempfile.TemporaryDirectory()
        temp_dir = Path(temp_mgr.__enter__())

        try:
            if process:
                if cfg.verbose:
                    print(f"Processing {ctx['display_name']}...")
                process(temp_dir, ctx)

            geojson_path = temp_dir / ctx["local_geojson"]
            if not geojson_path.exists():
                raise FileNotFoundError(f"Expected GeoJSON not found: {geojson_path}")

            if cfg.verbose:
                print(f"Generating {ctx['display_name']} MBTiles...")
            build_mbtiles(temp_dir, ctx)

            mbtiles_path = temp_dir / ctx["local_mbtiles"]
            if not mbtiles_path.exists():
                raise FileNotFoundError(f"Expected MBTiles not found: {mbtiles_path}")

            if cfg.verbose:
                print(
                    f"Uploading {ctx['display_name']} tileset to GCS {ctx['tileset_blob_name']}..."
                )
            upload_gcs(temp_dir, ctx)

            if cfg.verbose:
                print(f"Uploading {ctx['display_name']} tileset to Mapbox...")
            upload_mapbox(temp_dir, ctx)

            return {
                "temp_dir": str(temp_dir if cfg.keep_temp else None),
                "geojson_path": str(geojson_path),
                "mbtiles_path": str(mbtiles_path),
                "gcs_blob": cfg.tileset_blob_name,
                "tileset_id": cfg.tileset_id,
            }

        finally:
            if not cfg.keep_temp:
                temp_mgr.__exit__(None, None, None)
            else:
                if cfg.verbose:
                    print(f"Preserving temp dir at {temp_dir}")

    except Exception as ex:
        logger.error(
            {"message": f"Tileset pipeline failed for {ctx['display_name']}", "error": str(ex)}
        )
        raise


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
            mapbox_username=MAPBOX_USER,
            mapbox_token=MAPBOX_TOKEN,
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
        raise


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
            mapbox_username=MAPBOX_USER,
            mapbox_token=MAPBOX_TOKEN,
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
        raise


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
            mapbox_username=MAPBOX_USER,
            mapbox_token=MAPBOX_TOKEN,
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
        raise


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

    print(gadm_gdf.head(15), gadm_gdf.columns)

    gadm_gdf = gadm_gdf.pipe(add_translations, translations_df, "location", "code").drop(
        columns="code"
    )
    print(gadm_gdf.head(15), gadm_gdf.columns)
    gadm_gdf["geometry"] = gadm_gdf["geometry"].make_valid()
    geojson_local = temp_dir / ctx["local_geojson"]
    gadm_gdf.to_file(geojson_local, driver="GeoJSON")
