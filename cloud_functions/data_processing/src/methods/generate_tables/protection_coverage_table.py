import pandas as pd

from src.core.params import (
    BUCKET,
    PROJECT,
    PROTECTION_COVERAGE_FILE_NAME,
    WDPA_COUNTRY_LEVEL_FILE_NAME,
    WDPA_GLOBAL_LEVEL_FILE_NAME,
)
from src.methods.protection_coverage import (
    compute_country_global_coverage,
    compute_iho_protection_coverage,
)
from src.utils.gcp import upload_dataframe
from src.utils.logger import Logger

logger = Logger()


def generate_protection_coverage_stats_table(
    bucket: str = BUCKET,
    project: str = PROJECT,
    protection_coverage_file_name: str = PROTECTION_COVERAGE_FILE_NAME,
    wdpa_country_level_file_name: str = WDPA_COUNTRY_LEVEL_FILE_NAME,
    wdpa_global_level_file_name: str = WDPA_GLOBAL_LEVEL_FILE_NAME,
    percent_type: str = "area",  # area or counts
    verbose: bool = True,
):
    country_global_coverage, sov_country_area = compute_country_global_coverage(
        bucket=bucket,
        wdpa_country_level_file_name=wdpa_country_level_file_name,
        wdpa_global_level_file_name=wdpa_global_level_file_name,
        percent_type=percent_type,
        verbose=verbose,
    )

    if verbose:
        logger.info({"message": "computing IHO sea area protection coverage stats"})
    iho_coverage = compute_iho_protection_coverage(
        bucket=bucket,
        wdpa_global_level_file_name=wdpa_global_level_file_name,
        verbose=verbose,
    )

    protection_coverage_table = pd.concat(
        (country_global_coverage, iho_coverage), axis=0, ignore_index=True
    )

    protection_coverage_table["total_area"] = (
        protection_coverage_table["total_area"].round(0).astype("Int64")
    )

    upload_dataframe(
        bucket,
        protection_coverage_table,
        protection_coverage_file_name,
        project_id=project,
        verbose=verbose,
    )

    upload_dataframe(
        bucket,
        sov_country_area,
        "temporary/country_areas.csv",
        project_id=project,
        verbose=verbose,
    )

    return protection_coverage_table.to_dict(orient="records")
