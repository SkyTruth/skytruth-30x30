from collections.abc import Mapping
from typing import NamedTuple


class RasterHabitats(NamedTuple):
    """A PostGIS raster table of unprotected habitat, one row per tile, and the habitat
    each reported pixel value stands for."""

    table: str
    classes: Mapping[int, str]


# "Other" (255) is left out, as it is in the progress tracker
TERRESTRIAL_HABITATS = RasterHabitats(
    "terrestrial_habitats_minus_pa",
    {
        1: "forest",
        2: "savanna",
        3: "shrubland",
        4: "grassland",
        5: "wetlands-open-waters",
        6: "rocky-mountains",
        7: "desert",
        8: "artificial",
    },
)

MANGROVES = RasterHabitats("mangroves_minus_pa", {1: "mangroves"})
