from rasterstats import zonal_stats

from exactextract import exact_extract  # in the future i need to explore this further
import geopandas as gpd
import pandas as pd
import numpy as np
import rasterio as rio
from shapely.geometry import box

from pathlib import Path
from typing import List, Dict, Literal
from logging import getLogger
import asyncio
from tqdm.asyncio import tqdm
from functools import partial
from concurrent.futures import ProcessPoolExecutor

# from processing_grid import ComputationGrid
# from exactextract.raster import NumPyRasterSource

logger = getLogger(__name__)


def define_count_frac(df: pd.DataFrame | gpd.GeoDataFrame, col_name: str = "count") -> pd.DataFrame:
    prov_col = col_name
    if col_name == "count":
        prov_col = "value"

    return (
        df.assign(**{prov_col: df["count"] * df["frac"]})
        .drop(columns=["count", "frac"])
        .rename(columns={prov_col: col_name})
    )  # pixel units


def remap_classes(
    df: pd.DataFrame | gpd.GeoDataFrame, col: str, c_map: dict | None
) -> pd.DataFrame:
    if not c_map:
        return df
    else:
        return df.assign(**{col: df["unique"].map(c_map)}).drop(columns=["unique"])


def processing_raster_data_exact(
    rast: str, vecs: gpd.GeoDataFrame, ops: List[str], c_map_list, **kwargs
) -> pd.DataFrame:
    cols = vecs.columns.tolist()
    cols.pop(cols.index("geometry"))

    exact_extract_params = {
        "rast": rast,
        "vec": vecs,  # important to pass geom type polygon or multipolygon other types are not supported
        "max_cells_in_memory": 512 * 512 * 5,
        "output": "pandas",
        "ops": ops,
        "include_cols": "iso_3",
        "progress": False,
    }
    try:

        data = exact_extract(
            **exact_extract_params,
            **kwargs,
        )
        if data is None:
            return pd.DataFrame(columns=cols)

        if c_map_list:
            return (
                data.explode(["unique", "frac"])
                .pipe(define_count_frac)
                .pipe(remap_classes, "category", c_map_list)
            )

    except Exception as e:
        print(e, flush=True)

        return pd.DataFrame(columns=cols)


def processing_raster_data_raster_stats(
    rast: str, vecs: gpd.GeoDataFrame, ops: List[str], c_map_list, **kwargs
) -> pd.DataFrame:
    zonal_stats_params = {
        "vectors": vecs.geometry,
        "raster": rast,
        "all_touched": False,
    }
    if c_map_list:
        zonal_stats_params.update(
            {
                "categorical": True,
                "category_map": c_map_list,
            }
        )
    else:
        zonal_stats_params.update(
            {
                "stats": ops,
            }
        )
    # Todo: why this is not working?
    # if use_windowed:
    #     with rio.open(rast) as src:
    #         geom = box(*vecs.total_bounds)
    #         window = rio.features.geometry_window(src, [geom], pad_x=0, pad_y=0)
    #         nodata = src.nodata
    #         affine = src.transform
    #         data_arr = src.read(1, window=window, masked=False)
    #     zonal_stats_params.update(
    #         {
    #             "raster": data_arr,
    #             "affine": affine,
    #             "nodata": nodata,
    #         }
    #     )
    data_res = zonal_stats(**zonal_stats_params, **kwargs)
    data_df = pd.DataFrame(data_res, index=vecs.index)

    if c_map_list:
        data_df = (
            data_df.reset_index()
            .melt("index", var_name="category", value_name="count")
            .set_index("index")
        )

    return vecs.drop(columns="geometry").join(data_df, how="left")


async def process_raster_data(
    rast: str,
    vecs: gpd.GeoDataFrame,
    ops: List[str],
    c_map_list: dict,
    stats_func: str,
    pbar,
    SHARED_PROCESS_POOL,
    **kwargs
) -> pd.DataFrame:

    processing_func: Dict[str, callable] = {
        "exact": processing_raster_data_exact,
        "raster_stats": processing_raster_data_raster_stats,
    }

    try:

        selected_func = processing_func.get(stats_func)
        result = await asyncio.get_event_loop().run_in_executor(
            SHARED_PROCESS_POOL,
            partial(selected_func, rast, vecs, ops, c_map_list, **kwargs),
        )

        return result

    except Exception as e:
        print(e, flush=True)
        return None

    finally:
        pbar.update(1)


