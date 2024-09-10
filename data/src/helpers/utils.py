import os
import shutil
import requests
from logging import getLogger
from pathlib import Path
from typing import Any, Dict, Literal, Union
from google.cloud import storage
from google.oauth2 import service_account

from helpers.file_handler import FileConventionHandler, STEPS
from helpers.settings import Settings

logger = getLogger(__name__)


def rm_tree(pth: Path) -> None:
    pth = Path(pth)
    for child in pth.glob("*"):
        if child.is_file():
            child.unlink()
        else:
            rm_tree(child)
    pth.rmdir()


def downloadFile(
    url: str,
    output_path: Union[Path, None] = None,
    body: Union[dict, None] = None,
    params: Union[dict, None] = None,
    headers: Union[dict, None] = None,
    overwrite: bool = False,
    file: Union[str, None] = None,
) -> Path:
    """
    Download a file from a url.

    Args:
        url (str): The url to the file.
        output_path (Union[Path, None], optional): The path to the output file.
                                The default is None.
    Returns:
        Path: The path to the output file.
    """
    try:
        if not output_path:
            output_path = Path(os.getcwd())

        if not file:
            if isinstance(params, dict) and "name" in params.keys():
                file = params.get("name")
            else:
                raise ValueError("No file name in url or params")

        output_file = output_path.joinpath(file)

        if overwrite:  # so we can always start from scratch
            output_file.unlink(missing_ok=True)

        if output_file.exists() and not overwrite:
            logger.info(f"File {output_file} already exists.")
            return output_file

        if body:
            r = requests.post(url, params=params, data=body, headers=headers, allow_redirects=True)
        else:
            r = requests.get(url, params, headers=headers, allow_redirects=True)

        r.raise_for_status()

        with open(output_file, "wb") as f:
            f.write(r.content)

        logger.info("Download Finish.")
        return output_file

    except Exception as e:
        logger.error(e)
        raise e


def writeReadGCP(
    credentials: str | Dict[str, Any],
    bucket_name: str,
    blob_name: str,
    file: Path,
    operation: Literal["w", "r"] = "w",
):
    """Write or read a blob from GCS using file-like IO

    Args:
        bucket_name (str): The name of the bucket.
        blob_name (str): The name of the blob.
        file (io.BytesIO): The file-like object to write or read.
        operation (Literal["w", "r"], optional): The operation to perform. "w" for write, "r" for read. Defaults to "w".
    """
    storage_client = storage.Client(
        credentials=service_account.Credentials.from_service_account_info(credentials)
    )
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    if operation == "w":
        with open(file, "rb") as f:
            blob.upload_from_file(f)
    elif operation == "r":
        with open(file, "wb") as f:
            blob.download_to_file(f)
    else:
        raise ValueError("operation must be 'w' or 'r'")


def make_archive(source: Path, destination: Path) -> None:
    base_name = destination.parent.joinpath(destination.stem)
    fmt = destination.suffix.replace(".", "")
    root_dir = source.parent
    base_dir = source.name
    shutil.make_archive(str(base_name), fmt, root_dir, base_dir)


def download_and_unzip_if_needed(
    file_handler: FileConventionHandler, prev_step: STEPS, mysettings: Settings, fmt: str = "zip"
):

    zip_path = file_handler.get_step_fmt_file_path(prev_step, fmt, parent=True)

    unzzipped_path = file_handler.get_processed_step_path(prev_step)

    print(zip_path)
    print(unzzipped_path)

    if (
        unzzipped_path.exists()
        and unzzipped_path.is_dir()
        and len(list(unzzipped_path.glob("*"))) > 0
    ):
        return unzzipped_path

    elif not zip_path.exists():
        writeReadGCP(
            credentials=mysettings.GCS_KEYFILE_JSON,
            bucket_name=mysettings.GCS_BUCKET,
            blob_name=file_handler.get_remote_path(prev_step),
            file=zip_path,
            operation="r",
        )

    shutil.unpack_archive(zip_path, unzzipped_path.parent)

    return unzzipped_path
