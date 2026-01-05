"""Class for managing API credentials and CRUD methods for the intenral strapi API"""

import os
import time
from datetime import datetime

import requests

from src.utils.logger import Logger


class Strapi:
    def __init__(self):
        self.logger = Logger()
        self.BASE_URL = os.environ.get("STRAPI_API_URL", "")
        self.USERNAME = os.environ.get("STRAPI_USERNAME", "")
        self.PASSWORD = os.environ.get("STRAPI_PASSWORD", None)
        self.token = self.authenticate()
        self.default_headers = {"Content-Type": "application/json"}
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}

    # Authenitcate with the 30x30 API
    # The API requires passwrod based auth, after which it responds with a JWT
    # which must be included in the auth heaer of subsequent authenticated endpoints
    # this inlcudes all PUT and POST endpoints
    def authenticate(self) -> str:
        """Authenticate with the 30x30 API and return the JWT token."""

        attempt = 0
        try:
            attempt += 1
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
            if attempt < 3 and response.status_code != 401:
                self.logger.warning(
                    {
                        "message": "Error attempting to authenticate with 30x30 API, retrying...",
                        "exception": str(excep),
                    }
                )
                time.sleep(10)
            else:
                self.logger.error(
                    {
                        "message": "Failed to authenticate with 30x30 API",
                        "exception": str(excep),
                        "status_code": response.status_code,
                    }
                )
            raise excep

    def upsert_pas(self, pas: list[dict]) -> dict:
        """
        Bulk upsert existing PAs

          Parameters
        -----------
            pas: list[dict]
                list of Pas to either create or update, if the dict has an id field
                the pa with that databgase id will be updated with the new data, otherwise
                a new pa will be created.

                Sample data, required fields marked with *

            [
                {
                    id: 33,
                    "name": "aba", *
                    "area": 54819.04, *
                    "year": 2022,
                    "bbox": [
                        -88.987016503,
                        4.529014728999982,
                        -86.367012456,
                        6.237020961999974
                    ], *
                    "coverage": 9.15, *
                    "wdpaid": 170,
                    "wdpa_p_id": "2_a",
                    "zone_id": null,
                    "designation": "National Park",
                    "protection_status": "pa", *
                    "environment": "terrestrial", *
                    "location": "CRI", *
                    "data_source": "protected-planet", *
                    "mpaa_protection_level": null,
                    "iucn_category": "V",
                    "mpaa_establishment_stage": null,
                    "children": [
                        {
                            "wdpaid": 162,
                            "wdpa_p_id": "162_a",
                            "zone_id": 3,
                            "environment": "terrestrial"
                    }
                    ],
                    "parent": {
                        "wdpaid": 170,
                        "wdpa_p_id": "2_a",
                        "zone_id": 3,
                        "environment": "terrestrial"
                    }
                },
                ...
            ]
        """
        try:
            response = requests.post(
                f"{self.BASE_URL}pas",
                headers={**self.auth_headers, **self.default_headers},
                timeout=2600,  # Wait 60 minutes
                json={"data": pas},
            )
            return response.json()
        except Exception as excep:
            self.logger.error(
                {
                    "message": "Failed to upsert protected areas",
                    "exception": str(excep),
                }
            )
            raise excep

    def delete_pas(self, pas: list[int]) -> dict:
        """
        Bulk delete existing PAs

        Parameters
        -----------
            pas: list[int]
                list of PA database ids to be deleted,
                relational fields will also be deleted
        """
        try:
            response = requests.patch(
                f"{self.BASE_URL}pas",
                headers={**self.auth_headers, **self.default_headers},
                timeout=3600,  # Wait 60 minutes
                json={"data": {"method": "DELETE", "ids": pas}},
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
                json={"data": stats},
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
                json={"data": stats},
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
                json={"data": stats},
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
                json={"data": stats},
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

    def upsert_locations(self, locations: list[dict], options: dict | None = None) -> dict:
        """
        Upsert locations.

        Parameters
        ----------
        locations : list[dict]
            List of dictionaries containing all the metadata to be upserted with the locations.
            If the location is to be created it must contain the following keys:
            - code: The ISO3 code of the location.
            - name: The name of the location in Egnlish
            - name_es: The name of the location in Spanish
            - name_fr: The name of the location in French
            - name_pt: The name of the location in Portuguese
            - total_marine_area: The total marine area of the location in square kilometers.
            - total_land_area: The total land area of the location in square kilometers.
            - type: The location type, e.g. "country", "territory", "region", etc. defaults to
                "territory"

            If the location is to be updated it must contain the following keys:
            - code: The ISO3 code of the location.

            In either case otional fields are
            - marine_bounds: list of the bbox of the marine area
            - terrestiral_bounds: list of the bbox of the terrestrial area
            - marine_target: int representing the target percent for marine protection
            - marine_target_year: int represeting the target year for marine protection goal
        Returns
        -------
        dict
            The response from the API.
        """
        try:
            if options is None:
                options = {}

            response = requests.post(
                f"{self.BASE_URL}locations",
                headers={**self.auth_headers, **self.default_headers},
                timeout=600,  # Wait ten minutes
                json={"data": locations, "options": options},
            )
            return response.json()
        except Exception as excep:
            self.logger.error(
                {
                    "message": "Failed to upsert locations",
                    "exception": str(excep),
                }
            )
            raise excep
