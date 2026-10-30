from src.methods.static_processes.eez import (
    process_eez_geoms,
    process_eez_land_union,
)
from src.methods.static_processes.gadm import process_gadm_geoms
from src.methods.static_processes.marine_habitat_geoms import process_marine_habitat_geoms
from src.methods.static_processes.marine_habitat_sources import download_marine_habitats
from src.methods.static_processes.near_shore_iho import process_near_shore_iho
from src.methods.static_processes.terrestrial_biome import (
    generate_terrestrial_biome_stats_country,
    process_terrestrial_biome_raster,
)

__all__ = [
    # Land boundaries
    "process_gadm_geoms",
    # EEZ
    "process_eez_geoms",
    "process_eez_land_union",
    # Near-shore IHO
    "process_near_shore_iho",
    # Marine habitats
    "download_marine_habitats",
    "process_marine_habitat_geoms",
    # Terrestrial biome
    "generate_terrestrial_biome_stats_country",
    "process_terrestrial_biome_raster",
]
