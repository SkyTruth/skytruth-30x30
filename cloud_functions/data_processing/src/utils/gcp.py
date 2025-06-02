import gcsfs
from google.api_core.retry import Retry
from google.cloud import storage
import geopandas as gpd
import fiona
import fsspec
from io import BytesIO
import json
import os
import pandas as pd
from pathlib import Path
import requests
import shutil
import tempfile
from tqdm import tqdm
from typing import Optional
import zipfile

PROJECT = os.getenv("PROJECT", "")


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
        print(f"Uploading dataframe to gs://{bucket_name}/{destination_blob_name}.")
    bucket.blob(destination_blob_name).upload_from_string(df.to_csv(index=None), "csv")


def upload_gdf(
    bucket_name: str,
    gdf: gpd.GeoDataFrame,
    destination_blob_name: str,
    project_id: str = PROJECT,
    verbose: bool = True,
) -> None:
    """
    Saves a GeoDataFrame to GCS as a .geojson file.

    Parameters:
    ----------
    gdf : gpd.GeoDataFrame
        The GeoDataFrame to upload.
    bucket_name : str
        Name of the GCS bucket.
    destination_blob_name : str
        Destination path for the .geojson file in the bucket.
    project_id : str, optional
        Google Cloud project ID. Defaults to global `PROJECT`.
    verbose : bool
        If True, prints progress messages.
    """
    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)

    with tempfile.NamedTemporaryFile(suffix=".geojson") as tmp_file:
        gdf.to_file(tmp_file.name, driver="GeoJSON")

        if verbose:
            print(f"Uploading geodataframe to gs://{bucket_name}/{destination_blob_name}")

        bucket.blob(destination_blob_name).upload_from_filename(tmp_file.name)

    if verbose:
        print("Upload complete.")


