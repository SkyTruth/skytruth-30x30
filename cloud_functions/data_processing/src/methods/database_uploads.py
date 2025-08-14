from src.core.params import BUCKET, LOCATIONS_FILE_NAME
from src.utils.gcp import read_dataframe


def upload_locations(
    bucket: str = BUCKET, filename: str = LOCATIONS_FILE_NAME, verbose: bool = True
):
    locs_df = read_dataframe(bucket_name=bucket, filename=filename)
    locations = locs_df.to_dict(orient="records")
    print(locations)
