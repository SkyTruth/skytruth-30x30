from google.cloud import storage
import geopandas as gpd
import fsspec
from io import BytesIO
import requests
from tqdm import tqdm
import os
from google.api_core.retry import Retry

PROJECT = os.getenv("PROJECT", "")


class TqdmBytesIO(BytesIO):
    def __init__(self, data, total_size, chunk_size):
        super().__init__(data)
        self.tqdm_bar = tqdm(
            total=total_size, unit="B", unit_scale=True, desc="Uploading", leave=True
        )
        self.chunk_size = chunk_size

    def read(self, n=-1):
        chunk = super().read(n)
        self.tqdm_bar.update(len(chunk))
        return chunk

    def close(self):
        self.tqdm_bar.close()
        super().close()


def save_file_bucket(data, content_type, blob_name, bucket_name, verbose=True, chunk_size_mb=5):
    """
    Uploads a binary file (BytesIO) to GCS using chunked (resumable) upload with a progress bar.
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
            (
                f"Uploading {total_size/1e6:.2f} MB to gs://{bucket_name}/{blob_name} "
                f"in {chunk_size_mb} MB chunks..."
            )
        )

    blob.upload_from_file(
        file_obj=file_obj, content_type=content_type, timeout=600, retry=retry, rewind=True
    )

    file_obj.close()

    if verbose:
        print("Upload complete.")


def duplicate_blob(bucket_name, filename_in, filename_out, verbose=True):
    """
    Duplicate a GCS object by copying it within the same bucket.

    Parameters:
        bucket_name (str): Name of the GCS bucket.
        filename_in (str): Source blob name (path to existing file).
        filename_out (str): Destination blob name (path for the new file).
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    source_blob = bucket.blob(filename_in)
    bucket.copy_blob(source_blob, bucket, new_name=filename_out)

    if verbose:
        print(f"File copied from {filename_in} to {filename_out} in bucket {bucket_name}")


def download_zip_to_gcs(
    url, bucket_name, blob_name, data=None, params=None, headers=None, chunk_size=8192, verbose=True
):
    """
    Downloads a ZIP file from a URL and uploads it directly to GCS.

    Parameters:
        url (str): The URL of the ZIP file.
        bucket_name (str): GCS bucket name.
        blob_name (str): Path within the bucket to store the file.
        chunk_size (int): Size of each streamed chunk (default 8 KB).
    """
    # Start HTTP download stream
    if verbose:
        print(f"getting data from {url}")
    if data is not None:
        response = requests.post(
            url, params=params, data=data, headers=headers, allow_redirects=True
        )
    else:
        response = requests.get(url, stream=True)
    response.raise_for_status()

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


def upload_dataframe(bucket_name, df, destination_blob_name, project_id=PROJECT, verbose=True):
    """Uploads a dataframe to the bucket."""

    client = storage.Client(project=project_id)
    bucket = client.get_bucket(bucket_name)
    if verbose:
        print(f"Uploading dataframe to {destination_blob_name}.")
    bucket.blob(destination_blob_name).upload_from_string(df.to_csv(index=None), "csv")


def load_zipped_shapefile_from_gcs(filename: str, bucket: str) -> gpd.GeoDataFrame:
    """
    Loads a zipped shapefile from GCS into a GeoDataFrame.
    """
    gcs_zip_path = f"gs://{bucket}/{filename}"
    with fsspec.open(gcs_zip_path, mode="rb") as f:
        gdf = gpd.read_file(f)
    return gdf
