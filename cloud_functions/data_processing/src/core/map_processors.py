import os
import subprocess
from time import sleep

import boto3
import requests
from tqdm import tqdm

from src.core.map_params import MAPBOX_BASE_URL
from src.utils.logger import Logger

logger = Logger()


def mbtileGeneration(
    input_file: str,
    output_file: str,
    verbose: bool = False,
) -> None:
    """
        generate mbtiles file from geomtry file

        Args:
            input_file (Path): The path to the file.
            output_file (Union[Path, None], optional): The path to the output file.
    The default is None.
            update (bool, optional): Whether to update the mbtiles file. The default is False.

        Returns:
            Path: The path to the output file.

    """
    try:
        if verbose:
            print(f"Creating mbtiles file from {input_file}...")
        # https://github.com/mapbox/tippecanoe
        # -zg: Automatically choose a maxzoom that should be sufficient to clearly distinguish the
        #   features and the detail within each feature
        # -f: Deletes existing files in location with the same name
        # -P: reads the geojson in parallel if the file is newline delimited
        # -o: The following argurment is hte output path
        # -ae:  Increase the maxzoom if features are still being dropped at that zoom level
        subprocess.run(
            f"tippecanoe -zg -f -P -o {output_file} -ae {input_file}",
            shell=True,
            check=True,
        )

        if verbose:
            print(f"mbtiles file created and written to {output_file}")

    except Exception as e:
        logger.error(f"Error generating mbtiles file from {input_file}")
        raise e


def uploadToMapbox(
    source: str,
    tileset_id: str,
    display_name: str,
    username: str,
    token: str,
    verbose: bool = False,
) -> None:
    """
    Upload the mbtiles file to Mapbox. Following the steps outlined here:
    https://docs.mapbox.com/api/maps/uploads/

    In general the flow is:
    1. Get S3 credentials from Mapbox
    2. Upload the file to MapBox's S3
    3. Load hte tilset from S3 into MapBox
    """
    if verbose:
        print("Uploading to Mapbox...")

    mapboxCredentials = getS3Credentials(username, token)
    setS3Credentials(mapboxCredentials)

    uploadToS3(source, mapboxCredentials, verbose)

    loadToMapbox(username, token, mapboxCredentials, tileset_id, display_name)


def getS3Credentials(user: str, token: str) -> dict:
    response = requests.get(f"{MAPBOX_BASE_URL}{user}/credentials?access_token={token}")
    response.raise_for_status()
    return response.json()


def setS3Credentials(credentials: dict) -> None:
    """
    Set needed aws env variables to allow boto3 to authetnicate to S3
    """
    os.environ["AWS_ACCESS_KEY_ID"] = credentials["accessKeyId"]
    os.environ["AWS_SECRET_ACCESS_KEY"] = credentials["secretAccessKey"]
    os.environ["AWS_SESSION_TOKEN"] = credentials["sessionToken"]


def uploadToS3(source: str, credentials: dict, verbose: bool = False) -> None:
    """ """
    if verbose:
        print("Uploading to S3...")

    s3 = boto3.client("s3")
    s3.upload_file(source, credentials["bucket"], credentials["key"])

    if verbose:
        print("Upload to S3 complete.")


def loadToMapbox(
    username: str,
    token: str,
    credentials: dict,
    tileset_name: str,
    display_name=None,
    verbose: bool = False,
):
    def uploadStatus(upload_id):
        url = f"{MAPBOX_BASE_URL}{username}/{upload_id}?access_token={token}"
        response = requests.get(url)

        response.raise_for_status()

        if response.json()["error"]:
            raise Exception(response.json()["error"])

        return response.json()["complete"], response.json()["progress"]

    if not display_name:
        display_name = tileset_name

    # Create the tileset upload
    url = f"{MAPBOX_BASE_URL}{username}?access_token={token}"
    body = {
        "url": f"https://{credentials.get('bucket', '')}.s3.amazonaws.com/{credentials.get('key')}",
        "tileset": f"{username}.{tileset_name}",
        "name": f"{display_name}",
    }
    response = requests.post(url, json=body)
    response.raise_for_status()

    upload_id = response.json()["id"]
    # Progress bar to show upload status in Mapbox
    with tqdm(total=100) as pbar:
        pbar.set_description("Linking tileset to Mapbox")
        pbar.update(0)

        # Check the upload status
        status = False
        while status is False:
            sleep(5)
            status, progress = uploadStatus(upload_id)
            pbar.update(round(progress * 100))

    return status
