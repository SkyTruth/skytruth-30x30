import asyncio
import logging
from pathlib import Path
import functools
import zipfile
import requests

logger = logging.getLogger(__name__)


# local paralellization using asyncio
def background(f: callable):
    def wrapped(*args, **kwargs):
        return asyncio.get_event_loop().run_in_executor(None, f, *args, **kwargs)

    return wrapped


## Access data functions & utilities
def download_file(url: str, dst_file: Path, overwrite=False):

    if dst_file.exists() and not overwrite:
        return dst_file

    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(dst_file.as_posix(), "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

    return dst_file


def unzip_file(zip_file: Path, extracted_folder: Path | None = None, overwrite=False):
    if extracted_folder is None:
        extracted_folder = zip_file.parent.joinpath(zip_file.stem)

    print(extracted_folder)
    print(zip_file)

    if not overwrite and extracted_folder.exists() and len(list(extracted_folder.iterdir())) > 0:
        return extracted_folder

    with zipfile.ZipFile(zip_file, "r") as zip_ref:
        zip_ref.extractall(extracted_folder)
    return extracted_folder


def rm_tree(pth: Path) -> None:
    if not pth.exists():
        logger.warning(f"Path {pth} does not exist.")
        return

    for child in pth.glob("*"):
        if child.is_file():
            child.unlink()
        else:
            rm_tree(child)
    pth.rmdir()
