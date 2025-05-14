"""Class for managing API credentials and CRUD methods for the intenral strapi API"""

import os

import requests

from utils.logger import Logger


class Strapi:
    def __init__(self):
        self.logger = Logger()
        self.BASE_URL = os.environ.get("STRAPI_API_URL", "")
        self.USERNAME = os.environ.get("STRAPI_USERNAME", "")

        self.PASSWORD = os.environ.get("STRAPI_PASSWORD", None)
        self.token = self.login()

    
    # Authenitcate with the 30x30 API
    # The API requires passwrod based auth, after which it responds with a JWT
    # which must be included in the auth heaer of subsequent authenticated endpoints
    # this inlcudes all PUT and POST endpoints
    def login(self):
        try:
            if not self.PASSWORD:
                raise ValueError("No API password provided")
            response = requests.post(
                f"{self.BASE_URL}auth/local",
                data={"identifier": self.USERNAME, "password": self.PASSWORD},
                timeout=5,
            )

            response_data = response.json()
            return response_data.get("jwt")
        except Exception as excep:
            self.logger.error(
                {
                    "message": "Failed to authenticate with 30x30 API",
                    "exception": str(excep),
                }
            )
            
