import datetime
import os
import time

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import shape
from shapely.ops import transform
from tqdm.auto import tqdm

from src.core.params import (
    ARCHIVE_PROTECTED_SEAS_SITES_FILE_NAME,
    BUCKET,
    PROJECT,
    PROTECTED_SEAS_SITES_FILE_NAME,
)
from src.utils.gcp import duplicate_blob, read_parquet_from_gcs, upload_gdf
from src.utils.logger import Logger

logger = Logger()

BASE_URL = "https://map.navigatormap.org/api"


def force_2d(geom):
    return transform(lambda x, y, z=None: (x, y), geom)


def seed_protected_seas_sites(
    json_dir: str,  # local path for the one-time run
    last_updated_date: str = None,  # snapshot date (YYYY-MM-DD); defaults to today
    sites_file_name: str = PROTECTED_SEAS_SITES_FILE_NAME,
    archive_file_name: str = ARCHIVE_PROTECTED_SEAS_SITES_FILE_NAME,
    bucket: str = BUCKET,
    project: str = PROJECT,
    verbose: bool = True,
):
    os.environ["OGR_GEOJSON_MAX_OBJ_SIZE"] = "0"
    parts = [
        gpd.read_file(
            f"{json_dir}/Navigator_AllSites_GlobalEEZs_LFP{lfp}_071426.json", engine="pyogrio"
        )
        for lfp in tqdm(range(1, 6))
    ]
    gdf = gpd.GeoDataFrame(
        pd.concat(parts, ignore_index=True), geometry="geometry", crs=parts[0].crs
    )
    gdf = gdf[["SITE_ID", "site_name", "country", "lfp", "geometry"]].rename(
        columns={"SITE_ID": "site_id"}
    )

    # Stamp the snapshot date into the data itself, so the first update reads its
    # changed_since baseline straight from the sites file (no separate state file).
    gdf["last_updated"] = last_updated_date or datetime.date.today().isoformat()

    # Save the dated archive snapshot, then duplicate it to the current file.
    upload_gdf(bucket, gdf, archive_file_name, project_id=project, verbose=verbose)
    duplicate_blob(bucket, archive_file_name, sites_file_name, project_id=project, verbose=verbose)


def get_updated_site_index(
    changed_since: str,
    limit: int = 1000,
    sleep_seconds: float = 1.0,
) -> pd.DataFrame:
    rows = []
    page = 1

    while True:
        url = f"{BASE_URL}/search/"
        params = {
            "type": "sites_updated",
            "changed_since": changed_since,
            "limit": limit,
            "page": page,
            "export_bounds": "false",
        }

        response = requests.get(url, params=params, timeout=60)

        if response.status_code == 429:
            time.sleep(10)
            continue

        response.raise_for_status()
        data = response.json()

        sites = data.get("sites", [])
        if not sites:
            break

        rows.extend(sites)

        if len(sites) < limit:
            break

        page += 1
        time.sleep(sleep_seconds)

    return pd.DataFrame(rows)


def load_protected_seas_site(
    ps_id: str,
    keep_bounds: bool = True,
    max_retries: int = 5,
    base_sleep: float = 3.0,
) -> gpd.GeoDataFrame:
    url = f"{BASE_URL}/detail/"
    params = {
        "ps_id": ps_id,
        "export_boundaries": "true",
    }

    last_response = None

    for attempt in range(max_retries):
        response = requests.get(url, params=params, timeout=60)
        last_response = response

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            sleep_for = float(retry_after) if retry_after else base_sleep * (2**attempt)
            time.sleep(sleep_for)
            continue

        response.raise_for_status()
        data = response.json()

        if not data.get("site_boundary"):
            raise ValueError(f"No site_boundary found for ps_id={ps_id}")

        site_geom = force_2d(shape(data["site_boundary"]))
        attrs = {k: v for k, v in data.items() if k not in {"site_boundary", "bounds"}}

        if keep_bounds and data.get("bounds"):
            attrs["bounds_geometry"] = force_2d(shape(data["bounds"]))

        return gpd.GeoDataFrame([attrs], geometry=[site_geom], crs="EPSG:4326")

    raise requests.HTTPError(
        f"Exceeded retries for ps_id={ps_id}; "
        f"last status={getattr(last_response, 'status_code', None)}"
    )


