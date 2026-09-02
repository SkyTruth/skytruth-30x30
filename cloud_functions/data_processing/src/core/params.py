import datetime
import os

verbose = True
PP_API_KEY = os.getenv("PP_API_KEY", "")
BUCKET = os.getenv("BUCKET", "")
PROJECT = os.getenv("PROJECT", "")

GLOBAL_MARINE_AREA_KM2 = 361000000
GLOBAL_TERRESTRIAL_AREA_KM2 = 134954835

today_formatted = datetime.datetime.today().strftime("%b%Y")


# ------------------------------------------------------------
#                    Marine Regions
# ------------------------------------------------------------

# Marine region data versions: https://www.marineregions.org/stats_downloads.php
MARINE_REGIONS_URL = "https://www.marineregions.org/download_file.php"
MARINE_REGIONS_HEADERS = {
    "content-type": "application/x-www-form-urlencoded",
    "cookie": (
        "PHPSESSID=5600795b6f0472af520dc19af739737e; "
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
EEZ_FILE_NAME = "static/eez_processed.geojson"
EEZ_MULTIPLE_SOV_FILE_NAME = "static/eez_multi_sov_processed.geojson"

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

EEZS_TRANSLATED_FILE_NAME = "processing/eezs_translated.csv"

MARINE_REGIONS_FILE_NAME = "static/marine_regions_processed.geojson"

# ------------------------------------------------------------
#                           GADM
# ------------------------------------------------------------

GADM_URL = "https://geodata.ucdavis.edu/gadm/gadm4.1/gadm_410-levels.zip"
GADM_ZIPFILE_NAME = "static/gadm_410-levels.zip"
GADM_FILE_NAME = "static/GADM_processed.geojson"

# ------------------------------------------------------------
#                      GADM/EEZ union
# ------------------------------------------------------------

GADM_EEZ_UNION_FILE_NAME = "static/GADM_eez_union.geojson"

# ------------------------------------------------------------
#   Locations (combined Marine Regions, GADM, and IHO seas)
# ------------------------------------------------------------
LOCATIONS_FILE_NAME = "tables/locations_processed.csv"


# ------------------------------------------------------------
#                    MPATLAS
# ------------------------------------------------------------

MPATLAS_URL = "https://guide.mpatlas.org/api/public/v4/zone/geojson"
MPATLAS_FILE_NAME = "raw/mpatlas_zone_assessment.geojson"
MPATLAS_META_FILE_NAME = "intermediates/mpa_meta.csv"
ARCHIVE_MPATLAS_FILE_NAME = f"archive/raw/mpatlas_zone_assessment_{today_formatted}.geojson"
MPATLAS_COUNTRY_LEVEL_API_URL = "https://mpatlas.org/api/v1/internal/countries"
MPATLAS_COUNTRY_LEVEL_FILE_NAME = "raw/mpatlas_country_level.csv"
ARCHIVE_MPATLAS_COUNTRY_LEVEL_FILE_NAME = f"archive/raw/mpatlas_{today_formatted}_country_level.csv"
MPATLAS_GLOBAL_API_URL = "https://mpatlas.org/api/v1/internal/summary"
MPATLAS_GLOBAL_FILE_NAME = "raw/mpatlas_global.json"
ARCHIVE_MPATLAS_GLOBAL_FILE_NAME = f"archive/raw/mpatlas_{today_formatted}_global.json"

# ------------------------------------------------------------
#                 Protected Seas
# ------------------------------------------------------------

PROTECTED_SEAS_URL = "https://map.navigatormap.org/api/regionStats/"
# TODO: should this be static?
PROTECTED_SEAS_GEOM_ZIPFILE = "static/Protected_seas_geom.zip"
PROTECTED_SEAS_FILE_NAME = "raw/protected_seas.csv"
ARCHIVE_PROTECTED_SEAS_FILE_NAME = f"archive/raw/protected_seas_{today_formatted}.csv"
PROTECTED_SEAS_SITES_FILE_NAME = "protected_seas/protected_seas_sites.parquet"
ARCHIVE_PROTECTED_SEAS_SITES_FILE_NAME = (
    f"archive/protected_seas/protected_seas_sites_{today_formatted}.parquet"
)
PROTECTED_SEAS_SITES_URL = "https://map.navigatormap.org/api"


# ------------------------------------------------------------
#                 Protected Planet (WDPA)
# ------------------------------------------------------------
WDPA_API_URL = "http://api.protectedplanet.net/v3/"
WDPA_URL = (
    "https://d1gam3xoknrgr2.cloudfront.net/current/"
    f"WDPA_WDOECM_{today_formatted}_Public_all_shp.zip"
)
ARCHIVE_RAW_WDPA_FILE_NAME = f"archive/raw/WDPA_{today_formatted}_Public.zip"
WDPA_COUNTRY_LEVEL_FILE_NAME = "raw/WDPA_country_level.csv"
ARCHIVE_WDPA_COUNTRY_LEVEL_FILE_NAME = f"archive/raw/WDPA_{today_formatted}_country_level.csv"
WDPA_GLOBAL_LEVEL_FILE_NAME = "raw/WDPA_global_level.csv"
ARCHIVE_WDPA_GLOBAL_LEVEL_FILE_NAME = f"archive/raw/WDPA_{today_formatted}_global_level.csv"
WDPA_PA_FILE_NAME = "intermediates/pa_updates/WDPA_PA_changes.pkl"
ARCHIVE_WDPA_PA_FILE_NAME = f"archive/pa_updates/WDPA_{today_formatted}_PA_changes.pkl"
WDPA_GLOBAL_LEVEL_URL = "https://www.protectedplanet.net/en/global_statistics_download"
WDPA_TERRESTRIAL_FILE_NAME = "intermediates/protected_area_geoms/terrestrial_wdpa.geojson"
WDPA_MARINE_FILE_NAME = "intermediates/protected_area_geoms/marine_wdpa.geojson"
WDPA_META_FILE_NAME = "intermediates/wdpa_meta.csv"


# ------------------------------------------------------------
#                     Marine Habitats
# ------------------------------------------------------------
MANGROVES_URL = "https://zenodo.org/records/21346457/files/gmw_v4112_2025_mng_ext_cntry_info_vec.gpkg.gz?download=1"
MANGROVES_FILE_NAME = "habitats/mangroves.gpkg.gz"
ARCHIVE_MANGROVES_FILE_NAME = f"archive/habitats/mangroves_{today_formatted}.gpkg.gz"

SEAMOUNTS_URL = (
    "https://datadownload-production.s3.amazonaws.com/ZSL002_ModelledSeamounts2011_v1.zip"
)
SEAMOUNTS_ZIPFILE_NAME = "habitats/seamounts.zip"
SEAMOUNTS_SHAPEFILE_NAME = (
    "DownloadPack-14_001_ZSL002_ModelledSeamounts2011_v1/01_Data/Seamounts/Seamounts.shp"
)
ARCHIVE_SEAMOUNTS_FILE_NAME = f"archive/habitats/{SEAMOUNTS_URL.split('/')[-1]}"

COLD_WATER_CORALS_URL = "https://wcmc.io/WCMC_001"
COLD_WATER_CORALS_ZIPFILE_NAME = "habitats/cold_water_corals.zip"
ARCHIVE_COLD_WATER_CORALS_FILE_NAME = f"archive/habitats/cold_water_corals_{today_formatted}.zip"

SALTMARSHES_URL = "https://wcmc.io/WCMC_027"
SALTMARSHES_ZIPFILE_NAME = "habitats/saltmarshes.zip"
ARCHIVE_SALTMARSHES_FILE_NAME = f"archive/habitats/saltmarshes_{today_formatted}.zip"

SEAGRASSES_URL = "https://wcmc.io/WCMC_013_014"
SEAGRASSES_ZIPFILE_NAME = "habitats/seagrasses.zip"
ARCHIVE_SEAGRASSES_FILE_NAME = f"archive/habitats/seagrasses_{today_formatted}.zip"

MARINE_HABITAT_PARAMS = {
    "mangroves": {
        "url": MANGROVES_URL,
        "file_name": MANGROVES_FILE_NAME,
        "archive_file_name": ARCHIVE_MANGROVES_FILE_NAME,
        "needs_processing": True,
        "source": "gpkg",
        # Data comes from raster extent converted to vector, so there are no overlaps
        "overlaps": False,
    },
    "seamounts": {
        "url": SEAMOUNTS_URL,
        "file_name": SEAMOUNTS_ZIPFILE_NAME,
        "archive_file_name": ARCHIVE_SEAMOUNTS_FILE_NAME,
        "needs_processing": False,
    },
    "coldwatercorals": {
        "url": COLD_WATER_CORALS_URL,
        "file_name": COLD_WATER_CORALS_ZIPFILE_NAME,
        "archive_file_name": ARCHIVE_COLD_WATER_CORALS_FILE_NAME,
        "needs_processing": True,
        "source": "wcmc",
        "overlaps": True,
    },
    "saltmarshes": {
        "url": SALTMARSHES_URL,
        "file_name": SALTMARSHES_ZIPFILE_NAME,
        "archive_file_name": ARCHIVE_SALTMARSHES_FILE_NAME,
        "needs_processing": True,
        "source": "wcmc",
        "overlaps": True,
    },
    "seagrasses": {
        "url": SEAGRASSES_URL,
        "file_name": SEAGRASSES_ZIPFILE_NAME,
        "archive_file_name": ARCHIVE_SEAGRASSES_FILE_NAME,
        "needs_processing": True,
        "source": "wcmc",
        "overlaps": True,
    },
}

HABITAT_PROCESSING_PARAMS = {
    habitat: params
    for habitat, params in MARINE_HABITAT_PARAMS.items()
    if params["needs_processing"]
}

UNEP_POINT_AREA_KM2 = 1.0
MARINE_HABITAT_TOLERANCE = 0.0001
HABITAT_BY_LOCATION_FILE_PATTERN = "static/{habitat}_by_location.parquet"
GLOBAL_HABITAT_AREA_FILE_PATTERN = "intermediates/total_area/global_{habitat}_area.json"

# ------------------------------------------------------------
#                     Terrestrial Habitats
# ------------------------------------------------------------

PROCESSED_BIOME_RASTER_PATH = "static/processed_biome_raster.tif"
REPROJECTED_BIOME_RASTER_PATH = "static/reprojected_processed_biome_raster.tif"
COUNTRY_HABITATS_SUBTABLE_FILENAME = "habitats/processed_country_stats.csv"
COUNTRY_TERRESTRIAL_HABITATS_FILE_NAME = "static/country_terrestrial_stats.json"
PA_TERRESTRIAL_HABITATS_FILE_NAME = "habitats/pa_terrestrial_stats.json"

# ------------------------------------------------------------
#                       Global Areas
# ------------------------------------------------------------


# ------------------------------------------------------------
#                            Tables
# ------------------------------------------------------------
HABITAT_PROTECTION_FILE_NAME = f"tables/habitat_protection_{today_formatted}.csv"
FISHING_PROTECTION_FILE_NAME = f"tables/fishing_protection_{today_formatted}.csv"
PROTECTION_COVERAGE_FILE_NAME = f"tables/protection_coverage_{today_formatted}.csv"
PROTECTION_LEVEL_FILE_NAME = f"tables/protection_level_{today_formatted}.csv"

# ------------------------------------------------------------
#                            MISC
# ------------------------------------------------------------

CHUNK_SIZE = 8192
TOLERANCES = (0.001, 0.0001)
LOCATIONS_TRANSLATED_FILE_NAME = "processing/locations_translated.csv"
DEPENDENCY_TO_PARENT_FILE_NAME = "processing/dependency_to_parent.json"
RELATED_COUNTRIES_FILE_NAME = "processing/related_countries.json"
REGIONS_FILE_NAME = "processing/regions_with_territories.json"
NEAR_SHORE_BUFFER_KM = 10
NEAR_SHORE_IHO_FILE_NAME = f"static/iho_near_shore_{NEAR_SHORE_BUFFER_KM}km.parquet"

# ------------------------------------------------------------
#                     Conservation Builder
# ------------------------------------------------------------

CONSERVATION_BUILDER_MARINE_DATA = "conservation_builder/eez_minus_mpa.parquet"
CONSERVATION_BUILDER_NON_FULLY_HIGHLY_PROTECTED_MARINE_DATA = (
    "conservation_builder/location_minus_fhp_mpa.parquet"
)
CONSERVATION_BUILDER_TERRESTRIAL_DATA = "conservation_builder/gadm_minus_pa.parquet"
ARCHIVE_CONSERVATION_BUILDER_MARINE_DATA = (
    f"archive/conservation_builder/eez_minus_mpa_{today_formatted}.parquet"
)
ARCHIVE_CONSERVATION_BUILDER_NON_FULLY_HIGHLY_PROTECTED_MARINE_DATA = (
    f"archive/conservation_builder/location_minus_fhp_mpa_{today_formatted}.parquet"
)
ARCHIVE_CONSERVATION_BUILDER_TERRESTRIAL_DATA = (
    f"archive/conservation_builder/gadm_minus_pa_{today_formatted}.parquet"
)

# ------------------------------------------------------------
#                     Raster Data Sources
# ------------------------------------------------------------
CLIMATE_RES_CORAL_SOURCE_FILE = "raw/climate_resilient_corals.tif"

# ------------------------------------------------------------
#                     Workflow Parameters
# ------------------------------------------------------------
LONG_RUNNING_TASKS = [
    "download_protected_planet_pas",
    "generate_terrestrial_biome_stats",
    "update_protected_areas",
    "generate_gadm_minus_pa",
    "generate_protected_areas_table",
    "update_gadm_minus_pa",
    "update_climate_resilient_coral_tileset",
    "process_marine_habitat_geoms",
    "generate_habitat_protection_table",
    "generate_protection_coverage_stats_table",
    "process_mangroves",
    "download_protected_seas",
]
