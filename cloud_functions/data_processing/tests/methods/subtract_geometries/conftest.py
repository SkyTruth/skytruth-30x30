import geopandas as gpd
import pytest
from shapely.geometry import box


@pytest.fixture
def mock_location_gdf():
    return gpd.GeoDataFrame(
        {
            "location": ["AUS", "NZL"],
            "geometry": [box(0, 0, 2, 2), box(10, 0, 12, 2)],
        },
        crs="EPSG:4326",
    )


@pytest.fixture
def mock_pa_gdf():
    return gpd.GeoDataFrame(
        {
            "ISO3": ["AUS"],
            "STATUS": ["Designated"],
            "DESIG_ENG": ["Marine Park"],
            "PA_DEF": [1],
            "geometry": [box(0, 0, 1, 1)],
        },
        crs="EPSG:4326",
    )
