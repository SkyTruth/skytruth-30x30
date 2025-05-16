from dotenv import load_dotenv

# Need to load the env vars before importing the main handler
# to ensure they are available for the function
# This is especially important for local testing
load_dotenv(override=True)

from main import main as handler #noqa: E402,I001


def main(request):
    """
    Local entry point for the Cloud Function. This function is used for local testing
    and debugging. It loads environment variables from a .env file and calls the main
    handler function.
    """
    return handler(request)