import pickle

import pandas as pd
from google.cloud import storage

from src.core.params import (
    BUCKET,
    MPATLAS_META_FILE_NAME,
    PROJECT,
    WDPA_META_FILE_NAME,
    WDPA_PA_FILE_NAME,
)
from src.methods.protected_areas.protected_areas import (
    generate_protected_areas_table,
    make_pa_updates,
)
from src.utils.database import get_pas
from src.utils.logger import Logger

logger = Logger()


def generate_protected_areas_diff_table(
    wdpa_file_name: str = WDPA_META_FILE_NAME,
    mpatlas_file_name: str = MPATLAS_META_FILE_NAME,
    pa_file_name: str = WDPA_PA_FILE_NAME,
    bucket: str = BUCKET,
    project: str = PROJECT,
    verbose: bool = True,
):
    def clean_for_json(obj):
        import math

        """Recursively replace NaN/Infinity with None (-> JSON null)."""
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        elif isinstance(obj, str):
            if obj == "":
                return None
            return obj
        elif isinstance(obj, dict):
            return {k: clean_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [clean_for_json(v) for v in obj]
        else:
            return obj

    updated_pas = generate_protected_areas_table(
        wdpa_file_name=wdpa_file_name,
        mpatlas_file_name=mpatlas_file_name,
        bucket=bucket,
        verbose=verbose,
    )

    # Get the current database
    if verbose:
        logger.info({"message": "downloading current PA database"})
    current_db = get_pas()
    current_db_df = pd.DataFrame(current_db)
    if len(current_db_df) > 0:
        current_db_df["area"] = current_db_df["area"].apply(lambda x: float(x))
        current_db_df["coverage"] = current_db_df["coverage"].apply(
            lambda x: float(x) if x is not None else None
        )

    if verbose:
        logger.info({"message": f"current database length: {len(current_db)}"})

    if verbose:
        logger.info({"message": "finding database changes"})
    db_changes, change_cols = make_pa_updates(current_db_df, updated_pas, verbose=verbose)

    # Print which values have changed
    if verbose:
        for col in change_cols.columns:
            size = len(change_cols[change_cols[col]])
            if size > 0:
                logger.info({"message": f"{col}: {size} rows changed"})

    db_changes["new"] = clean_for_json(db_changes["new"])
    db_changes["changed"] = clean_for_json(db_changes["changed"])

    # Save archive DB changes
    source_file = "db_changes.pkl"
    with open(source_file, "wb") as f:
        pickle.dump(db_changes, f)

    client = storage.Client(project=project)
    bucket = client.bucket(bucket)
    blob = bucket.blob(pa_file_name)
    blob.upload_from_filename(source_file)

    if verbose:
        logger.info({"message": f"Uploaded {source_file} to gs://{bucket}/{pa_file_name}"})

    # return True if the database is being updated, otherwise False
    return len(db_changes["new"]) + len(db_changes["changed"]) > 0
