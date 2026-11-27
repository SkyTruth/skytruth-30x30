import pandas as pd

from src.core.commons import add_tolerance_suffix, load_regions
from src.core.params import (
    BUCKET,
    COUNTRY_TERRESTRIAL_HABITATS_FILE_NAME,
    GADM_EEZ_UNION_FILE_NAME,
    HABITAT_PROTECTION_FILE_NAME,
    PA_TERRESTRIAL_HABITATS_FILE_NAME,
    PROJECT,
    TOLERANCE,
    WDPA_MARINE_FILE_NAME,
)
from src.core.processors import rename_habitats
from src.methods.marine_habitats import process_marine_habitats
from src.methods.terrestrial_habitats import process_terrestrial_habitats
from src.utils.gcp import upload_dataframe
from src.utils.logger import Logger

logger = Logger()


def generate_habitat_protection_table(
    gadm_eez_union_file_name: str = GADM_EEZ_UNION_FILE_NAME,
    pa_stats_filename: str = PA_TERRESTRIAL_HABITATS_FILE_NAME,
    country_stats_filename: str = COUNTRY_TERRESTRIAL_HABITATS_FILE_NAME,
    marine_pa_file_name: str = WDPA_MARINE_FILE_NAME,
    file_name_out: str = HABITAT_PROTECTION_FILE_NAME,
    bucket: str = BUCKET,
    project: str = PROJECT,
    tolerance: float = TOLERANCE,
    verbose: bool = True,
):
    marine_pa_file_name = add_tolerance_suffix(marine_pa_file_name, tolerance)

    # TODO: check if we should return zero values for total_area. Right now we are not.

    if verbose:
        logger.info({"message": "loading regions"})
    combined_regions, _ = load_regions()

    marine_habitats = process_marine_habitats(
        combined_regions,
        gadm_eez_union_file_name=gadm_eez_union_file_name,
        marine_pa_file_name=marine_pa_file_name,
        bucket=bucket,
        tolerance=tolerance,
        verbose=verbose,
    )

    terrestrial_habitats = process_terrestrial_habitats(
        combined_regions,
        pa_stats_filename=pa_stats_filename,
        country_stats_filename=country_stats_filename,
        bucket=bucket,
        verbose=verbose,
    )

    habitats = pd.concat((marine_habitats, terrestrial_habitats), axis=0)

    habitats = habitats[habitats["total_area"] > 0].pipe(rename_habitats)

    upload_dataframe(bucket, habitats, file_name_out, project_id=project, verbose=True)

    return habitats.to_dict(orient="records")