def fetch_updated_site_details(
    changed_since: str,
    sleep_seconds: float = 5.0,
) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    updated_index = get_updated_site_index(changed_since=changed_since)

    if updated_index.empty:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326"), updated_index

    id_col = "ps_id" if "ps_id" in updated_index.columns else "site_id"
    changed_ids = updated_index[id_col].dropna().astype(str).drop_duplicates().tolist()

    gdfs = []
    failures = []

    for site_id in tqdm(changed_ids):
        try:
            gdfs.append(load_protected_seas_site(site_id))
        except Exception as exc:
            failures.append({"site_id": site_id, "error": str(exc)})
        time.sleep(sleep_seconds)

    if gdfs:
        changed_gdf = pd.concat(gdfs, ignore_index=True)
        changed_gdf = gpd.GeoDataFrame(changed_gdf, geometry="geometry", crs="EPSG:4326")
    else:
        changed_gdf = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    changed_gdf.attrs["failures"] = failures
    return changed_gdf, updated_index


def upsert_protected_seas_sites(
    local_gdf: gpd.GeoDataFrame,
    changed_gdf: gpd.GeoDataFrame,
    id_col: str = "site_id",
) -> gpd.GeoDataFrame:
    if changed_gdf.empty:
        return local_gdf

    changed = changed_gdf[["ps_id", "site_name", "country", "lfp", "geometry"]].rename(
        columns={"ps_id": "site_id"}
    )
    changed["lfp"] = changed["lfp"].astype(int)

    changed_ids = set(changed[id_col].astype(str))
    local_without_changed = local_gdf[~local_gdf[id_col].astype(str).isin(changed_ids)]

    updated = pd.concat([local_without_changed, changed], ignore_index=True)

    fishing_protection_mapping = {1: "less", 2: "less", 3: "moderately", 4: "highly", 5: "highly"}
    updated["fishing_protection"] = updated["lfp"].map(fishing_protection_mapping)
    return gpd.GeoDataFrame(updated, geometry="geometry", crs=local_gdf.crs)


def update_protected_seas_data(
    sites_file_name: str = PROTECTED_SEAS_SITES_FILE_NAME,
    archive_file_name: str = ARCHIVE_PROTECTED_SEAS_SITES_FILE_NAME,
    bucket: str = BUCKET,
    project: str = PROJECT,
    verbose: bool = True,
):
    current_gdf = read_parquet_from_gcs(bucket, sites_file_name, verbose=verbose)
    last_update_date = current_gdf["last_updated"].iloc[0]

    if verbose:
        logger.info({"message": f"fetching Protected Seas sites updated since {last_update_date}"})

    changed, _ = fetch_updated_site_details(last_update_date)

    if verbose:
        logger.info({"message": f"{len(changed)} site(s) changed since {last_update_date}"})
        if changed.attrs.get("failures"):
            logger.warning(
                {"message": "some sites failed to fetch", "failures": changed.attrs["failures"]}
            )

    updated = upsert_protected_seas_sites(current_gdf, changed)

    # Advance the baseline so the next run fetches changes since this run.
    today = datetime.date.today().isoformat()
    updated["last_updated"] = today

    # Save the dated archive snapshot, then duplicate it to the current file.
    if verbose:
        logger.info({"message": f"uploading protected seas to {archive_file_name}"})
    upload_gdf(bucket, updated, archive_file_name, project_id=project, verbose=verbose)

    if verbose:
        logger.info({"message": f"duplicating blob to {sites_file_name}"})
    duplicate_blob(bucket, archive_file_name, sites_file_name, project_id=project, verbose=verbose)

    if verbose:
        logger.info({"message": f"Protected Seas data updated; last_updated set to {today}"})
