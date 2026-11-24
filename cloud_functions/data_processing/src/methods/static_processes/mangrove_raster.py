import tarfile
import tempfile
from pathlib import Path

import rasterio

from src.core.params import (
    BUCKET,
    MANGROVES_RASTER_FILE_NAME,
    MANGROVES_RASTER_PATH,
    MANGROVES_RASTER_YEAR,
)
from src.utils.gcp import download_file_from_gcs, upload_file_to_gcs
from src.utils.logger import Logger

logger = Logger()


def build_mangrove_raster(vrt_path: str, out_path: str, year: int) -> None:
    """
    Writes one year of the Global Mangrove Watch extent stack as a single-band raster.

    The stack is a VRT with one band per year, named by its description. Only blocks
    holding mangroves are written, so the global raster stays small: mangroves cover
    a sliver of its extent.

    Parameters
    ----------
    vrt_path : str
        Local path to the stack's VRT.
    out_path : str
        Local path of the GeoTIFF written, with mangrove pixels 1 and nodata 0.
    year : int
        Year of the band to write.
    """
    with rasterio.open(vrt_path) as src:
        if str(year) not in src.descriptions:
            raise ValueError(f"{vrt_path} has no band for {year}: {src.descriptions}")
        band = src.descriptions.index(str(year)) + 1

        profile = {
            "driver": "GTiff",
            "width": src.width,
            "height": src.height,
            "count": 1,
            "dtype": "uint8",
            "crs": src.crs,
            "transform": src.transform,
            "nodata": 0,
            "tiled": True,
            "blockxsize": 512,
            "blockysize": 512,
            "compress": "deflate",
            "predictor": 2,
            "sparse_ok": True,
            "bigtiff": "yes",
        }
        with rasterio.open(out_path, "w", **profile) as dst:
            for _, window in dst.block_windows(1):
                block = src.read(band, window=window)
                if block.any():
                    dst.write(block, 1, window=window)


def process_mangrove_raster(
    file_name: str = MANGROVES_RASTER_FILE_NAME,
    year: int = MANGROVES_RASTER_YEAR,
    bucket: str = BUCKET,
    verbose: bool = True,
) -> None:
    """
    Writes one year of the downloaded Global Mangrove Watch extent stack to GCS

    Parameters
    ----------
    file_name : str
        GCS path of the stack's .tar.gz, holding one GeoTIFF per 1° tile and a VRT
        over them.
    year : int
        Year of the extent to keep.
    bucket : str
        GCS bucket name.
    verbose : bool
        Whether to print progress messages.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        archive = Path(tmp_dir) / "mangroves_raster.tar.gz"
        download_file_from_gcs(bucket, file_name, str(archive), verbose=verbose)

        if verbose:
            logger.info({"message": f"Extracting {archive}..."})
        raster_dir = Path(tmp_dir) / "mangroves_raster"
        with tarfile.open(archive) as tar:
            tar.extractall(raster_dir, filter="data")
        archive.unlink()

        # An archive packed on macOS holds a "._" metadata file beside each real one
        vrts = [vrt for vrt in raster_dir.rglob("*.vrt") if not vrt.name.startswith("._")]
        if len(vrts) != 1:
            raise ValueError(f"Expected one VRT in {file_name}, found {len(vrts)}: {vrts}")

        if verbose:
            logger.info({"message": f"Writing the {year} mangrove extent..."})
        out_path = Path(tmp_dir) / "mangroves.tif"
        build_mangrove_raster(str(vrts[0]), str(out_path), year)
        upload_file_to_gcs(bucket, str(out_path), MANGROVES_RASTER_PATH)

    if verbose:
        logger.info({"message": f"Uploaded the {year} mangrove extent to {MANGROVES_RASTER_PATH}"})
