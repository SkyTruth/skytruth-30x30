import geopandas as gpd
import pytest


@pytest.fixture
def mock_related_countries_map():
    """
    Mock sample of the related countires json mapping
    """
    return {
        "ABNJ": ["ABNJ", "HS", "ATA"],
        "CHN": ["CHN", "HKG"],
        "CYP": ["CYP", "ZNC"],
        "HKG": ["HKG"],
        "USA*": ["PRI"],
        "FRA*": ["FRA", "MYT"],
        "COM*": ["COM", "MYT"],
    }


@pytest.fixture
def uploads_recorder():
    """
    Collect every (bucket, df, destination_blob) call to upload_gdf.
    """
    calls = []

    def _upload_gdf(bucket, df, destination_blob):
        # Serialize to GeoJSON for a light shape/column sanity check (emulates real upload payload)
        # We won't use GCS client here; just record.
        assert isinstance(df, gpd.GeoDataFrame)
        payload = df.to_json()  # not strictly necessary, but proves serializability
        calls.append(
            {
                "bucket": bucket,
                "df": df,
                "destination_blob": destination_blob,
                "payload_len": len(payload),
            }
        )

    return calls, _upload_gdf
