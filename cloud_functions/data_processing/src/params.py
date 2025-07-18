import datetime

today_formatted = datetime.datetime.today().strftime("%b%Y")

# ------------------------------------------------------------
#                    Marine Regions
# ------------------------------------------------------------

# Marine region data versions: https://www.marineregions.org/stats_downloads.php
MARINE_REGIONS_URL = "https://www.marineregions.org/download_file.php"
MARINE_REGIONS_HEADERS = {
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
MARINE_REGIONS_BODY = {
    "name": "Jason",
    "organisation": "skytruth",
    "email": "tech@skytruth.com",
    "country": "United States",
    "user_category": "academia",
    "purpose_category": "Conservation",
    "agree": "1",
}

EEZ_ZIPFILE_NAME = "static/eezs.zip"
EEZ_SHAPEFILE_NAME = "eez_v12.shp"
EEZ_PARAMS = {"name": "World_EEZ_v12_20231025.zip"}

HIGH_SEAS_ZIPFILE_NAME = "static/high_seas.zip"
HIGH_SEAS_SHAPEFILE_NAME = "High_Seas_v2.shp"
HIGH_SEAS_PARAMS = {"name": "World_High_Seas_v2_20241010.zip"}


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
WDPA_URL = f"https://d1gam3xoknrgr2.cloudfront.net/current/WDPA_{today_formatted}_Public.zip"
WDPA_FILE_NAME = "raw/WDPA_Public.zip"
ARCHIVE_WDPA_FILE_NAME = f"archive/raw/WDPA_{today_formatted}_Public.zip"
WDPA_COUNTRY_LEVEL_FILE_NAME = "raw/WDPA_country_level.csv"
ARCHIVE_WDPA_COUNTRY_LEVEL_FILE_NAME = f"archive/raw/WDPA_{today_formatted}_country_level.csv"
WDPA_GLOBAL_LEVEL_FILE_NAME = "raw/WDPA_global_level.csv"
ARCHIVE_WDPA_GLOBAL_LEVEL_FILE_NAME = f"archive/raw/WDPA_{today_formatted}_global_level.csv"
WDPA_GLOBAL_LEVEL_URL = "https://www.protectedplanet.net/en/global_statistics_download"


# ------------------------------------------------------------
#                         Habitats
# ------------------------------------------------------------
HABITATS_URL = "https://habitats.oceanplus.org/downloads/global_statistics.zip"
HABITATS_FILE_NAME = "habitats/global_statistics.zip"
ARCHIVE_HABITATS_FILE_NAME = f"archive/habitats/global_statistics_{today_formatted}.zip"
MANGROVES_API_URL = "https://mangrove-atlas-api.herokuapp.com/admin/widget_protected_areas.csv"
MANGROVES_REQUEST_HEADERS = {
    "Cookie": (
        "_mangrove_atlas_api_session=fJuobvI2fH42WfGfMtRTp%2BksIDdPEpY6DG8uCuITsENtrRGG4AA3nYEeAI7"
        "dytzpK%2F0dGIHq84O54MRr6eiPgiwCYXp2XP4IzXM40dFt%2FI6hoB0WXC%2Fwrd81XreNnMZiSEE6IVT5R0fqMcm"
        "sZdPn53u0A1d4CGU3FfliOZuWkckBuA%2F7C4upBGuSS8817LqOh1slG%2BsEOGp3nk7WX4fMoPbsHWtARfFwdfoAH"
        "z448LO7uWuZdyiu7YOrS0ZxOZEb9JZ8hcUJph4pBFofZLpOvtQQutgZY21T5bhQ7Kwfl56e6Qr0SZ%2B8sIzMfky3h"
        "%2FjOA6DNTLoy%2BZLiZBAgFHlTYm2JwlwqWgAZU8D7cE7Zn%2Fxgf3LFF9pZ9Fe3QG4c8LIwH%2FxqjEd8GsZAhBMg"
        "BWbxubigQ9gZssZt6CIO--7qiVsTAT8JAKj1jU--U7TI%2Fz9c151bfD8iZdkBDw%3D%3D"
    )
}

MANGROVES_FILE_NAME = "habitats/mangroves_protected_areas.csv"
ARCHIVE_MANGROVES_FILE_NAME = f"archive/habitats/mangroves_protected_areas_{today_formatted}.csv"
SEAMOUNTS_URL = (
    "https://datadownload-production.s3.amazonaws.com/ZSL002_ModelledSeamounts2011_v1.zip"
)
SEAMOUNTS_FILE_NAME = "habitats/seamounts.zip"
ARCHIVE_SEAMOUNTS_FILE_NAME = f"archive/habitats/{SEAMOUNTS_URL.split('/')[-1]}"


# ------------------------------------------------------------
#                         GADM
# ------------------------------------------------------------
GADM_URL = "https://geodata.ucdavis.edu/gadm/gadm4.1/gadm_410-levels.zip"
GADM_ZIPFILE_NAME = "static/gadm_410-levels.zip"

CHUNK_SIZE = 8192
