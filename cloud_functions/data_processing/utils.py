import fiona
from google.cloud import storage
import io
import pandas as pd
from io import BytesIO
import requests
from pathlib import Path
from tqdm import tqdm
import os
import tempfile
import zipfile
import geopandas as gpd
import fsspec
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


def load_zipped_shapefile_from_gcs(filename, bucket, shapefile_name=None, verbose=False):
    """
    Downloads a ZIP archive from GCS, extracts it locally, and loads the requested shapefile.
    If shapefile_name is None, the first .shp file found is used.
    Prints out all .shp files found in the archive.
    """
    gcs_zip_path = f"gs://{bucket}/{filename}"

    # Read ZIP content from GCS
    with fsspec.open(gcs_zip_path, mode="rb") as f:
        zip_bytes = io.BytesIO(f.read())

    # Extract ZIP to a temporary directory
    with zipfile.ZipFile(zip_bytes) as z:
        with tempfile.TemporaryDirectory() as tmpdir:
            z.extractall(tmpdir)

            # Find shapefile if not specified
            shp_files = []
            for root, _, files in os.walk(tmpdir):
                for file in files:
                    if file.endswith(".shp"):
                        shp_files.append(os.path.join(root, file))

            # Print all found shapefile paths
            if shp_files:
                if verbose:
                    print("Shapefiles found in archive:")
                    for shp in shp_files:
                        print(f"  - {os.path.relpath(shp, tmpdir)}")
            else:
                raise ValueError("No .shp file found in archive.")

            # Determine which shapefile to load
            if shapefile_name is None:
                shapefile_path = shp_files[0]
            else:
                shapefile_path = os.path.join(tmpdir, shapefile_name)

            # Load with geopandas
            gdf = gpd.read_file(shapefile_path)
            return gdf


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


def save_gdf_to_zipped_shapefile_gcs(gdf, zip_name, bucket_name, blob_path, verbose=True):
    """
    Saves a GeoDataFrame to a zipped shapefile and uploads it directly to GCS.

    Parameters:
        gdf (GeoDataFrame): The geodataframe to save.
        zip_name (str): Base name for the shapefile (no path or .zip).
        bucket_name (str): GCS bucket name.
        blob_path (str): Path to store the zipped shapefile in GCS.
        verbose (bool): Whether to print upload status.
    """
    zip_name = Path(zip_name).stem
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_path)

    with tempfile.TemporaryDirectory() as tmpdir:
        shp_dir = Path(tmpdir) / "shapefile"
        shp_dir.mkdir(parents=True, exist_ok=True)

        # Save shapefile components
        shp_base = shp_dir / zip_name
        gdf.to_file(shp_base.with_suffix(".shp"), driver="ESRI Shapefile")

        # Zip the contents into memory
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file in shp_dir.glob(f"{zip_name}.*"):
                zipf.write(file, arcname=file.name)
        zip_buffer.seek(0)

        total_size = len(zip_buffer.getvalue())
        chunk_size = 5 * 1024 * 1024  # 5 MB
        wrapped_buffer = TqdmBytesIO(zip_buffer.getvalue(), total_size, chunk_size)

        blob.chunk_size = chunk_size
        if verbose:
            print(f"Uploading {blob_path} to gs://{bucket_name} ({total_size / 1e6:.2f} MB)...")

        blob.upload_from_file(wrapped_buffer, content_type="application/zip", timeout=600)
        wrapped_buffer.close()

        if verbose:
            print(f"Upload complete: gs://{bucket_name}/{blob_path}")
