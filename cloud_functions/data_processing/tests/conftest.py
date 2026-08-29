import geopandas as gpd
import pandas as pd
import pytest
from shapely import Point, Polygon


@pytest.fixture
def mock_locs_translations_df():
    """Minimal translations table to be merged at the end."""
    return pd.DataFrame(
        {
            "code": ["USA", "MEX", "ABNJ", "NA", "USA*", "MEX*"],
            "name": [
                "United States",
                "Mexico",
                "High Seas",
                "North America",
                "United States*",
                "Mexico*",
            ],
            "name_es": [
                "Estados Unidos",
                "México",
                "Alta mar",
                "Norteamérica",
                "Estados Unidos*",
                "México*",
            ],
            "name_fr": [
                "États-Unis",
                "Mexique",
                "Haute mer",
                "Amérique du Nord",
                "États-Unis*",
                "Mexique*",
            ],
            "name_pt": [
                "Estados Unidos",
                "México",
                "Alto-mar",
                "América do Norte",
                "Estados Unidos*",
                "México*",
            ],
        }
    )


@pytest.fixture
def mock_eez_by_loc_gdf(crs="EPSG:4326"):
    """
    Minimal EEZ-like frame
    """
    return gpd.GeoDataFrame(
        {
            "location": ["USA", "MEX", "ABNJ"],
            "AREA_KM2": ["1000.4", "499.6", "123.1"],  # strings on purpose
            "has_shared_marine_area": [True, None, False],
            "geometry": [
                Point(-100, 35).buffer(3.0),
                Point(-102, 18).buffer(2.0),
                Polygon([(-10, -10), (-10, 10), (10, 10), (10, -10)]),
            ],
        },
        crs=crs,
    )


@pytest.fixture
def mock_eez_by_sov_gdf():
    """
    Minimal EEZ-like frame
    """
    return gpd.GeoDataFrame(
        {
            "name": ["mock_eez"],
            "name_es": ["mock_eez_es"],
            "name_fr": ["mock_eez_fr"],
            "name_pt": ["mock_eez_pt"],
            "ISO_TER1": ["USA"],
            "ISO_TER2": ["MEX"],
            "ISO_TER3": ["ABNJ"],
            "ISO_SOV1": ["USA*"],
            "MRGID": [1234],
            "AREA_KM2": ["1000.4"],  # strings on purpose
            "geometry": [Polygon([(-10, -10), (-10, 10), (10, 10), (10, -10)])],
        },
        crs="EPSG:4326",
    )


@pytest.fixture
def mock_mpatlas_v4_geojson():
    """
    MPAtlas API v4 /zone/geojson response shape (see the v4 API docs).
    Covers: single- and multi-value country, all three partial-date formats,
    null designated_date, qualifying and non-qualifying establishment stages,
    a null geometry, and site-level establishment_stage differing from the
    zone-effective assessment_establishment_stage.
    """

    def make_feature(zone_id, properties, geometry="default"):
        if geometry == "default":
            geometry = {
                "type": "Polygon",
                "coordinates": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]],
            }
        return {
            "type": "Feature",
            "id": zone_id,
            "geometry": geometry,
            "properties": {"zone_id": zone_id, "site_id": zone_id + 1000, **properties},
        }

    return {
        "type": "FeatureCollection",
        "features": [
            make_feature(
                4821,
                {
                    "zone_name": "Cairns Section",
                    "site_name": "Great Barrier Reef",
                    "site_designation": "Marine Park",
                    "country": "AUS",
                    "sovereign": "AUS",
                    "establishment_stage": "designated",  # site-level, must be ignored
                    "assessment_establishment_stage": "implemented",
                    "mpaguide_protection_level": "high",
                    "proposed_date": "1975",
                    "designated_date": "1981-01",
                    "implemented_date": "2004-07-01",
                    "wdpa_id": 555624,
                    "wdpa_pid": "555624_1",
                    "status": "published",
                },
            ),
            make_feature(
                4822,
                {
                    "zone_name": "Shared Waters Zone",
                    "site_name": "Tasman Sea Site",
                    "site_designation": "Marine Reserve",
                    "country": "AUS,NZL",
                    "sovereign": "AUS,NZL",
                    "establishment_stage": "implemented",
                    "assessment_establishment_stage": "actively managed",
                    "mpaguide_protection_level": "full",
                    "proposed_date": None,
                    "designated_date": "1990",
                    "implemented_date": "1995",
                    "wdpa_id": 100001,
                    "wdpa_pid": "100001_A",
                    "status": "published",
                },
            ),
            make_feature(
                4823,
                {
                    "zone_name": "Pending Zone",
                    "site_name": "Pending Site",
                    "site_designation": "Sanctuary",
                    "country": "MEX",
                    "sovereign": "MEX",
                    "establishment_stage": "implemented",
                    "assessment_establishment_stage": "designated",  # non-qualifying
                    "mpaguide_protection_level": "full",
                    "proposed_date": "2010-05",
                    "designated_date": None,
                    "implemented_date": None,
                    "wdpa_id": 100002,
                    "wdpa_pid": "100002_A",
                    "status": "published",
                },
                geometry=None,
            ),
        ],
    }
