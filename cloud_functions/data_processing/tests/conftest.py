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
