from src.core.params import (
    BUCKET,
    CHUNK_SIZE,
    EEZ_PARAMS_200NM,
    MARINE_REGIONS_BODY,
    MARINE_REGIONS_HEADERS,
    MARINE_REGIONS_URL,
)
from src.utils.gcp import download_zip_to_gcs


def download_eez(verbose=True):
    """
    # This section creates an EEZ for Bouvet Island (BVT). Because the BVT EEZ is a 24 nm eez, 
    # it is missing from the standard 200nm eez definitions.
    # Downloads the three EEZs (200 nm, 24 nm, and 12 nm) from a specified UR
    # Extracts the BVT EEZ
    # Merge the BVT EEZ with the other 200nm EEZ data
    # Rerun all data processing jobs that use EEZ data

    # Parameters:
    # ----------
    """
    download_zip_to_gcs(
        url=MARINE_REGIONS_URL,
        bucket_name=BUCKET,
        blob_name=EEZ_PARAMS_200NM["zipfile_name"],
        data=MARINE_REGIONS_BODY,
        params=EEZ_PARAMS_200NM,
        headers=MARINE_REGIONS_HEADERS,
        chunk_size=CHUNK_SIZE,
        verbose=verbose,
    )
