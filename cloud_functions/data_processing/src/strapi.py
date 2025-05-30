"""Class for managing API credentials and CRUD methods for the intenral strapi API"""

import os

import requests
from datetime import datetime

from src.utils.logger import Logger


class Strapi:
    def __init__(self):
        self.logger = Logger()
        self.BASE_URL = os.environ.get("STRAPI_API_URL", "")
        self.USERNAME = os.environ.get("STRAPI_USERNAME", "")
        self.PASSWORD = os.environ.get("STRAPI_PASSWORD", None)
        self.pas_page = 1
        self.pas_per_page = 1000  # Default to 1000 PAs per page
        self.token = self.authenticate()
        self.default_headers = {"Content-Type": "application/json"}
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

    def get_pas(
        self, next_page: bool = True, page: int | None = None, page_size: int | None = None
    ) -> list[dict]:
        """
        Get all protected areas (PAs) from the API.

        Parameters
        ----------
        next_page : bool
            If True, will fetch the next page of the paginated results
        page : int, optional
            The page number to fetch. If None, and next_page=false will fetch the first page.
            This parameter is ignored if next_page is True.
        page_size : int, optional
            The number of results per page. If None, the default page size of 1000 will be used.
            If page_size is set and page is not set, it will fetch the first page with the specified page size.
            This effectivley resets the next_page back to the first page.

        Returns
        -------
        list[dict]
            A list of protected areas.
        Raises
        ------
        Exception
            If the request fails or the API returns an error.
        """
        try:
            if page_size is not None and page_size != self.pas_per_page:
                self.pas_per_page = page_size
                self.pas_page = 1

            if not next_page:
                self.pas_page = page if page else 1
               
            query_params = (
                "fields[]=name&fields[]=year&fields[]=wdpaid&fields[]=wdpa_p_id&fields[]=zone_id"
                "&fields[]=designation&fields[]=bbox&fields[]=coverage&populate[data_source][fields]=slug"
                "&populate[environment][fields]=slug&populate[mpaa_establishment_stage][fields]=slug"
                "&populate[location][fields]=code&populate[mpaa_protection_level][fields]=slug"
                "&populate[iucn_category][fields]=slug&populate[parent][fields]=id&populate[children][fields]=id"
                f"&pagination[pageSize]={self.pas_per_page}&pagination[page]={self.pas_page}"
            )
            response = requests.get(
                f"{self.BASE_URL}pas?{query_params}",
                headers={**self.default_headers},
                timeout=600,  # Wait ten minutes
            )
            response.raise_for_status()
            data = response.json()

            current_page = data.get("meta").get("pagination").get("page")
            self.pas_page = current_page + 1 if current_page else self.pas_page + 1

            return data
        except Exception as excep:
            self.logger.error(
                {
                    "message": "Failed to get protected areas",
                    "exception": str(excep),
                }
            )
            raise excep

    def update_pas(self, pas: list[dict]) -> dict:
        """
        Bulk update existing PAs
        """
        try:
            response = requests.put(
                f"{self.BASE_URL}pas",
                headers={**self.auth_headers, **self.default_headers},
                timeout=600,  # Wait ten minutes
                data={"data": pas},
            )
            return response.json()
        except Exception as excep:
            self.logger.error(
                {
                    "message": "Failed to create protected areas",
                    "exception": str(excep),
                }
            )
            raise excep

    def create_pas(self, pas: list[dict]) -> dict:
        """
        Bulk create existing PAs
        """
        try:
            response = requests.post(
                f"{self.BASE_URL}pas",
                headers={**self.auth_headers, **self.default_headers},
                timeout=600,  # Wait ten minutes
                data={"data": pas},
            )
            return response.json()
        except Exception as excep:
            self.logger.error(
                {
                    "message": "Failed to update protected areas",
                    "exception": str(excep),
                }
            )
            raise excep

    def delete_pas(self, pas: list[int]) -> dict:
        """
        Bulk delete existing PAs
        """
        try:
            response = requests.patch(
                f"{self.BASE_URL}pas",
                headers={**self.auth_headers, **self.default_headers},
                timeout=600,  # Wait ten minutes
                data={"data": pas},
            )
            return response.json()
        except Exception as excep:
            self.logger.error(
                {
                    "message": "Failed to delete protected areas",
                    "exception": str(excep),
                }
            )
            raise excep

    def upsert_protection_coverage_stats(self, stats: list[dict], year: int | None = None) -> dict:
        """
        Add protection coverage stats for a given year.
        Parameters
        ----------
        year : int
            The year for which the stats are being added.
        stats : list[dict]
            The protection coverage stats to be added.
        Returns
        -------
        dict
            The response from the API.
        Raises
        ------
        Exception
            If the request fails or the API returns an error.
        """
        try:
            if year is None:
                year = int(datetime.now().strftime("%Y"))

            response = requests.post(
                f"{self.BASE_URL}protection-coverage-stats/{year}",
                headers={**self.auth_headers, **self.default_headers},
                timeout=600,  # Wait ten minutes
                data={"data": stats},
            )
            return response.json()
        except Exception as excep:
            self.logger.error(
                {
                    "message": "Failed to add protection coverage stats",
                    "exception": str(excep),
                }
            )
            raise excep

    def upsert_mpaa_protection_level_stats(self, stats: list[dict]) -> dict:
        """
        Upsert MPAA protection level stats.

        Parameters
        ----------
        stats : list[dict]
            The MPAA protection level stats to be upserted.

        Returns
        -------
        dict
            The response from the API.
        """
        try:
            response = requests.post(
                f"{self.BASE_URL}mpaa-protection-level-stats",
                headers={**self.auth_headers, **self.default_headers},
                timeout=600,  # Wait ten minutes
                data={"data": stats},
            )
            return response.json()
        except Exception as excep:
            self.logger.error(
                {
                    "message": "Failed to upsert MPAA protection level stats",
                    "exception": str(excep),
                }
            )
            raise excep

    def upsert_fishing_protection_level_stats(self, stats: list[dict]) -> dict:
        """
        Upsert fishing protection level stats.

        Parameters
        ----------
        stats : list[dict]
            The fishing protection level stats to be upserted.

        Returns
        -------
        dict
            The response from the API.
        """
        try:
            response = requests.post(
                f"{self.BASE_URL}fishing-protection-level-stats",
                headers={**self.auth_headers, **self.default_headers},
                timeout=600,  # Wait ten minutes
                data={"data": stats},
            )
            return response.json()
        except Exception as excep:
            self.logger.error(
                {
                    "message": "Failed to upsert fishing protection level stats",
                    "exception": str(excep),
                }
            )
            raise excep

    def upsert_habitat_stats(self, stats: list[dict], year: int | None = None) -> dict:
        """
        Upsert habitat stats.

        Parameters
        ----------
        stats : list[dict]
            The habitat stats to be upserted.

        Returns
        -------
        dict
            The response from the API.

        Raises
        ------
        Exception
            If the request fails or the API returns an error.
        """
        try:
            if year is None:
                year = int(datetime.now().strftime("%Y"))
            response = requests.post(
                f"{self.BASE_URL}habitat-stats/{year}",
                headers={**self.auth_headers, **self.default_headers},
                timeout=600,  # Wait ten minutes
                data={"data": stats},
            )
            return response.json()
        except Exception as excep:
            self.logger.error(
                {
                    "message": "Failed to upsert habitat stats",
                    "exception": str(excep),
                }
            )
            raise excep
