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

EEZ_PARAMS = {
    "name": "World_EEZ_v12_20231025.zip",
    "zipfile_name": "static/eezs.zip",
    "shapefile_name": "eez_v12.shp",
}
# EEZ_ZIPFILE_NAME = "static/eezs.zip"
# EEZ_SHAPEFILE_NAME = "eez_v12.shp"
# EEZ_PARAMS = {"name": "World_EEZ_v12_20231025.zip"}

HIGH_SEAS_PARAMS = {
    "name": "World_High_Seas_v2_20241010.zip",
    "zipfile_name": "static/high_seas.zip",
    "shapefile_name": "High_Seas_v2.shp",
}

EEZ_LAND_UNION_PARAMS = {
    "name": "EEZ_land_union_v4_202410.zip",
    "zipfile_name": "static/eez_land_union.zip",
    "shapefile_name": "EEZ_land_union_v4_202410.shp",
}

# HIGH_SEAS_ZIPFILE_NAME = "static/high_seas.zip"
# HIGH_SEAS_SHAPEFILE_NAME = "High_Seas_v2.shp"
# HIGH_SEAS_PARAMS = {"name": "World_High_Seas_v2_20241010.zip"}

MARINE_REGIONS_FILE_NAME = "static/marine_regions_processed.geojson"

# ------------------------------------------------------------
#                           GADM
# ------------------------------------------------------------

GADM_URL = "https://geodata.ucdavis.edu/gadm/gadm4.1/gadm_410-levels.zip"
GADM_ZIPFILE_NAME = "static/gadm_410-levels.zip"
GADM_FILE_NAME = "static/GADM_processed.geojson"


# ------------------------------------------------------------
#        Locations (combined Marine Regions and GADM)
# ------------------------------------------------------------
LOCATIONS_FILE_NAME = "static/locations_processed.csv"


# ------------------------------------------------------------
#                    MPATLAS
# ------------------------------------------------------------

MPATLAS_URL = "https://guide.mpatlas.org/api/v2/zone/geojson"
MPATLAS_FILE_NAME = "raw/mpatlas_zone_assessment.geojson"
ARCHIVE_MPATLAS_FILE_NAME = f"archive/raw/mpatlas_zone_assessment_{today_formatted}.geojson"
MPATLAS_COUNTRY_LEVEL_API_URL = "https://mpatlas.org/api/v1/internal/countries"
MPATLAS_COUNTRY_LEVEL_FILE_NAME = "raw/mpatlas_country_level.csv"
ARCHIVE_MPATLAS_COUNTRY_LEVEL_FILE_NAME = f"archive/raw/mpatlas_{today_formatted}_country_level.csv"

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
WDPA_MPA_FILE_NAME = "raw/WDPA_marine_protected_areas.geojson"
WDPA_TERRESTRIAL_FILE_NAME = "intermediates/protected_area_geoms/terrestrial_wdpa.geojson"
WDPA_MARINE_FILE_NAME = "intermediates/protected_area_geoms/marine_wdpa.geojson"


# ------------------------------------------------------------
#                     Marine Habitats
# ------------------------------------------------------------
HABITATS_URL = "https://habitats.oceanplus.org/downloads/global_statistics.zip"
HABITATS_ZIP_FILE_NAME = "habitats/global_statistics.zip"
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

MANGROVES_ZIPFILE_NAME = "habitats/Marine-habitats_Mangroves_GlobalMangroveWatch_v3_2020.zip"
MANGROVES_SHAPEFILE_NAME = "gmw_v3_2020_vec.shp"
MANGROVES_FILE_NAME = "habitats/mangroves_protected_areas.csv"
MANGROVES_BY_COUNTRY_FILE_NAME = "static/mangroves_by_country.geojson"
ARCHIVE_MANGROVES_FILE_NAME = f"archive/habitats/mangroves_protected_areas_{today_formatted}.csv"
SEAMOUNTS_URL = (
    "https://datadownload-production.s3.amazonaws.com/ZSL002_ModelledSeamounts2011_v1.zip"
)
SEAMOUNTS_ZIPFILE_NAME = "habitats/seamounts.zip"
SEAMOUNTS_SHAPEFILE_NAME = (
    "DownloadPack-14_001_ZSL002_ModelledSeamounts2011_v1/01_Data/Seamounts/Seamounts.shp"
)
ARCHIVE_SEAMOUNTS_FILE_NAME = f"archive/habitats/{SEAMOUNTS_URL.split('/')[-1]}"

# HABITATS_FILE_NAME = "habitats/habitats_table.csv"

# ------------------------------------------------------------
#                     Terrestrial Habitats
# ------------------------------------------------------------

TERRESTRIAL_HABITATS_URL = "https://storage.cloud.google.com/vector-data-raw/terrestrial/jung_etal_2020/iucn_habitatclassification_composite_lvl1_ver004.tif"
BIOME_RASTER_PATH = (
    "static/terrestrial_jung_etal_2020_iucn_habitatclassification_composite_lvl1_ver004.tif"
)
PROCESSED_BIOME_RASTER_PATH = "static/processed_biome_raster.tif"
REPROJECTED_BIOME_RASTER_PATH = "static/reprojected_processed_biome_raster.tif"
COUNTRY_HABITATS_SUBTABLE_FILENAME = "habitats/processed_country_stats.csv"
COUNTRY_TERRESTRIAL_HABITATS_FILE_NAME = "static/country_terrestrial_stats.json"
PA_TERRESTRIAL_HABITATS_FILE_NAME = "habitats/pa_terrestrial_stats.json"

# ------------------------------------------------------------
#                       Global Areas
# ------------------------------------------------------------
GLOBAL_MANGROVE_AREA_FILE_NAME = "intermediates/total_area/global_mangrove_area.json"


# ------------------------------------------------------------
#                            Tables
# ------------------------------------------------------------
PROTECTION_COVERAGE_FILE_NAME = f"tables/protection_coverage_{today_formatted}.csv"
PROTECTION_LEVEL_FILE_NAME = f"tables/protection_level_{today_formatted}.csv"
FISHING_PROTECTION_FILE_NAME = f"tables/fishing_protection_{today_formatted}.csv"
HABITAT_PROTECTION_FILE_NAME = f"tables/habitat_protection_{today_formatted}.csv"

# ------------------------------------------------------------
#                            MISC
# ------------------------------------------------------------
#                         GADM
# ------------------------------------------------------------
GADM_URL = "https://geodata.ucdavis.edu/gadm/gadm4.1/gadm_410-levels.zip"
GADM_ZIPFILE_NAME = "static/gadm_410-levels.zip"

CHUNK_SIZE = 8192
LOCATIONS_TRANSLATED_FILE_NAME = "processing/locations_translated.csv"
DEPENDENCY_TO_PARENT_FILE_NAME = "processing/dependency_to_parent.json"
RELATED_COUNTRIES_FILE_NAME = "processing/related_countries.json"
REGIONS_FILE_NAME = "processing/regions_with_territories.json"
