import os
from io import BytesIO

import fsspec
import geopandas as gpd
import pandas as pd
import requests
from google.api_core.retry import Retry
from google.cloud import storage
from tqdm import tqdm

from src.utils.logger import Logger

PROJECT = os.getenv("PROJECT", "")
logger = Logger()


class TqdmBytesIO(BytesIO):
    """
    A subclass of BytesIO that wraps a tqdm progress bar around read operations.

    This is especially useful when streaming binary data (e.g. to upload to cloud storage)
    and you want to track progress in real-time using tqdm.

    Attributes:
    ----------
    tqdm_bar : tqdm.tqdm
        The progress bar tracking number of bytes read.
    chunk_size : int
        Size of each read chunk, used for progress updates.
    """

    def __init__(self, data: bytes, total_size: int, chunk_size: int):
        super().__init__(data)
        self.tqdm_bar = tqdm(
            total=total_size, unit="B", unit_scale=True, desc="Uploading", leave=True
        )
        self.chunk_size = chunk_size

    def read(self, n: int = -1) -> bytes:
        chunk = super().read(n)
        self.tqdm_bar.update(len(chunk))
        return chunk

    def close(self) -> None:
        self.tqdm_bar.close()
        super().close()


def save_file_bucket(
    data: bytes,
    content_type: str | None,
    blob_name: str,
    bucket_name: str,
    verbose: bool = True,
    chunk_size_mb: int = 5,
) -> None:
    """
    Uploads a binary file to a Google Cloud Storage (GCS) bucket using a resumable upload
    with chunked streaming and a tqdm progress bar.

    Parameters:
    ----------
    data : bytes
        The binary content to upload, typically from a file or HTTP response.
    content_type : str
        The MIME type of the file (e.g., "application/zip", "application/json").
    blob_name : str
        Name of the destination blob in the GCS bucket.
    bucket_name : str
        Name of the GCS bucket to upload the file to.
    verbose : bool, optional
        If True, prints upload status and progress messages. Default is True.
    chunk_size_mb : int, optional
        Size of each upload chunk in megabytes. Must be a multiple of 256 KB.
        Default is 5 MB.
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    # Set chunk size (must be multiple of 256 KB)
    chunk_size = chunk_size_mb * 1024 * 1024
    blob.chunk_size = chunk_size

    retry = Retry(initial=1.0, maximum=60.0, multiplier=2.0, deadline=600.0)

    total_size = len(data)
    file_obj = TqdmBytesIO(data, total_size, chunk_size)

    if verbose:
        print(
            f"Uploading {total_size / 1e6:.2f} MB to gs://{bucket_name}/{blob_name} "
            f"in {chunk_size_mb} MB chunks..."
        )

    blob.upload_from_file(
        file_obj=file_obj, content_type=content_type, timeout=600, retry=retry, rewind=True
    )

    file_obj.close()

    if verbose:
        print("Upload complete.")


def duplicate_blob(
    bucket_name: str, filename_in: str, filename_out: str, verbose: bool = True
) -> None:
    """
    Duplicates a file (blob) within a Google Cloud Storage (GCS) bucket by copying
    an existing object to a new location (name).

    Parameters:
    ----------
    bucket_name : str
        Name of the GCS bucket containing the file.
    filename_in : str
        Name of the existing blob to copy (source).
    filename_out : str
        Name for the new blob (destination).
    verbose : bool, optional
        If True, prints a message confirming the copy. Default is True.
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    source_blob = bucket.blob(filename_in)
    bucket.copy_blob(source_blob, bucket, new_name=filename_out)

    if verbose:
        print(f"File copied from {filename_in} to {filename_out} in bucket {bucket_name}")


