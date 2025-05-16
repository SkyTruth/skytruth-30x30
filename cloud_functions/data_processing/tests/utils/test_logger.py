from unittest.mock import patch

import pytest

from src.utils.logger import Logger


@pytest.fixture(autouse=True)
def set_common_env(monkeypatch):
    """Set common environment variables for all tests."""
    monkeypatch.setenv("PROJECT", "test_project")


@patch("builtins.print")
def test_log_info(mock_print):
    """Test the info method of the Logger class with a request object."""
    logger = Logger()
    logger.info({"message": "test info message"})
    mock_print.assert_called_once_with('{"message": "test info message", "severity": "INFO"}')


@patch("builtins.print")
def test_log_warning(mock_print):
    """Test the info method of the Logger class with a request object."""
    logger = Logger()
    logger.warning({"message": "test info message"})
    mock_print.assert_called_once_with('{"message": "test info message", "severity": "WARNING"}')


@patch("builtins.print")
def test_log_error(mock_print):
    """Test the info method of the Logger class with a request object."""
    logger = Logger()
    logger.error({"message": "test info message"})
    mock_print.assert_called_once_with('{"message": "test info message", "severity": "ERROR"}')
