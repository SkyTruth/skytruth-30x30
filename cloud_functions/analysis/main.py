import functions_framework
from flask.logging import default_handler
import logging

from src.connect_tcp import connect_tcp_socket
from src.analysis import get_locations_stats_terrestrial, get_locations_stats_marine

logger = logging.getLogger(__name__)
logger.addHandler(default_handler)
logger.setLevel(logging.DEBUG)
db = connect_tcp_socket()


@functions_framework.http
def index(request):
    """HTTP Cloud Function.
    Args:
        request (flask.Request): The request object.
        <https://flask.palletsprojects.com/en/1.1.x/api/#incoming-request-data>
    Returns:
        The response text, or any set of values that can be turned into a
        Response object using `make_response`
        <https://flask.palletsprojects.com/en/1.1.x/api/#flask.make_response>.
    Note:
        For more information on how Flask integrates with Cloud
        Functions, see the `Writing HTTP functions` page.
        <https://cloud.google.com/functions/docs/writing/http#http_frameworks>
    """
    try:
        # For more information about CORS and CORS preflight requests, see:
        # https://developer.mozilla.org/en-US/docs/Glossary/Preflight_request

        # Set CORS headers for the preflight request
        if request.method == "OPTIONS":
            # Allows GET requests from any origin with the Content-Type
            # header and caches preflight response for an 3600s
            headers = {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, PUT, POST, HEAD",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Max-Age": "3600",
            }

            return ("", 204, headers)

        # Set CORS headers for the main request
        headers = {"Access-Control-Allow-Origin": "*"}

        geometry = ({**request.args, **request.get_json()}).get("geometry", None)
        if not geometry:
            raise ValueError("geometry is required")

        funct = {
            "marine": get_locations_stats_marine,
            "terrestrial": get_locations_stats_terrestrial,
        }

        environment = ({**request.args, **request.get_json()}).get(
            "environment", "marine"
        )
        if environment not in funct.keys():
            raise ValueError("environment must be one of `marine` or `terrestrial`")

        return (funct[environment](db, geometry), 200, headers)

    except ValueError as e:
        logger.exception(str(e))
        return {"error": str(e)}, 400, headers
    except Exception as e:
        logger.exception(str(e))
        return {"error": str(e)}, 500, headers
