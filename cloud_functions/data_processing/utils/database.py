"""Class for managing API credentials and CRUD methods for the intenral strapi API"""

import os

import requests


class Strapi:
    def __init__(self):
        self.ENV = "local"  # local | dev | prod
        self.PROJECT_ID = "x30-399415"
        self.USER_ID = "data_write"

        self.BASE_URLS = {
            "local": "http://localhost:1337/api/",
            "dev": "https://30x30-dev.skytruth.org/cms/api/",
            "prod": "https://30x30.skytruth.org/cms/api/",
        }

        self.api_password = os.environ.get("API_PASSWORD")
        self.token = self.login()

    # Authenitcate with the 30x30 API
    # The API requires passwrod based auth, after which it responds with a JWT
    # which must be included in the auth heaer of subsequent authenticated endpoints
    # this inlcudes all PUT and POST endpoints
    def login(self):
        try:
            if not self.api_password:
                raise ValueError("No API password provided")
            response = requests.post(
                f"{self.BASE_URLS.get(self.ENV)}auth/local",
                data={"identifier": self.USER_ID, "password": self.api_password},
            )

            response_data = response.json()
            return response_data.get("jwt")
        except Exception as excep:
            print("Failed to authenticate with 30x30 API ", excep)

    def fishing_protection_stats(self, location: str) -> dict[str:any]:
        """"""
        try:
            path = (
                f"locations?filters[code]={location}"
                "&populate[fishing_protection_level_stats][populate][fishing_protection_level]"
                "=*&fields=code"
            )
            response = requests.get(
                f"{self.BASE_URLS.get(self.ENV)}{path}",
            )
            response_data = response.json()
            return response_data.get("data")
        except Exception as excep:
            print(f"Failed to get fishing stats for location {location} ", excep)
