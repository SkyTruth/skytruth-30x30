import gc
import glob
import os
import subprocess
import sys
import textwrap
import zipfile

import pyarrow

from src.utils.logger import Logger
from src.utils.resource_handling import show_container_mem

logger = Logger()


def unpack_in_subprocess(zip_stem, zip_path, dir, shp, layer_name, verbose=True):
    """
    unpacks a single shapefile into a parquet using subprocess to effectively
    clear memory loaded by geopandas
    """
    if verbose:
        logger.info({"message": "running subprocess to unpack shapefile into a parquet file"})
    out_path = f"{dir}/{zip_stem}_{layer_name}.parquet"
    script = textwrap.dedent(f"""
        import os, glob, geopandas as gpd, gc

        # Read directly from the zip and write to parquet
        gdf = gpd.read_file(f"zip://{zip_path}!{shp}")
        gdf.to_parquet("{out_path}")

        # Clean up GeoDataFrame memory
        gdf = gpd.GeoDataFrame()
        del gdf
        gc.collect()
    """)
    subprocess.run([sys.executable, "-c", script], check=True)
    if verbose:
        logger.info({"message": "subprocess completed"})


def unpack_parquet(zip_stem, zip_path, dir, shp, layer_name, verbose=True):
    """
    unpacks a single shapefile into a parquet using subprocess and releases
    unused memory
    """

    out_path = os.path.join(dir, f"{zip_stem}_{layer_name}.parquet")
    if verbose:
        logger.info({"message": f"Converting {zip_stem}: {layer_name} to {out_path}"})
    try:
        unpack_in_subprocess(zip_stem, zip_path, dir, shp, layer_name, verbose=True)
    except Exception as e:
        logger.warning({"message": f"Error processing {layer_name}: {e}"})
    finally:
        gc.collect()
        pyarrow.default_memory_pool().release_unused()
        show_container_mem("after garbage collection")


def unpack_pas_to_parquet(pa_dir, verbose=True):
    """
    Unpacks every shapefile in every zip under pa_dir into a parquet beside it,
    deleting each zip once its layers are written.
    """
    # Define params for unpacking
    for zip_path in glob.glob(os.path.join(pa_dir, "*.zip")):
        zip_stem = os.path.splitext(os.path.basename(zip_path))[0]
        with zipfile.ZipFile(zip_path) as z:
            for shp in [n for n in z.namelist() if n.lower().endswith(".shp")]:
                _ = unpack_parquet(
                    zip_stem,
                    zip_path,
                    pa_dir,
                    shp,
                    shp.replace(".shp", ""),
                    verbose,
                )

            # Delete zipped files
            os.remove(zip_path)
