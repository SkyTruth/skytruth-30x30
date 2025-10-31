"""Unit tests for the database module."""

from datetime import datetime
from unittest.mock import patch

import pytest
import responses
from requests.exceptions import HTTPError

from src.core.strapi import Strapi

BASE_URL = "https://test.com/api/"


@pytest.fixture(autouse=True)
def set_common_env(monkeypatch):
    """Set common environment variables for all tests."""
    monkeypatch.setenv("STRAPI_API_URL", BASE_URL)
    monkeypatch.setenv("STRAPI_USERNAME", "test_user")
    monkeypatch.setenv("STRAPI_PASSWORD", "test_password")
    monkeypatch.setenv("PROJECT", "test_project")
    yield


@pytest.fixture()
def mock_authenticate():
    """Mock the authenticate method."""
    with patch("src.core.strapi.Strapi.authenticate", return_value="jwt") as mock_authenticate:
        yield mock_authenticate


def test_init__(mock_authenticate):
    """Test the __init__ method."""
    Strapi()
    mock_authenticate.assert_called_once()


@responses.activate
def test_login_success():
    """Test successful API authentication"""
    responses.add(
        responses.POST,
        "https://test.com/api/auth/local",
        json={"jwt": "test_token"},
        status=200,
    )
    strapi = Strapi()
    assert strapi.token == "test_token"


@patch("src.core.strapi.Logger.error")
def test_login_no_pwd_failure(mock_logger_error, monkeypatch):
    """Test failure to authenticate with no password"""
    monkeypatch.setenv("STRAPI_PASSWORD", "")
    with pytest.raises(ValueError, match="No API password provided"):
        Strapi()

    mock_logger_error.assert_called_once_with(
        {
            "message": "Failed to authenticate with 30x30 API",
            "exception": "No API password provided",
        }
    )


@responses.activate
@patch("src.core.strapi.Logger.error")
def test_login_failure_bad_auth(mock_logger_error):
    """Test failure to authenticate with bad credentials"""

    responses.add(
        responses.POST,
        "https://test.com/api/auth/local",
        status=401,
    )
    with pytest.raises(HTTPError, match=r".*Unauthorized.*"):
        Strapi()

    mock_logger_error.assert_called_once()


@responses.activate
def test_upsert_pas_success(mock_authenticate):
    api = Strapi()
    payload = {"data": [{"id": 10}]}
    responses.add(
        responses.POST,
        BASE_URL + "pas",
        json=payload,
        status=200,
    )

    result = api.upsert_pas([{"id": 10}])
    assert result == payload

    assert len(responses.calls) == 1
    call = responses.calls[0].request
    assert call.method == "POST"
    assert call.url == BASE_URL + "pas"


@patch("src.core.strapi.Logger.error")
@patch("src.core.strapi.requests.post", side_effect=HTTPError("update-fail"))
def test_update_pas_failure(mock_req, mock_error, mock_authenticate):
    api = Strapi()
    with pytest.raises(HTTPError):
        api.upsert_pas([{"id": 1}])

    mock_error.assert_called_once()
    assert "Failed to upsert protected areas" in mock_error.call_args[0][0]["message"]


@responses.activate
def test_create_pas_success(mock_authenticate):
    api = Strapi()
    payload = {"data": [{"foo": "bar"}]}
    responses.add(
        responses.POST,
        BASE_URL + "pas",
        json=payload,
        status=200,
    )

    result = api.upsert_pas([{"foo": "bar"}])
    assert result == payload

    assert len(responses.calls) == 1
    call = responses.calls[0].request
    assert call.method == "POST"
    assert call.url == BASE_URL + "pas"


@responses.activate
def test_delete_pas_success(mock_authenticate):
    api = Strapi()
    payload = {"data": [1, 2, 3]}
    responses.add(
        responses.PATCH,
        BASE_URL + "pas",
        json=payload,
        status=200,
    )

    result = api.delete_pas([1, 2, 3])
    assert result == payload

    assert len(responses.calls) == 1
    call = responses.calls[0].request
    assert call.method == "PATCH"
    assert call.url == BASE_URL + "pas"


