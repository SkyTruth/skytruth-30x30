from typing import List, Literal
from itertools import product

import geopandas as gpd
import numpy as np
from shapely.geometry import box
from pyproj import CRS, Transformer

from vector_utils import get_matches, check_crs_area_of_use_contains_bbox
from raster_utils import check_chunk_size, chunks
from interfaces import BoundingBox


class ComputationGrid:

    def __init__(
        self,
        bounds: BoundingBox,
        crs: CRS,
        max_cell_size: int = 10,
        grid_type: Literal["dense", "sparse"] = "dense",
    ):
        if not check_crs_area_of_use_contains_bbox(crs, bounds):
            raise ValueError(f"Bounds are outside of the area of use of the CRS {bounds}")

        self.bounds = bounds
        self.crs = crs
        self.grid_cell_size = max_cell_size
        self.grid_type = grid_type
        self.grid_gdf = self.__create_grid()

    # TODO:Extract this as helper function
    def __create_grid(self) -> gpd.GeoDataFrame:
        minx, miny, maxx, maxy = self.bounds
        x = np.arange(minx, maxx, self.grid_cell_size)
        y = np.arange(miny, maxy, self.grid_cell_size)
        polygons = [
            {
                "geometry": box(i, j, i + self.grid_cell_size, j + self.grid_cell_size),
                "cell_id": f"{i}_{j}",
            }
            for i, j in product(x, y)
        ]
        return gpd.GeoDataFrame(polygons, crs=self.crs)

    # TODO:Extract this as helper function
    def __subdivide_grid(
        self, gdf: gpd.GeoDataFrame, max_cellsize: float, max_complexity: int
    ) -> List:
        subdivided_elements = []
        for grid_element in self.grid_gdf.geometry:
            candidates = get_matches(grid_element, gdf)
            density = len(candidates)
            if density > max_complexity:
                subdivision_cellsize = max_cellsize / 2
                subgrid = ComputationGrid(
                    grid_element.bounds, self.crs, subdivision_cellsize, self.grid_type
                )
                subdivided_elements.extend(
                    subgrid.__subdivide_grid(gdf, subdivision_cellsize, max_complexity)
                )
            elif self.grid_type == "sparse" and density > 0:
                subdivided_elements.append(grid_element)

            elif self.grid_type == "dense":
                subdivided_elements.append(grid_element)

        return subdivided_elements

    def create_gdf_density_based_grid(
        self, gdf: gpd.GeoDataFrame, max_complexity: int = 10000
    ) -> gpd.GeoDataFrame:
        if gdf.crs != self.crs:
            gdf = gdf.to_crs(self.crs)

        if not check_crs_area_of_use_contains_bbox(self.crs, gdf.total_bounds):
            raise ValueError(
                f"Bounds {gdf.total_bounds} are outside of the area of use of the CRS {self.crs.area_of_use.bounds}"
            )

        subdivided_elements = self.__subdivide_grid(gdf, self.grid_cell_size, max_complexity)

        self.grid_gdf = gpd.GeoDataFrame(geometry=subdivided_elements, crs=self.crs)
        return self.grid_gdf

    def create_rasters_based_grid(
        self,
        list_of_rasters: List[str] | str,
        mem_limit: int | None = None,
        cpu_limit: int | None = None,
        buffer_size: int = 0,
        cell_size_m: int = 100,
    ) -> gpd.GeoDataFrame:

        if isinstance(list_of_rasters, str):
            list_of_rasters = [list_of_rasters]

        # get the cell size of the grid projection
        projected_from_wgs84 = Transformer.from_crs("EPSG:4310", self.crs, always_xy=True)
        bounds_midpoint = (self.bounds[0] + self.bounds[2]) / 2, (
            self.bounds[1] + self.bounds[3]
        ) / 2
        cell_size = projected_from_wgs84.transform(*bounds_midpoint)[0] * cell_size_m

        recomended_chunk_size = check_chunk_size(list_of_rasters, buffer_size, mem_limit, cpu_limit)

        my_chunks = chunks(self.bounds, cell_size, recomended_chunk_size)

        if self.grid_gdf.shape[0] < len(list(my_chunks)):
            self.grid_gdf = gpd.GeoDataFrame(
                geometry=[box(*chunk) for chunk in my_chunks], crs=self.crs
            )
        return self.grid_gdf

    def split_gdf_by_grid(
        self,
        gdf: gpd.GeoDataFrame,
        clip: bool = False,
        clip_buffer: int | float | None = None,
    ) -> List:
        if gdf.crs != self.crs:
            gdf = gdf.to_crs(self.crs)

        result = []
        gdf["already_processed"] = False

        for geometry in self.grid_gdf.geometry:
            candidates = get_matches(geometry, gdf.geometry)
            subset = gdf.loc[(candidates.index)]
            subset_np = subset[~subset["already_processed"]]
            if clip:
                if clip_buffer is not None:
                    subset_np = gpd.clip(subset_np, geometry.buffer(clip_buffer))
                else:
                    subset_np = gpd.clip(subset_np, geometry)
            else:
                gdf.loc[subset_np.index, "already_processed"] = True

            if not subset_np.empty:
                result.append(subset_np.drop(columns=["already_processed"]))

        return result
