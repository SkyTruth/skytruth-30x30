import pyogrio
import geopandas as gpd
import rasterio as rio
from rasterio.windows import from_bounds, Window
from pathlib import Path
import pandas as pd


class VectorDataset:
    type: str = "raster"
    path: Path | None = None
    name: str | None = None
    id: str | None = None
    crs: str | None = None
    bounds: tuple | None = None

    def __init__(self, file_path, name=None):
        self.type = "vector"
        self.path = file_path
        self.name = name if name else file_path.split("/")[-1].split(".")[0]
        self.id = f"{self.name}_{self.type}"

        self.set_metadata()

    def set_metadata(self):
        # Set metadata for the vector dataset
        metadata = pyogrio.read_info(self.file_path)
        self.crs = metadata.crs
        self.bounds = metadata.total_bounds
        self.shape = metadata.shape
        self.fields = metadata.fields  # Fields in the mo

    def read(self, bbox=None, **kwargs):
        # Read data from the vector dataset
        return gpd.read_file(self.file_path, bbox=bbox, **kwargs)

    def write(self, data, output_file, append=True, **kwargs):
        # Save data to the vector dataset
        data.to_file(output_file, append, **kwargs)


class RasterDataset:
    type: str = "raster"
    path: Path = None
    name: str | None = None
    id: str | None = None
    crs: str | None = None
    bounds: tuple | None = None
    profile: dict = None  # rasterio profile typing

    def __init__(
        self,
        path,
        profile=None,
    ):
        self.path = path
        self.name = path.stem
        self.id = f"{self.name}_{self.type}"

        if profile is not None:  # is an output file for writing
            self.profile = profile
            self._write_metadata()  # creates an empty file with the metadata to prepare it for writing
        else:
            self.__load_metadata()

    def __load_metadata(self):
        with rio.open(self.path.as_posix()) as src:
            self.profile = src.profile.copy()
            self.bounds = src.bounds
            self.crs = src.crs

    def _write_metadata(self):
        with rio.open(self.path.as_posix(), "w", **self.profile) as dst:
            print(f"Created empty raster file: {dst.name}")
            pass

    def _open_writer(self, *args, **kwargs) -> rio.io.DatasetWriter:
        return rio.open(self.path.as_posix(), "r+", *args, **kwargs)

    def _open_reader(self, *args, **kwargs) -> rio.io.DatasetReader:
        return rio.open(self.path.as_posix(), "r", *args, **kwargs)

    def read(self, band=1, window: Window | None = None, *read_args, **read_kwargs):
        with self._open_reader(*read_args, **read_kwargs) as src:
            return src.read(band, window=window)

    def write(self, data, band=1, window=None, is_masked=False, *write_args, **write_kwargs):
        with self._open_writer(*write_args, **write_kwargs) as dst:
            dst.write(data, indexes=band, window=window, masked=is_masked)


class NonGeospatialDataset:
    #  Note: This class is not prepare to be larger than memory size
    def __init__(self, file_path):
        self.file_path = file_path
        self.bounds = None  # Non-geospatial datasets do not have bounds
        self.crs = None  # Non-geospatial datasets do not have CRS
        self.shape = None  # Non-geospatial datasets do not have shape
        self.fields = None  # Non-geospatial datasets do not have fields

    def set_metadata(self):
        # Set metadata for the non-geospatial dataset
        pass

    def read(self, **kwargs):
        # Read data from the non-geospatial dataset
        return pd.read_csv(self.file_path, **kwargs)

    def write(self, data, output_file, **kwargs):
        # Save data to the non-geospatial dataset
        data.to_csv(output_file, **kwargs)