@patch("src.core.strapi.Logger.error")
@patch("src.core.strapi.requests.patch", side_effect=HTTPError("delete-fail"))
def test_delete_pas_failure(mock_req, mock_error, mock_authenticate):
    api = Strapi()
    with pytest.raises(HTTPError):
        api.delete_pas([1])

    mock_error.assert_called_once()
    assert "Failed to delete protected areas" in mock_error.call_args[0][0]["message"]


@responses.activate
def test_upsert_protection_coverage_stats_success(mock_authenticate):
    api = Strapi()
    year = 2022
    stats = [{"cov": 75}]
    payload = {"data": stats}
    url = f"{BASE_URL}protection-coverage-stats/{year}"

    responses.add(
        responses.POST,
        url,
        json=payload,
        status=200,
    )

    result = api.upsert_protection_coverage_stats(stats, year)
    assert result == payload

    assert len(responses.calls) == 1
    call = responses.calls[0].request
    assert call.method == "POST"
    assert call.url == url


@responses.activate
def test_upsert_protection_coverage_stats_no_year_provided(mock_authenticate):
    api = Strapi()
    year = int(datetime.now().strftime("%Y"))
    stats = [{"cov": 75}]
    payload = {"data": stats}
    url = f"{BASE_URL}protection-coverage-stats/{year}"

    responses.add(
        responses.POST,
        url,
        json=payload,
        status=200,
    )

    result = api.upsert_protection_coverage_stats(stats)
    assert result == payload

    assert len(responses.calls) == 1
    call = responses.calls[0].request
    assert call.method == "POST"
    assert call.url == url


@patch("src.core.strapi.Logger.error")
@patch("src.core.strapi.requests.post", side_effect=HTTPError("stats-fail"))
def test_upsert_protection_coverage_stats_failure(mock_req, mock_error, mock_authenticate):
    api = Strapi()
    with pytest.raises(HTTPError):
        api.upsert_protection_coverage_stats([{"a": 1}], 2023)

    mock_error.assert_called_once()
    assert "Failed to add protection coverage stats" in mock_error.call_args[0][0]["message"]


@responses.activate
def test_upsert_mpaa_protection_level_stats_success(mock_authenticate):
    api = Strapi()
    stats = [{"lvl": 1}]
    payload = {"data": stats}

    responses.add(
        responses.POST,
        BASE_URL + "mpaa-protection-level-stats",
        json=payload,
        status=200,
    )

    result = api.upsert_mpaa_protection_level_stats(stats)
    assert result == payload

    assert len(responses.calls) == 1
    call = responses.calls[0].request
    assert call.method == "POST"
    assert call.url == BASE_URL + "mpaa-protection-level-stats"


@patch("src.core.strapi.Logger.error")
@patch("src.core.strapi.requests.post", side_effect=HTTPError("mpaa-fail"))
def test_upsert_mpaa_protection_level_stats_failure(mock_req, mock_error, mock_authenticate):
    api = Strapi()
    with pytest.raises(HTTPError):
        api.upsert_mpaa_protection_level_stats([{"lvl": 2}])

    mock_error.assert_called_once()
    assert "Failed to upsert MPAA protection level stats" in mock_error.call_args[0][0]["message"]


@responses.activate
def test_upsert_fishing_protection_level_stats_success(mock_authenticate):
    api = Strapi()
    stats = [{"fish": 2}]
    payload = {"data": stats}

    responses.add(
        responses.POST,
        BASE_URL + "fishing-protection-level-stats",
        json=payload,
        status=200,
    )

    result = api.upsert_fishing_protection_level_stats(stats)
    assert result == payload

    assert len(responses.calls) == 1
    call = responses.calls[0].request
    assert call.method == "POST"
    assert call.url == BASE_URL + "fishing-protection-level-stats"


