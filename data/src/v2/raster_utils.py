import numpy as np
import psutil
from numpy import dtype, ndarray
import math
from itertools import product
from os import cpu_count
from typing import List, Iterator
import rasterio

from v2.interfaces import BoundingBox, WindowWH


def get_raster_info(raster_file):
    info = {}
    with rasterio.open(raster_file) as src:
        info = src.profile
        info["block"] = src.block_shapes
        return info


def memory_usage_2d_mb(chunk_size, _dtype, buffer_size):

    N = chunk_size[0] + 2 * buffer_size
    M = chunk_size[1] + 2 * buffer_size

    return N, M, N * M * dtype(_dtype).itemsize * 1e-6


def calculate_memory_usage(raster, buffer_size=0) -> dict:
    """
    chunksize_x = np.lcm.reduce(x) * n_factor
    chunksize_y = np.lcm.reduce(y) * n_factor
    N = chunksize_x + 2*buffer
    M = chunksize_y + 2*buffer

    N * M * number_of_arrays * bit_size * 1e-6 // MB
    """
    info = raster.metadata
    total_pixels = info["width"] * info["height"]
    N, M, block_pixels_mb = memory_usage_2d_mb(info["block"][0], info["dtype"], buffer_size)
    _, _, total_pixels_mb = memory_usage_2d_mb(
        (info["width"], info["height"]), info["dtype"], buffer_size
    )
    result = {
        "total": {"size": total_pixels_mb * info["count"]},
        "block": {
            "size": block_pixels_mb * info["count"],
            "nblocks": math.ceil(total_pixels / (N * M)),
        },
        "meta": {"size": "mb", "dtype": info["dtype"], "bands": info["count"]},
    }
    return result


def print_info(
    memory_available_mb,
    cpus,
    recommended_memory_per_core,
    block_x,
    block_y,
    dimensions,
    memory_consumption,
    buffered_memory_consumption,
    chunk_size_max,
    N,
    M,
):
    print(
        f"Memory Available: {memory_available_mb} MB \nCPUS: {cpus} \nRecommended Memory per Core: {recommended_memory_per_core} MB"
    )
    print(
        f"Block Size: {block_x}x{block_y} with {dimensions} dimensions - Memory Consumption: {round(memory_consumption,2)} MB"
    )
    print(
        f"Buffered Block Size: {N}x{M} with {dimensions} dimensions - Memory Consumption: {round(buffered_memory_consumption,2)} MB"
    )
    print(f"Max Chunk Size: {chunk_size_max}")
    print(
        f"Max Chunk Size: { math.floor(math.sqrt(recommended_memory_per_core / (buffered_memory_consumption*dimensions)))}"
    )


def recommended_memory_per_core(memory_available_mb: int | None = None, cpus: int | None = None):

    cpus = cpus or cpu_count()

    memory_available_mb = (memory_available_mb or psutil.virtual_memory().available) * (
        1.024 * 1e-6
    )  # MB

    memory_per_core = (
        np.floor((memory_available_mb / cpus) * 0.9)
        if memory_available_mb and cpus
        else memory_available_mb
    )  # 90% of the available memory

    return cpus, memory_available_mb, memory_per_core


def optimal_n_chunks(
    x: ndarray,
    y: ndarray,
    z: ndarray,
    buffer: int = 0,
    dtype: str = "uint8",
    memory_available: int | None = None,
    cpus: int | None = None,
    display_info: bool = False,
):
    """
    calculate the optimal number of chunks to process a set of rasters
    """
    cpus_availables, memory_available_mb, rmemory_per_core = recommended_memory_per_core(
        memory_available, cpus
    )

    block_x = np.gcd.reduce(x)
    block_y = np.gcd.reduce(y)
    dimensions = z.sum()
    bN, bM, buffered_memory = memory_usage_2d_mb((block_x, block_y), dtype, buffer)

    buffered_memory_consumption = buffered_memory * dimensions
    chunk_size_max = math.floor(math.sqrt(rmemory_per_core / (buffered_memory_consumption)))
    if display_info:
        xN, yM, block_memory = memory_usage_2d_mb((block_x, block_y), dtype, 0)
        memory_consumption = block_memory * dimensions
        print_info(
            memory_available_mb,
            cpus_availables,
            rmemory_per_core,
            block_x,
            block_y,
            dimensions,
            memory_consumption,
            buffered_memory_consumption,
            chunk_size_max,
            xN,
            yM,
        )

    return chunk_size_max * bN, chunk_size_max * bM


def check_chunk_size(
    raster: List[any],
    buffer_size: int = 0,
    memory_available: int | None = None,
    cpus: int | None = None,
):

    x, y, z = [], [], []

    for r in raster:
        if isinstance(r, str):
            r_info = get_raster_info(r)
            x.append(r_info["block"][0][0])
            y.append(r_info["block"][0][1])
            z.append(r_info["count"])

    return optimal_n_chunks(
        np.array(x),
        np.array(y),
        np.array(z),
        buffer_size,
        memory_available=memory_available,
        cpus=cpus,
    )


def bbox_size(
    bounds: BoundingBox,
    scale: float,
) -> WindowWH:
    left, bottom, right, top = bounds
    return (round((right - left) / scale), round((top - bottom) / scale))


def w_h_bbox(bounds, scale):
    left, bottom, right, top = bounds
    return (round((right - left) / scale), round((top - bottom) / scale))


def block_generator(arr: np.ndarray, block_x: int, block_y: int):
    for r in range(0, np.prod(arr.shape), block_x * block_y):
        i, j = divmod(r, arr.shape[1])
        yield arr[i : i + block_x, j : j + block_y]


def chunk_bounds(
    total_bounds: BoundingBox,
    scale: float,
    x: int,
    y: int,
    chunksize: int,
) -> BoundingBox:
    """Get the bounding box of a chunk with index <x>,<y>."""
    left, bottom, right, top = total_bounds
    if isinstance(chunksize, int):
        chunksize = (chunksize, chunksize)
    _chunksize = np.asarray(chunksize) * scale

    l = left + x * _chunksize[0]
    r = min(l + _chunksize[0], right)
    t = top - y * _chunksize[1]
    b = max(t - _chunksize[1], bottom)

    return (l, b, r, t)


def num_chunks(
    total_bounds: BoundingBox,
    scale: float,
    chunksize: WindowWH | int,
) -> WindowWH:
    """Return the number of chunks necessary to cover the Manager's bounding box."""
    left, bottom, right, top = total_bounds

    if isinstance(chunksize, int):
        chunksize = (chunksize, chunksize)

    return (
        math.ceil((right - left) / scale / chunksize[0]),
        math.ceil((top - bottom) / scale / chunksize[1]),
    )


def chunks(total_bounds: BoundingBox, scale: float, chunksize: int = 512) -> Iterator[BoundingBox]:
    """Generate bounding boxes for chunks of at most <chunksize> pixels in the managers scale and projection.

    The chunks method divides the Manager's bounding box into chunks of manageable size.
    Each chunk will be at most <chunksize> pixels, though the geographic extent of the chunk
    depends on the Manager's projection and scale.

    Args:
        chunksize (int): Size of the chunks in pixels (excluding buffer).

    Yields:
        BoundingBox: The bounding box of the chunk in the Manager's projection
    """
    xshards, yshards = num_chunks(total_bounds, scale, chunksize)
    for x, y in product(range(xshards), range(yshards)):
        yield chunk_bounds(total_bounds, scale, x, y, chunksize)
