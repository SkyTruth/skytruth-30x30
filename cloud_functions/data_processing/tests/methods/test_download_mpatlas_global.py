from unittest.mock import patch

import pytest

import src.methods.download_and_process as download

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def api_response():
    return {
        "analysis_date": "2026-04-16",
        "eez_km2": 140547921,
        "highseas_km2": 222498835,
        "total_km2": 363046756,
        "mpaguide_status": {
            "total": [
                {"key": "if", "km2": 6055530, "has_points": False, "zones": 310, "percent": 1.67},
                {"key": "ih", "km2": 6226802, "has_points": False, "zones": 182, "percent": 1.72},
                {"key": "il", "km2": 1996249, "has_points": False, "zones": 274, "percent": 0.55},
            ]
        },
    }


@patch("src.methods.download_and_process.duplicate_blob")
@patch("src.methods.download_and_process.save_file_bucket")
@patch("src.methods.download_and_process.requests.get")
def test_get_request(mock_get, mock_save, mock_duplicate, api_response):
    # Configure the mock response
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = api_response

    download.download_mpatlas_global()

    assert mock_save.call_args[0][0] == mock_get.return_value.content