async def calculate_zonal_stats(
    ras,
    vecs,
    stats,
    gby_cols=None,
    c_map=None,
    _with: Literal["exact", "raster_stats"] = "raster_stats",
    **kwargs
):
    """
    Calculate zonal statistics for a list of rasters and vector files
    :param ras: list of rasters
    :param vecs: list of vectors
    :param stats: list of statistics to calculate
    :param prefix: prefix for the output files
    :param out_dir: output directory
    :return: None
    """

    with rio.Env(CPL_DEBUG=False), ProcessPoolExecutor() as pool, tqdm(
        total=len(vecs), desc="Computing raster stats", unit="chunk"
    ) as p_bar:
        tasks = [
            process_raster_data(ras, vec, stats, c_map, _with, p_bar, pool, **kwargs)
            for vec in vecs
        ]

        result = await asyncio.gather(*tasks)

    return result
    # pd.concat(result, axis=0).groupby(gby_cols).agg({"count": "sum"}).reset_index()


def calculate_custom_unique(raster_A, raster_B, gdf_subset, oupt_cols):
    bbox = box(*gdf_subset.total_bounds)
    with rio.env.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_USE_HEAD=False):
        with rio.open(raster_A) as src:
            window = rio.features.geometry_window(src, [bbox], pad_x=0, pad_y=0)
            transform_a = rio.windows.transform(window, src.transform)
            data = src.read(1, window=window, masked=False)
            shape = data.shape

        with rio.open(raster_B) as src:
            window = rio.features.geometry_window(src, [bbox], pad_x=0, pad_y=0)
            data_for_masks = src.read(1, window=window, masked=False)

        location_part_rast = rio.features.rasterize(
            [(x.geometry, i) for i, x in gdf_subset.iterrows()],
            out_shape=shape,
            transform=transform_a,
            all_touched=True,
        )

    merged = np.array([data.flatten(), location_part_rast.flatten(), data_for_masks.flatten()]).T

    data_view = np.ascontiguousarray(merged).view(
        np.dtype((np.void, merged.dtype.itemsize * merged.shape[1]))
    )

    values, count = np.unique(
        data_view,
        return_counts=True,
    )

    return gdf_subset[oupt_cols].join(
        pd.DataFrame(
            values.view(merged.dtype).reshape(-1, merged.shape[1]),
            columns=["data", "location", "mask"],
            dtype=int,
        )
        .join(pd.DataFrame(count, columns=["count"], dtype=int))
        .set_index("location")
    )


async def custom_process_raster_data(
    rast: str,
    mask_rast: str,
    vecs: gpd.GeoDataFrame,
    oupt_cols: List[str],
    pbar,
    SHARED_PROCESS_POOL,
    **kwargs
) -> pd.DataFrame:
    try:
        result = await asyncio.get_event_loop().run_in_executor(
            SHARED_PROCESS_POOL,
            partial(calculate_custom_unique, rast, mask_rast, vecs, oupt_cols),
        )

        return result

    except Exception as e:
        print(e, flush=True)
        return None

    finally:
        pbar.update(1)


async def custom_calculate_zonal_stats(dataset_raster_path, efg_raster_path, gdf_list, cols_output):
    """
    Calculate zonal statistics for a list of rasters and vector files
    :param ras: list of rasters
    :param vecs: list of vectors
    :param stats: list of statistics to calculate
    :param prefix: prefix for the output files
    :param out_dir: output directory
    :return: None
    """

    with ProcessPoolExecutor(max_workers=17) as pool, tqdm(
        total=len(gdf_list), desc="Computing raster stats", unit="chunk"
    ) as p_bar:
        tasks = [
            custom_process_raster_data(
                dataset_raster_path,
                efg_raster_path,
                vector,
                cols_output,
                pbar=p_bar,
                SHARED_PROCESS_POOL=pool,
            )
            for vector in gdf_list
        ]

        result = await asyncio.gather(*tasks)

    return pd.concat(result, ignore_index=True)
