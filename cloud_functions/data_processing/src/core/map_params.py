import os

# ------------------------
# General Mapbox
# ------------------------
MAPBOX_BASE_URL = "https://api.mapbox.com/uploads/v1/"
MAPBOX_USER = os.environ.get("MAPBOX_USERNAME", None)
MAPBOX_TOKEN = os.environ.get("MAPBOX_TOKEN", None)

# ------------------------
# EEZ
# ------------------------
EEZ_TILESET_ID = "eez_v12"
EEZ_TILESET_NAME = "EEZ V12"
EEZ_TILESET_FILE = "maps/eez_v12.mbtiles"

# ------------------------
# Miscellaneous
# ------------------------
MAP_TOLERANCE = 0.0001
