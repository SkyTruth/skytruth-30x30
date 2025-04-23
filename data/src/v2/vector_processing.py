import logging
from typing import Dict
import asyncio
from tqdm.asyncio import tqdm
import geopandas as gpd
import pandas as pd
from shapely.geometry import box
from shapely import remove_repeated_points

from vector_utils import get_matches, repair_geometry, arrange_dimensions
from processing_grid import ComputationGrid
from utils import background


logger = logging.getLogger(__name__)


@background
def simplify_job(geometry, pbar, rmv_slivers=True, tlrc=0.0001, **kwargs) -> gpd.GeoDataFrame:
    try:
        return repair_geometry(geometry.simplify(tlrc), remove_slivers=rmv_slivers)
    except Exception as e:
        print(e)
        return geometry
    finally:
        pbar.update(1)


@background
def spatial_dissolve_job(gdf: gpd.GeoDataFrame, geometry_restr, p_bar, gby, ops):
    try:
        candidates = get_matches(
            geometry_restr,
            gdf.geometry,
        )
        if len(candidates) > 0:

            subset = (
                gdf.loc[candidates.index]
                .clip(geometry_restr)
                .dissolve(by=gby, aggfunc=ops)
                .reset_index()
            )
            return subset
    except Exception as e:
        logging.error(e)
        return gpd.GeoDataFrame()
    finally:
        p_bar.update(1)


@background
def spatial_join_job(df_large_chunk, df_small, pbar, **kwargs):
    """Spatial join job


    Args:
        df_large_chunk (gpd.GeoDataFrame): Large GeoDataFrame
        df_small (gpd.GeoDataFrame): Small GeoDataFrame

    Returns:
        gpd.GeoDataFrame: Spatial join result
    """
    try:
        bbox = df_large_chunk.total_bounds

        candidates = get_matches(box(*bbox), df_small.geometry)
        if len(candidates) > 0:
            subset = df_small.loc[candidates.index].clip(box(*bbox))

            result = gpd.overlay(df_large_chunk, subset).reset_index(drop=True)
            result.geometry = result.geometry.apply(repair_geometry)
        else:
            result = gpd.GeoDataFrame(columns=df_large_chunk.columns)
        return result
    except Exception as e:
        logging.error(e)
        return gpd.GeoDataFrame()
    finally:
        pbar.update(1)


@background
def spatial_difference_job(df_large_chunk, df_small, pbar, **kwargs):
    """Spatial difference job


    Args:
        df_large_chunk (gpd.GeoDataFrame): Large GeoDataFrame
        df_small (gpd.GeoDataFrame): Small GeoDataFrame

    Returns:
        gpd.GeoDataFrame: Spatial difference result
    """
    try:
        bbox = df_small.total_bounds

        candidates = get_matches(box(*bbox), df_large_chunk.geometry)
        if len(candidates) > 0:
            subset_large = df_large_chunk.loc[candidates.index].clip(box(*bbox))
            filtered = subset_large.loc[
                subset_large.geometry.geom_type.isin(["MultiPolygon", "Polygon"])
            ].reset_index()
            result = gpd.overlay(
                df_small,
                filtered,
                how="difference",
            ).reset_index(drop=True)
        else:
            result = df_large_chunk
        return result
    except Exception as e:
        logging.error(e)
        print(e, flush=True)
        return gpd.GeoDataFrame()
    finally:
        pbar.update(1)


async def simplify_async(gdf: gpd.GeoDataFrame, rmv_sliv=False) -> gpd.GeoDataFrame:
    gdf["geometry"] = gdf.geometry.remove_repeated_points()

    with tqdm(total=gdf.shape[0], desc="simplifying", unit="row") as pbar:
        gdf["geometry"] = await asyncio.gather(
            *(simplify_job(val, pbar, rmv_sliv) for val in gdf["geometry"])
        )
    return gdf


async def spatial_join(
    geodataframe_a: gpd.GeoDataFrame, geodataframe_b: gpd.GeoDataFrame, grid: ComputationGrid
) -> gpd.GeoDataFrame:
    """Create spatial join between two GeoDataFrames."""
    # we build the spatial index for the larger GeoDataFrame
    smaller_dim, larger_dim = arrange_dimensions(geodataframe_a, geodataframe_b)

    grid.create_gdf_density_based_grid(larger_dim, 5000)

    list_of_chunks = grid.split_gdf_by_grid(larger_dim)

    logger.info(f"grid split into {len(list_of_chunks)} chunks")

    with tqdm(
        total=len(list_of_chunks), desc="spatial join", unit="chunk"
    ) as p_bar:  # we create a progress bar
        new_df = await asyncio.gather(
            *(spatial_join_job(chunk, smaller_dim, p_bar) for chunk in list_of_chunks)
        )

    return gpd.GeoDataFrame(pd.concat(new_df, ignore_index=True), crs=smaller_dim.crs)


async def spatial_dissolve(
    gdf, grid_comp: ComputationGrid, gby: str, ops: str | Dict[str, str]
) -> gpd.GeoDataFrame:
    grid_comp.create_gdf_density_based_grid(gdf, 5000)
    with tqdm(
        total=grid_comp.grid_gdf.shape[0], desc="Disolving dataset elements", unit="chunk"
    ) as p_bar:
        result = await asyncio.gather(
            *[
                spatial_dissolve_job(gdf, geometry, p_bar, gby, ops)
                for geometry in grid_comp.grid_gdf.geometry.values
            ],
        )

    return gpd.GeoDataFrame(pd.concat(result, ignore_index=True), crs=gdf.crs)


async def spatial_difference(
    geodataframe_a: gpd.GeoDataFrame, geodataframe_b: gpd.GeoDataFrame, grid: ComputationGrid
) -> gpd.GeoDataFrame:
    """Create spatial difference between two GeoDataFrames."""
    # we build the spatial index for the larger GeoDataFrame
    smaller_dim, larger_dim = arrange_dimensions(geodataframe_a, geodataframe_b)

    list_of_chunks_small = grid.split_gdf_by_grid(smaller_dim, clip=True)
    list_of_chunks_big = grid.split_gdf_by_grid(larger_dim, clip=True)

    logger.info(f"grid split into {len(list_of_chunks_big)} chunks")

    with tqdm(
        total=len(list_of_chunks_big), desc="spatial difference", unit="chunk"
    ) as p_bar:  # we create a progress bar
        new_df = await asyncio.gather(
            *(
                spatial_difference_job(chunk_b, chunk_s, p_bar)
                for chunk_b, chunk_s in zip(list_of_chunks_big, list_of_chunks_small)
            )
        )

    return gpd.GeoDataFrame(pd.concat(new_df, ignore_index=True), crs=smaller_dim.crs)
