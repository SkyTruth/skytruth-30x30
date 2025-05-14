"""Unit tests for the database module."""
import unittest

from cloud_functions.data_processing.src.utils.Strapi import Strapi


class TestStrapi(unittest.TestCase):
  """Test the Database class."""
  def test_init__(self):
    """Test the __init__ method."""
    Strapi()
    assert True

if __name__ == '__main__':
    unittest.main()