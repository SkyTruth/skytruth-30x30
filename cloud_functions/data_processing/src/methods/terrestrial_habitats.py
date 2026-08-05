import pandas as pd
import requests

from src.core.commons import add_tolerance_suffix
from src.core.land_cover_params import LAND_COVER_CLASSES, terrestrial_tolerance
from src.core.params import (
    BUCKET,
    COUNTRY_TERRESTRIAL_HABITATS_FILE_NAME,
    GADM_FILE_NAME,
    PA_TERRESTRIAL_HABITATS_FILE_NAME,
    PROCESSED_BIOME_RASTER_PATH,
    PROJECT,
    WDPA_TERRESTRIAL_FILE_NAME,
)
from src.core.raster_pa_stats import compute_class_areas_by_location
from src.utils.gcp import download_file_from_gcs, read_dataframe, read_json_df, upload_dataframe
from src.utils.logger import Logger

logger = Logger()


def download_file(url, destination):
    response = requests.get(url, stream=True)
    response.raise_for_status()

    with open(destination, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)


def generate_terrestrial_biome_stats_pa(
    land_cover_classes: dict = LAND_COVER_CLASSES,
    pa_stats_filename: str = PA_TERRESTRIAL_HABITATS_FILE_NAME,
    raster_path: str = PROCESSED_BIOME_RASTER_PATH,
    gadm_file_name: str = GADM_FILE_NAME,
    terrestrial_pa_file_name: str = WDPA_TERRESTRIAL_FILE_NAME,
    bucket: str = BUCKET,
    project: str = PROJECT,
    country_col="ISO3",
    tile_size_pixels=8192,
    verbose: bool = True,
    tolerance: float = terrestrial_tolerance,
):
    terrestrial_pa_file_name = add_tolerance_suffix(terrestrial_pa_file_name, tolerance)
    gadm_file_name = add_tolerance_suffix(gadm_file_name, tolerance)

    if verbose:
        logger.info({"message": f"loading GADM geometries from {gadm_file_name}"})

    gadm = read_json_df(bucket, gadm_file_name, verbose=verbose)

    if verbose:
        logger.info({"message": "loading protected areas (this may take a few minutes)"})

    terrestrial_pas = read_json_df(bucket, terrestrial_pa_file_name, verbose=verbose)
    terrestrial_pas["geometry"] = terrestrial_pas.make_valid()

    if verbose:
        logger.info({"message": f"downloading raster from {raster_path}"})
    local_raster_path = raster_path.split("/")[-1]
    download_file_from_gcs(bucket, raster_path, local_raster_path, verbose=False)

    if verbose:
        logger.info({"message": "calculating terrestrial habitat area within PAs"})

    pa_stats = compute_class_areas_by_location(
        raster_path=local_raster_path,
        regions_gdf=gadm,
        class_map=land_cover_classes,
        region_col="location",
        polygons_gdf=terrestrial_pas,
        polygon_location_col=country_col,
        tile_size_pixels=tile_size_pixels,
        verbose=verbose,
    )

    class_columns = [column for column in pa_stats.columns if column not in ("location", "total")]
    pa_stats = pa_stats[["location", *class_columns, "total"]]

    # upload PA land cover type areas (km2) per country
    upload_dataframe(
        bucket,
        pa_stats,
        pa_stats_filename,
        project_id=project,
        verbose=verbose,
    )

    return pa_stats


def process_terrestrial_habitats(
    combined_regions,
    pa_stats_filename: str = PA_TERRESTRIAL_HABITATS_FILE_NAME,
    country_stats_filename: str = COUNTRY_TERRESTRIAL_HABITATS_FILE_NAME,
    bucket: str = BUCKET,
    verbose: bool = True,
):
    def get_group_stats(df, loc, relations):
        df_group = df if loc == "GLOB" else df[df["location"].isin(relations[loc])]

        out = df_group[[c for c in df_group.columns if c != "location"]].sum().to_dict()
        out["location"] = loc

        return out

    if verbose:
        logger.info({"message": f"loading country habitat stats from {country_stats_filename}"})
    country_stats = read_dataframe(bucket, country_stats_filename, verbose=verbose)
    country_stats = country_stats.apply(pd.to_numeric, errors="ignore")

    if verbose:
        logger.info({"message": f"loading country habitat stats from {pa_stats_filename}"})
    pa_stats = read_dataframe(bucket, pa_stats_filename, verbose=verbose)
    pa_stats = pa_stats.apply(pd.to_numeric, errors="ignore")

    # wrap up pa stats by sovereign country
    grouped_pa_stats = pd.DataFrame(
        [get_group_stats(pa_stats, reg, combined_regions) for reg in combined_regions]
    )

    # wrap up country stats by sovereign country
    grouped_cnt_stats = pd.DataFrame(
        [get_group_stats(country_stats, reg, combined_regions) for reg in combined_regions]
    )

    # calculate percent land cover within PA of total land cover per country
    cnt = (
        pd.melt(
            grouped_cnt_stats.rename(columns={"total": "total_land_area"}),
            id_vars="location",  # Keep 'location' as identifier
            var_name="habitat",  # Name of the new column for cover type
            value_name="total_area",  # Name of the values column (optional)
        )
        .sort_values(["location", "habitat"])
        .reset_index(drop=True)
    )

    pa = (
        pd.melt(
            grouped_pa_stats.rename(columns={"total": "total_land_area"}),
            id_vars="location",  # Keep 'location' as identifier
            var_name="habitat",  # Name of the new column for cover type
            value_name="protected_area",  # Name of the values column (optional)
        )
        .sort_values(["location", "habitat"])
        .reset_index(drop=True)
    )

    pa["environment"] = "terrestrial"

    terrestrial_habitats = pd.merge(
        pa[["location", "habitat", "environment", "protected_area"]],
        cnt[["location", "habitat", "total_area"]],
        on=["location", "habitat"],
        how="right",
    )

    return terrestrial_habitats