@patch("src.core.strapi.Logger.error")
@patch("src.core.strapi.requests.post", side_effect=HTTPError("fish-fail"))
def test_upsert_fishing_protection_level_stats_failure(mock_req, mock_error, mock_authenticate):
    api = Strapi()
    with pytest.raises(HTTPError):
        api.upsert_fishing_protection_level_stats([{"fish": 3}])

    mock_error.assert_called_once()
    assert (
        "Failed to upsert fishing protection level stats" in mock_error.call_args[0][0]["message"]
    )  # noqa E501


@responses.activate
def test_upsert_habitat_stats_success(mock_authenticate):
    api = Strapi()
    year = 1961
    stats = [{"h": 3}]
    payload = {"data": stats}

    responses.add(
        responses.POST,
        f"{BASE_URL}habitat-stats/{year}",
        json=payload,
        status=200,
    )

    result = api.upsert_habitat_stats(stats, year)
    assert result == payload

    assert len(responses.calls) == 1
    call = responses.calls[0].request
    assert call.method == "POST"
    assert call.url == f"{BASE_URL}habitat-stats/{year}"


@responses.activate
def test_upsert_habitat_stats_success_no_year_provided(mock_authenticate):
    api = Strapi()
    year = int(datetime.now().strftime("%Y"))
    stats = [{"h": 3}]
    payload = {"data": stats}

    responses.add(
        responses.POST,
        f"{BASE_URL}habitat-stats/{year}",
        json=payload,
        status=200,
    )

    result = api.upsert_habitat_stats(stats)
    assert result == payload

    assert len(responses.calls) == 1
    call = responses.calls[0].request
    assert call.method == "POST"
    assert call.url == f"{BASE_URL}habitat-stats/{year}"


@patch("src.core.strapi.Logger.error")
@patch("src.core.strapi.requests.post", side_effect=HTTPError("hab-fail"))
def test_upsert_habitat_stats_failure(mock_req, mock_error, mock_authenticate):
    api = Strapi()
    with pytest.raises(HTTPError):
        api.upsert_habitat_stats([{"h": 4}], 1872)

    mock_error.assert_called_once()
    assert "Failed to upsert habitat stats" in mock_error.call_args[0][0]["message"]


@responses.activate
def test_upsert_locations_success(mock_authenticate):
    api = Strapi()
    locations = [
        {
            "code": "USA",
            "name": "United States",
            "name_es": "Estados Unidos",
            "name_fr": "États-Unis",
            "name_pt": "Estados Unidos",
            "total_marine_area": 1000,
            "total_land_area": 9000,
            "type": "country",
        }
    ]
    payload = {"data": locations}
    responses.add(
        responses.POST,
        BASE_URL + "locations",
        json=payload,
        status=200,
    )

    result = api.upsert_locations(locations)
    assert result == payload

    assert len(responses.calls) == 1
    call = responses.calls[0].request
    assert call.method == "POST"
    assert call.url == BASE_URL + "locations"


@responses.activate
def test_upsert_locations_with_options(mock_authenticate):
    api = Strapi()
    locations = [
        {
            "code": "USA",
            "name": "United States",
            "type": "country",
        }
    ]
    options = {"fruit": "durian"}
    payload = {"data": locations, "options": options}

    responses.add(
        responses.POST,
        BASE_URL + "locations",
        json=payload,
        status=200,
    )

    result = api.upsert_locations(locations, options)
    assert result == payload

    assert len(responses.calls) == 1
    call = responses.calls[0].request
    assert call.method == "POST"
    assert call.url == BASE_URL + "locations"


@patch("src.core.strapi.Logger.error")
@patch("src.core.strapi.requests.post", side_effect=HTTPError("locations-fail"))
def test_upsert_locations_failure(mock_req, mock_error, mock_authenticate):
    api = Strapi()
    locations = [{"code": "CAN"}]
    with pytest.raises(HTTPError):
        api.upsert_locations(locations)

    mock_error.assert_called_once()
    assert "Failed to upsert locations" in mock_error.call_args[0][0]["message"]
