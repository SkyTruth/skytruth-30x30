import numpy as np

# based on https://www.researchgate.net/publication/343446883_A_global_map_of_terrestrial_habitat_types
TERRESTRIAL_HABITATS_URL = "https://storage.cloud.google.com/vector-data-raw/terrestrial/jung_etal_2020/iucn_habitatclassification_composite_lvl1_ver004.tif"
BIOME_RASTER_PATH = (
    "static/terrestrial_jung_etal_2020_iucn_habitatclassification_composite_lvl1_ver004.tif"
)
resolution_m = 100
terrestrial_tolerance = (
    0.001  # simplification tolerance (in degrees) for PA polygons; proportional to resolution_m
)
marine_tolerance = 0.0001

LAND_COVER_CLASSES = {
    1: "Forest",
    2: "Savanna",
    3: "Shrubland",
    4: "Grassland",
    5: "Wetlands/open water",
    6: "Rocky/mountains",
    7: "Desert",
    8: "Artificial",
    255: "Other",
}


def reclass_function(ndata: np.ndarray) -> np.ndarray:
    # Apply the value changes
    ndata = np.where(ndata < 200, 1, ndata)  # forest
    ndata = np.where((ndata >= 200) & (ndata < 300), 2, ndata)  # savanna
    ndata = np.where((ndata >= 300) & (ndata < 400), 3, ndata)  # scrub/shrub
    ndata = np.where((ndata >= 400) & (ndata < 500), 4, ndata)  # grassland
    ndata = np.where(ndata == 501, 5, ndata)  # open water - Wetlands/open water
    ndata = np.where(ndata == 505, 5, ndata)  # open water - Wetlands/open water
    ndata = np.where((ndata >= 500) & (ndata < 600), 5, ndata)  # wetlands - Wetlands/open water
    ndata = np.where(ndata == 984, 5, ndata)  # wetlands - Wetlands/open  water
    ndata = np.where(ndata == 910, 5, ndata)  # wetlands - Wetlands/open water
    ndata = np.where((ndata >= 600) & (ndata < 800), 6, ndata)  # rocky/mountains
    ndata = np.where((ndata >= 800) & (ndata < 900), 7, ndata)  # desert
    ndata = np.where((ndata >= 1400) & (ndata < 1500), 8, ndata)  # ag/urban - Artificial

    # Ensure the ndata is within the 8-bit range

    return np.clip(ndata, 0, 255).astype(np.uint8)
