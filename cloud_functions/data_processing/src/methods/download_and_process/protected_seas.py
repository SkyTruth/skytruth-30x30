import pandas as pd
import requests

from src.core.commons import retry_and_alert
from src.core.params import (
    ARCHIVE_PROTECTED_SEAS_FILE_NAME,
    BUCKET,
    PROJECT,
    PROTECTED_SEAS_FILE_NAME,
    PROTECTED_SEAS_SITES_FILE_NAME,
    PROTECTED_SEAS_URL,
)
from src.methods.protected_seas import update_protected_seas_data
from src.utils.gcp import duplicate_blob, upload_dataframe
from src.utils.logger import Logger

logger = Logger()


def download_protected_seas(
    url: str = PROTECTED_SEAS_URL,
    bucket: str = BUCKET,
    filename: str = PROTECTED_SEAS_FILE_NAME,
    archive_filename: str = ARCHIVE_PROTECTED_SEAS_FILE_NAME,
    sites_file_name=PROTECTED_SEAS_SITES_FILE_NAME,
    project: str = PROJECT,
    verbose: bool = True,
) -> None:
    """
    Downloads Protected Seas data from the provided URL, processes it into a DataFrame,
    and uploads both a current version and an archived version to Google Cloud Storage.

    Parameters:
    ----------
    url : str
        The URL to fetch the Protected Seas data from.
    bucket : str
        GCS bucket name where the data will be saved.
    filename : str
        Blob name for the current, active version of the data.
    archive_filename : str
        Blob name for the archived version of the data.
    sites_file_name : str
        Blob name of the site geometries updated after the download.
    project : str
        Google Cloud project ID used for authentication during upload.
    verbose : bool, optional
        If True, prints progress and status messages. Default is True.
    """

    def download_from_url(url):
        response = requests.get(url)
        response.raise_for_status()

        data = pd.DataFrame(response.json())

        data["includes_multi_jurisdictional_areas"] = data[
            "includes_multi_jurisdictional_areas"
        ].map({"t": True, "f": False})
        return data.drop_duplicates()

    data = retry_and_alert(
        download_from_url, url, alert_message=f"failed to download Protected Seas from {url}"
    )

    if verbose:
        logger.info({"message": f"saving Protected Seas to gs://{bucket}/{archive_filename}"})
    upload_dataframe(bucket, data, archive_filename, project_id=project, verbose=verbose)
    duplicate_blob(bucket, archive_filename, filename, verbose=True)

    if verbose:
        logger.info({"message": "updating Protected Seas site geometries"})
    update_protected_seas_data(
        sites_file_name=sites_file_name,
        bucket=bucket,
        project=project,
        verbose=verbose,
    )
