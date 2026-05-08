import geopandas as gpd

from src.core.processors import mask_mpatlas_protection_level


def test_mask_mpatlas_protection_level():
    """
    Test the mask_mpatlas_protection_level function with various
    combinations of establishment_stage and protection_mpaguide_level values

    mask_mpatlas_protection_level should replace protection_mpaguide_level with "unknown" for rows
    where establishment_stage is not "actively managed" or "implemented"
    """
    gdf = gpd.GeoDataFrame(
        {
            "designation": ["MPA", "MPA", "MPA", "MPA", "MPA"],
            "establishment_stage": [
                "actively managed",
                "implemented",
                "designated",
                "proposed/committed",
                "unknown",
            ],
            "country": ["ABNJ", "ABNJ", "ABNJ", "ABNJ", "ABNJ"],
            "zone_id": ["1", "2", "3", "4", "5"],
            "protection_mpaguide_level": ["high", "full", "low", "high", "unknown"],
            "name": ["A", "B", "C", "D", "E"],
            "wdpa_id": ["1", "2", "3", "4", "5"],
            "year": ["2017", "2018", "2019", "2020", "2021"],
        },
        geometry=gpd.GeoSeries.from_wkt(
            ["POINT (0 0)", "POINT (1 1)", "POINT (2 2)", "POINT (3 3)", "POINT (4 4)"]
        ),
        crs="EPSG:4326",
    )

    out = mask_mpatlas_protection_level(gdf)

    # Protection_mpaguide_level should be set to unknown if establishment stage is not actively 
    # managed or implemented
    assert out.iloc[0]["protection_mpaguide_level"] == "high"
    assert out.iloc[1]["protection_mpaguide_level"] == "full"
    assert out.iloc[2]["protection_mpaguide_level"] == "unknown"
    assert out.iloc[3]["protection_mpaguide_level"] == "unknown"
    assert out.iloc[4]["protection_mpaguide_level"] == "unknown"
