import pyarrow

from src.methods.download_and_process.mpatlas import (
    download_mpatlas,
    download_mpatlas_country,
    download_mpatlas_global,
    download_mpatlas_zone,
    normalize_mpatlas_geojson,
)
from src.methods.download_and_process.protected_planet_stats import (
    download_protected_planet,
    download_protected_planet_country,
    download_protected_planet_global,
)
from src.methods.download_and_process.protected_seas import download_protected_seas
from src.methods.download_and_process.wdpa import download_and_process_protected_planet_pas

pyarrow.set_memory_pool(pyarrow.default_memory_pool())
pyarrow.default_memory_pool().release_unused()

__all__ = [
    # MPAtlas
    "download_mpatlas",
    "download_mpatlas_country",
    "download_mpatlas_global",
    "download_mpatlas_zone",
    "normalize_mpatlas_geojson",
    # Protected Planet statistics
    "download_protected_planet",
    "download_protected_planet_country",
    "download_protected_planet_global",
    # Protected Seas
    "download_protected_seas",
    # WDPA protected areas
    "download_and_process_protected_planet_pas",
]
