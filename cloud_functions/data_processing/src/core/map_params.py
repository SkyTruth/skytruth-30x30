import os

# ------------------------
# General Mapbox
# ------------------------
MAPBOX_BASE_URL = "https://api.mapbox.com/uploads/v1/"
MAPBOX_USER = os.environ.get("MAPBOX_USER", None)
MAPBOX_TOKEN = os.environ.get("MAPBOX_TOKEN", None)

# ------------------------
# EEZ
# ------------------------
EEZ_TILESET_ID = "eez_v12"
EEZ_TILESET_NAME = "EEZ V12"
EEZ_TILESET_FILE = "maps/eez_v12.mbtiles"
EEZ_TOLERANCE = 0.0001

MARINE_REGIONS_TILESET_ID = "marine_regions"
MARINE_REGIONS_TILESET_NAME = "Marine Regions"
MARINE_REGIONS_TILESET_FILE = "maps/marine_regions.mbtiles"

# ------------------------
# GADM
# ------------------------
COUNTRIES_TILESET_ID = "countries"
COUNTRIES_TILESET_NAME = "countries"
COUNTRIES_TILESET_FILE = "maps/countries.mbtiles"
COUNTRIES_TOLERANCE = 0.001

TERRESTRIAL_REGIONS_TILESET_ID = "terrestrial_regions"
TERRESTRIAL_REGIONS_TILESET_NAME = "Terrestrial Regions"
TERRESTRIAL_REGIONS_TILESET_FILE = "maps/terrestrial_regions.mbtiles"

# ------------------------
# WDPA
# ------------------------
TERRESTRIAL_PA_TILESET_ID = "terrestrial_pas"
TERRESTRIAL_PA_TILESET_NAME = "Terrestrial Pas"
TERRESTRIAL_PA_TILESET_FILE = "maps/terrestrial_pas.mbtiles"

MARINE_PA_TILESET_ID = "marine_pas"
MARINE_PA_TILESET_NAME = "Marine Pas"
MARINE_PA_TILESET_FILE = "maps/marine_pas.mbtiles"

WDPA_TOLERANCE = 0.001