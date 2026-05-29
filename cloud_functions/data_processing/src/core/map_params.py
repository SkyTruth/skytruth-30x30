import datetime
import os

today_formatted = datetime.datetime.today().strftime("%b%Y")

# ------------------------
# General Mapbox
# ------------------------
MAPBOX_BASE_URL = "https://api.mapbox.com/uploads/v1/"
MAPBOX_USER = os.environ.get("MAPBOX_USER", None)
MAPBOX_TOKEN = os.environ.get("MAPBOX_TOKEN", None)

# ------------------------
# General PMTiles
# ------------------------
PMTILES_BUCKET = os.environ.get("PMTILES_BUCKET", "")

# ------------------------
# EEZ
# ------------------------
EEZ_TILESET_ID = "eez_v12"
EEZ_TILESET_NAME = "EEZ V12"
EEZ_TILESET_FILE = f"maps/eez_v12_{today_formatted}.mbtiles"
EEZ_TOLERANCE = 0.0001

MARINE_REGIONS_TILESET_ID = "marine_regions"
MARINE_REGIONS_TILESET_NAME = "Marine Regions"
MARINE_REGIONS_TILESET_FILE = f"maps/marine_regions_{today_formatted}.mbtiles"

# ------------------------
# GADM
# ------------------------
COUNTRIES_TILESET_ID = "countries"
COUNTRIES_TILESET_NAME = "countries"
COUNTRIES_TILESET_FILE = f"maps/countries_{today_formatted}.mbtiles"
COUNTRIES_TOLERANCE = 0.001

TERRESTRIAL_REGIONS_TILESET_ID = "terrestrial_regions"
TERRESTRIAL_REGIONS_TILESET_NAME = "Terrestrial Regions"
TERRESTRIAL_REGIONS_TILESET_FILE = f"maps/terrestrial_regions_{today_formatted}.mbtiles"

# ------------------------
# WDPA
# ------------------------
TERRESTRIAL_PA_TILESET_ID = "terrestrial_pas"
TERRESTRIAL_PA_TILESET_NAME = "Terrestrial PAs"
TERRESTRIAL_PA_TILESET_FILE = f"maps/terrestrial_pas_{today_formatted}.mbtiles"

MARINE_PA_TILESET_ID = "marine_pas"
MARINE_PA_TILESET_NAME = "Marine PAs"
MARINE_PA_TILESET_FILE = f"maps/marine_pas_{today_formatted}.mbtiles"
WDPA_TOLERANCE = 0.001

# ------------------------
# MPAtlas_New
# ------------------------
MPATLAS_TILESET_ID = "mpatlas"
MPATLAST_TILESET_NAME = "MPATLAS"
MPATLAS_TILESET_FILE = f"maps/mpatlas_{today_formatted}.mbtiles"

# ------------------------
# Cimate Resilient Corals (WCS MERMAID)
# ------------------------
CORAL_REEF_TILESET_NAME = "Climate Resilient Corals"
CORAL_REEF_TILESET_FILE = "climate_resilient_corals.pmtiles"
CORAL_REEF_TILESET_ARCHIVE_FILE = f"maps/climate_resilient_corals_{today_formatted}.pmtiles"
CORAL_REEF_COLOR_RAMP = "coral"
CORAL_REEF_DOMAIN = (0.0, 1.0)
CORAL_REEF_MAX_ZOOM = 10
