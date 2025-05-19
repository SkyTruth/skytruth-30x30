"""Class for managing API credentials and CRUD methods for the intenral strapi API"""

import os

import requests

from src.utils.logger import Logger


class Strapi:
    def __init__(self):
        self.logger = Logger()
        self.BASE_URL = os.environ.get("STRAPI_API_URL", "")
        self.USERNAME = os.environ.get("STRAPI_USERNAME", "")

        self.PASSWORD = os.environ.get("STRAPI_PASSWORD", None)
        self.token = self.authenticate()
        self.default_headers = {'Content-Type': 'application/json'}
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}

    # Authenitcate with the 30x30 API
    # The API requires passwrod based auth, after which it responds with a JWT
    # which must be included in the auth heaer of subsequent authenticated endpoints
    # this inlcudes all PUT and POST endpoints
    def authenticate(self) -> str:
        """Authenticate with the 30x30 API and return the JWT token."""
        try:
            if not self.PASSWORD:
                raise ValueError("No API password provided")
            response = requests.post(
                f"{self.BASE_URL}auth/local",
                data={"identifier": self.USERNAME, "password": self.PASSWORD},
                timeout=5,
            )
            response.raise_for_status()
            response_data = response.json()
            return response_data.get("jwt")
        except Exception as excep:
            self.logger.error(
                {
                    "message": "Failed to authenticate with 30x30 API",
                    "exception": str(excep),
                }
            )
            raise excep
        
    def _get_pa(self, properties: dict[str, str]) -> int | None:
        """
        Get the protected area from the 30x30 API.
        
        Parameters
        ----------
        properties : dict[str, str]
            The properties that define the PA to be used as filters.

        Returns
        -------
        int
            The ID of the protected area.
        """
        try:
            filters = self._make_query_filters(properties)
            response = requests.get(
                f"{self.BASE_URL}pas?{filters}",
                headers={**self.auth_headers, **self.default_headers},
                timeout=5,
            )
            response.raise_for_status()
            response_data = response.json()
            if len(response_data.data) > 1:
                self.logger.warning(
                    {
                        "message": "Multiple protected areas found with the same properties",
                        "properties": properties,
                    }
                )
                return None
            return response.json()
        except Exception as excep:
            self.logger.error(
                {
                    "message": "Failed to get protected area from 30x30 API",
                    "exception": str(excep),
                }
            )
            raise excep
        
    def _make_query_filters(self, filters: dict) -> str:
        """
        Make a query string from the filters dictionary.
        
        Parameters
        ----------
        filters : dict
            The filters to apply to the query.

        Returns
        -------
        str
            The query string.
        """
        return "&".join([f"filters[{key}][$eq]={value}" for key, value in filters.items() 
            if value is not None])