def load_zipped_shapefile_from_gcs(filename: str, bucket: str, internal_shapefile_path: str = ""):
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
    internal_shapefile_path : str
        Path to shapefile

    Returns:
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the shapefile’s features and attributes.
    """

    gcs_path = f"gs://{bucket}/{filename}"

    if internal_shapefile_path == "":
        with fsspec.open(gcs_path, mode="rb") as f:
            gdf = gpd.read_file(f)

    else:
        with fsspec.open(gcs_path, mode="rb") as f:
            zip_bytes = f.read()

        with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
            with tempfile.TemporaryDirectory() as tmpdir:
                # Extract only the files associated with the shapefile
                base_path = os.path.dirname(internal_shapefile_path)
                basename = os.path.splitext(os.path.basename(internal_shapefile_path))[0]

                shapefile_parts = [
                    name
                    for name in zf.namelist()
                    if name.startswith(f"{base_path}/{basename}")
                    and name.split(".")[-1].lower() in {"shp", "shx", "dbf", "prj", "cpg"}
                ]

                for part in shapefile_parts:
                    target_path = os.path.join(tmpdir, os.path.basename(part))
                    with zf.open(part) as source, open(target_path, "wb") as target:
                        target.write(source.read())

                local_shp_path = os.path.join(tmpdir, f"{basename}.shp")
                gdf = gpd.read_file(local_shp_path)

    return gdf


def read_zipped_gpkg_from_gcs(
    bucket: str, zip_blob_name: str, chunk_size: int = 8192
) -> gpd.GeoDataFrame:
    """
    Downloads a zipped .gpkg from GCS, extracts it locally, reads the geopackage,
    and returns a GeoDataFrame, with a progress bar during download.

    Parameters:
    ----------
    bucket : str
        The GCS bucket name.
    zip_blob_name : str
        Path to the .zip file in the bucket (e.g., "data/myfile.zip").
    chunk_size : int
        Size of each streamed read chunk (default: 8192 bytes)

    Returns:
    -------
    gpd.GeoDataFrame
    """
    gcs_path = f"gs://{bucket}/{zip_blob_name}"

    with fsspec.open(gcs_path, mode="rb") as remote_file:
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "file.zip")

            # Get total size for progress bar (if available)
            total_size = (
                remote_file.size if hasattr(remote_file, "size") and remote_file.size else 0
            )
            raw_data = remote_file.read()

            tqdm_stream = TqdmBytesIO(raw_data, total_size or len(raw_data), chunk_size)
            with open(zip_path, "wb") as f:
                while True:
                    chunk = tqdm_stream.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
            tqdm_stream.close()

            # Extract and load gpkg
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(tmpdir)

            gpkg_files = [
                os.path.join(tmpdir, f) for f in os.listdir(tmpdir) if f.lower().endswith(".gpkg")
            ]
            if not gpkg_files:
                raise FileNotFoundError("No .gpkg file found in the zip archive.")

            return gpd.read_file(gpkg_files[0])


def read_dataframe(
    bucket_name: str,
    filename: str,
    skip_empty: bool = False,
    skip_empty_val: int = 2,
    keep_default_na=False,
    verbose: bool = False,
) -> Optional[pd.DataFrame]:
    """
    Reads a CSV file from Google Cloud Storage into a pandas DataFrame.

    Parameters
    ----------
    bucket_name : str
        Name of the GCS bucket.
    filename : str
        Path to the CSV file in the bucket.
    skip_empty : bool, optional
        If True, checks the file size before reading and skips files that are empty.
    skip_empty_val : int, optional
        File size threshold in bytes to consider as empty (default is 2).
    verbose : bool, optional
        If True, prints a message when skipping an empty file.

    Returns
    -------
    pd.DataFrame or None
        A DataFrame if the file is non-empty and readable, or None if skipped.
    """

    # must have gcsfs installed to work
    fs = gcsfs.GCSFileSystem()
    fpath = f"gs://{bucket_name}/{filename}"

    if skip_empty:
        # Check the file size before reading (2B is empty)
        file_info = fs.info(fpath)
        if file_info["size"] <= skip_empty_val:
            if verbose:
                print(f"Skipping empty file: {filename}")
            return None
    return pd.read_csv(fpath, low_memory=False, keep_default_na=keep_default_na)


def read_json_df(
    bucket_name: str, filename: str, verbose: bool = True
) -> pd.DataFrame | gpd.GeoDataFrame:
    """
    Reads a .json or .geojson file from GCS and returns a DataFrame or GeoDataFrame.

    Parameters:
    ----------
    bucket_name : str
        Name of the GCS bucket.
    filename : str
        Path to the .json or .geojson file in the bucket.
    verbose : bool
        If True, prints progress messages.

    Returns:
    -------
    pd.DataFrame or gpd.GeoDataFrame
        The loaded data.

    Raises:
    -------
    ValueError
        If the file extension is not .json or .geojson.
    """
    file_type = filename.lower().split(".")[-1]

    if verbose:
        print(f"Loading from gs://{bucket_name}/{filename} (type: {file_type})")

    fs = gcsfs.GCSFileSystem()

    with fs.open(f"gs://{bucket_name}/{filename}", "r") as f:
        if file_type == "geojson":
            return gpd.read_file(f)
        elif file_type == "json":
            raw = json.load(f)
            if isinstance(raw, dict) and "features" in raw:
                return gpd.GeoDataFrame.from_features(raw["features"])
            return pd.DataFrame(raw)
        else:
            raise ValueError(
                f"Unsupported file extension: .{file_type} (expected .json or .geojson)"
            )


def read_json_from_gcs(bucket_name: str, filename: str, verbose: bool = True) -> dict:
    """
    Reads a .json or .geojson file from GCS and returns the raw JSON data as a dictionary.

    Parameters:
    ----------
    bucket_name : str
        GCS bucket name.
    filename : str
        Path to the JSON or GeoJSON file in the bucket.
    verbose : bool
        If True, prints progress messages.

    Returns:
    -------
    dict
        Parsed JSON or GeoJSON content as a Python dictionary.
    """
    fs = gcsfs.GCSFileSystem()
    gcs_path = f"gs://{bucket_name}/{filename}"

    if verbose:
        print(f"Reading JSON from {gcs_path}")

    with fs.open(gcs_path, "r") as f:
        return json.load(f)


def download_zipfile_from_gcs(bucket_name: str, zip_filename: str, verbose: bool = True) -> Path:
    """
    Downloads a ZIP file from GCS into a temporary directory and extracts it,
    with a progress bar during download.

    Parameters:
    ----------
    bucket_name : str
        GCS bucket name.
    zip_filename : str
        Path to the zip file in the bucket.
    verbose : bool
        If True, prints status messages and shows progress bar.

    Returns:
    -------
    Path
        Path to the directory containing extracted zip contents.
    """
    fs = gcsfs.GCSFileSystem()
    gcs_path = f"gs://{bucket_name}/{zip_filename}"

    if verbose:
        print(f"Downloading {gcs_path}...")

    # Create a temp dir to hold zip and extracted files
    temp_dir = Path(tempfile.mkdtemp())
    zip_path = temp_dir / "archive.zip"

    with fs.open(gcs_path, "rb") as f_in, open(zip_path, "wb") as f_out:
        total_size = fs.info(gcs_path)["size"]
        with tqdm(total=total_size, unit="B", unit_scale=True, desc="Downloading zip") as pbar:
            while True:
                chunk = f_in.read(8192)
                if not chunk:
                    break
                f_out.write(chunk)
                pbar.update(len(chunk))

    # Extract
    extract_dir = temp_dir / "unzipped"
    extract_dir.mkdir()
    shutil.unpack_archive(zip_path, extract_dir)

    if verbose:
        print(f"Extracted to: {extract_dir}")

    return extract_dir


def load_gdb_layer_from_gcs(
    zip_filename: str, bucket: str, chunk_size=1024 * 1024
) -> gpd.GeoDataFrame:
    """
    Loads a layer from a zipped File Geodatabase stored in GCS, with a progress bar.

    Parameters:
        zip_filename: Path to ZIP file in the GCS bucket
        bucket: GCS bucket name
        layer_index: Index of the layer to load (default: 0 = first layer)
        chunk_size: Number of bytes to read per chunk (default: 1MB)

    Returns:
        GeoDataFrame with the selected layer
    """
    gcs_path = f"gs://{bucket}/{zip_filename}"

    with fsspec.open(gcs_path, mode="rb") as f:
        file_size = f.size  # Get total size for progress bar
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "data.zip")
            with open(zip_path, "wb") as local_zip:
                print(f"Downloading {zip_filename} from GCS...")
                with tqdm(total=file_size, unit="B", unit_scale=True, desc="Downloading") as pbar:
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        local_zip.write(chunk)
                        pbar.update(len(chunk))

            # Extract ZIP
            print("Extracting ZIP...")
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(tmpdir)

            # Find .gdb folder
            gdb_dirs = [os.path.join(tmpdir, d) for d in os.listdir(tmpdir) if d.endswith(".gdb")]
            if not gdb_dirs:
                raise FileNotFoundError("No .gdb directory found in ZIP.")

            gdb_path = gdb_dirs[0]

            # List layers
            layers = fiona.listlayers(gdb_path)
            print("Available layers:", layers)

            gdf = gpd.GeoDataFrame()
            for layer in layers:
                print(f"Loading layer: {layer}")
                gdf0 = gpd.read_file(gdb_path, layer=layer)
                gdf0["gdb_layer_name"] = layer
                gdf = pd.concat((gdf, gdf0), axis=0)

            return gdf
