"""Unit tests for the database module."""

from unittest.mock import patch

import pytest
import responses
from requests.exceptions import HTTPError

from src.strapi import Strapi


@pytest.fixture(autouse=True)
def set_common_env(monkeypatch):
    """Set common environment variables for all tests."""
    monkeypatch.setenv("STRAPI_API_URL", "https://test.com/api/")
    monkeypatch.setenv("STRAPI_USERNAME", "test_user")
    monkeypatch.setenv("STRAPI_PASSWORD", "test_password")
    monkeypatch.setenv("PROJECT", "test_project")

    yield

@pytest.fixture()
def mock_authenticate():
    """Mock the authenticate method."""
    with patch("src.strapi.Strapi.authenticate", return_value='jwt') as mock_authenticate:
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


@patch("src.strapi.Logger.error")
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
@patch("src.strapi.Logger.error")
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


def test__make_query_filters(mock_authenticate):
    """Test the _make_query_filters method."""
    strapi = Strapi()
    properties = {"name": "test_name", "type": "test_type"}
    expected = 'filters[name][$eq]=test_name&filters[type][$eq]=test_type'
    filters = strapi._make_query_filters(properties)
    assert filters == expected

def test__make_query_filters_none_values(mock_authenticate):
    """Test the _make_query_filters method ignores None fields."""
    strapi = Strapi()
    properties = {"name": None, "type": "test_type", "other": None}
    expected = 'filters[type][$eq]=test_type'
    filters = strapi._make_query_filters(properties)
    assert filters == expected