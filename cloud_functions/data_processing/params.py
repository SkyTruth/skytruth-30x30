import datetime

today_formatted = datetime.datetime.today().strftime("%b%Y")

# ------------------------------------------------------------
#                    Marine Regions
# ------------------------------------------------------------

# Marine region data versions: https://www.marineregions.org/stats_downloads.php
MARINE_REGIONS_url = "https://www.marineregions.org/download_file.php"
MARINE_REGIONS_headers = {
    "content-type": "application/x-www-form-urlencoded",
    "cookie": (
        "PHPSESSID=29190501b4503e4b33725cd6bd01e2c6; "
        "vliz_webc=vliz_webc2; "
        "jwplayer.captionLabel=Off"
    ),
    "dnt": "1",
    "origin": "https://www.marineregions.org",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
}
MARINE_REGIONS_body = {
    "name": "Jason",
    "organisation": "skytruth",
    "email": "hello@skytruth.com",
    "country": "Spain",
    "user_category": "academia",
    "purpose_category": "Conservation",
    "agree": "1",
}

EEZ_ZIPFILE_NAME = "static/eezs.zip"
EEZ_SHAPEFILE_NAME = "eez_v12.shp"
EEZ_params = {"name": "World_EEZ_v12_20231025.zip"}

HIGH_SEAS_ZIPFILE_NAME = "static/high_seas.zip"
HIGH_SEAS_SHAPEFILE_NAME = "High_Seas_v2.shp"
HIGH_SEAS_params = {"name": "World_High_Seas_v2_20241010.zip"}


# ------------------------------------------------------------
#                    MPATLAS
# ------------------------------------------------------------

MPATLAS_URL = "https://guide.mpatlas.org/api/v2/zone/geojson"
MPATLAS_FILE_NAME = "raw/mpatlas_zone_assessment.zip"
ARCHIVE_MPATLAS_FILE_NAME = f"archive/raw/mpatlas_zone_assessment_{today_formatted}.zip"

# ------------------------------------------------------------
#                 Protected Seas
# ------------------------------------------------------------

PROTECTED_SEAS_URL = "https://map.navigatormap.org/api/regionStats/"
# TODO: should this be static?
PROTECTED_SEAS_GEOM_ZIPFILE = "static/Protected_seas_geom.zip"
PROTECTED_SEAS_FILE_NAME = "raw/protected_seas.csv"
ARCHIVE_PROTECTED_SEAS_FILE_NAME = f"archive/raw/protected_seas_{today_formatted}.zip"


# ------------------------------------------------------------
#                 Protected Planet (WDPA)
# ------------------------------------------------------------
WDPA_API_URL = "http://api.protectedplanet.net/v3/"
ARCHIVE_WDPA_FILE_NAME = f"archive/raw/WDPA_{today_formatted}_Public.zip"
ARCHIVE_WDPA_COUNTRY_LEVEL_FILE_NAME = f"archive/raw/WDPA_{today_formatted}_country_level.csv"
WDPA_FILE_NAME = "raw/WDPA_Public.zip"
WDPA_COUNTRY_LEVEL_FILE_NAME = "raw/WDPA_country_level.csv"


FISHING_PROTECTION_FILENAME = "intermediate/fishing_protection.csv"
LOCATIONS_FILENAME = "static/locations.csv"


# Product Archive
HIGHLY_PROTECTED_MPA_FILE_NAME = f"archive/prod/highly_protected_mpa_{today_formatted}.zip"