def download_zip_to_gcs(
    url: str,
    bucket_name: str,
    blob_name: str,
    data: dict | None = None,
    params: dict | None = None,
    headers: dict | None = None,
    chunk_size: int = 8192,
    verbose: bool = True,
) -> None:
    """
    Downloads a ZIP file from a URL (via GET or POST) and uploads it to Google Cloud Storage
    with a progress bar.

    Parameters:
    ----------
    url : str
        The URL of the ZIP file to download.
    bucket_name : str
        Name of the GCS bucket to upload the file to.
    blob_name : str
        Destination path (blob name) within the GCS bucket.
    data : dict, optional
        Data to include in the POST request body. If `None`, a GET request is used.
    params : dict, optional
        URL query parameters to include in the request.
    headers : dict, optional
        HTTP headers to send with the request.
    chunk_size : int, optional
        Number of bytes to read at a time while streaming. Default is 8192 (8 KB).
    verbose : bool, optional
        If True, prints progress messages. Default is True.
    """
    # Start HTTP download stream
    if verbose:
        print(f"getting data from {url}")

    try:
        if data is not None:
            response = requests.post(
                url, params=params, data=data, headers=headers, allow_redirects=True
            )
        else:
            response = requests.get(url, stream=True)
        response.raise_for_status()
    except requests.HTTPError as excep:
        logger.error({"message": "HTTP error during download", "error": str(excep)})
        raise excep
    except Exception as excep:
        logger.error({"message": "Error during download", "error": str(excep)})
        raise excep

    try:
        total_size = int(response.headers.get("content-length", 0))
        raw_buffer = BytesIO()

        if verbose:
            print("streaming data into buffer")
        for chunk in tqdm(
            response.iter_content(chunk_size=chunk_size),
            total=total_size // chunk_size + 1,
            unit="B",
            unit_scale=True,
            desc="Downloading",
        ):
            raw_buffer.write(chunk)

        raw_buffer.seek(0)

        # Upload to GCS using TqdmBytesIO
        tqdm_buffer = TqdmBytesIO(raw_buffer.read(), total_size=total_size, chunk_size=chunk_size)
        tqdm_buffer.seek(0)

        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        if verbose:
            print(f"Uploading to gs://{bucket_name}/{blob_name}")
        blob.upload_from_file(tqdm_buffer, content_type="application/zip", rewind=True, timeout=600)
        tqdm_buffer.close()
    except Exception as excep:
        logger.error({"message": "Error during upload to GCS", "error": str(excep)})
        raise excep


def upload_dataframe(
    bucket_name: str,
    df: pd.DataFrame,
    destination_blob_name: str,
    project_id: str = PROJECT,
    verbose: bool = True,
) -> None:
    """
    Uploads a pandas DataFrame to a Google Cloud Storage bucket as a CSV file.

    Parameters:
    ----------
    bucket_name : str
        Name of the GCS bucket to upload the file to.
    df : pd.DataFrame
        The pandas DataFrame to upload.
    destination_blob_name : str
        Name of the destination blob (object path) in the GCS bucket.
    project_id : str, optional
        Google Cloud project ID. Defaults to global `PROJECT`.
    verbose : bool, optional
        If True, prints status messages. Default is True.
    """

    client = storage.Client(project=project_id)
    bucket = client.get_bucket(bucket_name)
    if verbose:
        print(f"Uploading dataframe to {destination_blob_name}.")
    bucket.blob(destination_blob_name).upload_from_string(df.to_csv(index=None), "csv")


def load_zipped_shapefile_from_gcs(filename: str, bucket: str) -> gpd.GeoDataFrame:
    """
    Loads a zipped shapefile from a Google Cloud Storage (GCS) bucket into a GeoDataFrame.

    This function assumes that the ZIP file contains a single shapefile with
    consistent base names (e.g., `.shp`, `.shx`, `.dbf`, etc.) and reads it directly
    using fsspec-compatible streaming.

    Parameters:
    ----------
    filename : str
        Name of the ZIP file (blob) in the GCS bucket.
    bucket : str
        Name of the GCS bucket where the ZIP file is stored.

    Returns:
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the shapefile’s features and attributes.
    """

    gcs_zip_path = f"gs://{bucket}/{filename}"
    with fsspec.open(gcs_zip_path, mode="rb") as f:
        gdf = gpd.read_file(f)
    return gdf
