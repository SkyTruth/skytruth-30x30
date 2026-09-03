"""Save the (protected area, IHO sea area) intersections the pipeline reads.

The coverage and protection level stats, the protected areas table, the mangrove
and coral habitat stats and the Conservation Builder layers each ran their own
spatial join against the IHO layer. They are joined once here and saved for
those jobs to read instead.

The near-shore file uses the buffered seas, which stand in for the land/sea
union that exists for countries but not for sea areas.
"""

import pandas as pd

from src.core.commons import (
    add_tolerance_suffix,
    intersect_mpatlas_with_iho,
    intersect_wdpa_with_iho,
)
from src.core.params import (
    BUCKET,
    MARINE_TOLERANCE,
    MPATLAS_IHO_FILE_NAME,
    WDPA_IHO_FILE_NAME,
    WDPA_MARINE_FILE_NAME,
    WDPA_NEAR_SHORE_IHO_FILE_NAME,
    WDPA_TERRESTRIAL_FILE_NAME,
)
from src.utils.gcp import upload_gdf
from src.utils.logger import Logger

logger = Logger()

WDPA_ENVIRONMENTS = (
    ("marine", WDPA_MARINE_FILE_NAME),
    ("terrestrial", WDPA_TERRESTRIAL_FILE_NAME),
)


def generate_iho_pa_intersections(
    tolerance: float = MARINE_TOLERANCE,
    bucket: str = BUCKET,
    verbose: bool = True,
) -> None:
    """Join every protected area dataset to the IHO sea areas and save the pairs."""

    def wdpa_pairs(buffer):
        """Marine and terrestrial PAs, labelled, so a consumer can take either or both."""
        return pd.concat(
            [
                intersect_wdpa_with_iho(
                    bucket=bucket,
                    tolerance=tolerance,
                    pa_file_name=pa_file_name,
                    buffer=buffer,
                    with_geometry=True,
                ).assign(environment=environment)
                for environment, pa_file_name in WDPA_ENVIRONMENTS
            ],
            ignore_index=True,
        )

    def save(pairs, file_name):
        if verbose:
            logger.info({"message": f"saving {len(pairs)} pair(s) to gs://{bucket}/{file_name}"})
        upload_gdf(bucket_name=bucket, gdf=pairs, destination_blob_name=file_name, verbose=verbose)

    # The WDPA names take a tolerance because the PAs they were built from were
    # simplified to it. MPAtlas is read as published, so its name does not.
    save(wdpa_pairs(buffer=False), add_tolerance_suffix(WDPA_IHO_FILE_NAME, tolerance))
    save(wdpa_pairs(buffer=True), add_tolerance_suffix(WDPA_NEAR_SHORE_IHO_FILE_NAME, tolerance))
    save(intersect_mpatlas_with_iho(bucket=bucket, with_geometry=True), MPATLAS_IHO_FILE_NAME)
