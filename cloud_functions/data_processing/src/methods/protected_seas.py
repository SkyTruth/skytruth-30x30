import datetime
import time

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import shape
from shapely.ops import transform
from tqdm.auto import tqdm

from src.core.params import (
    BUCKET,
    PROJECT,
    PROTECTED_SEAS_LAST_UPDATED_FILE_NAME,
    PROTECTED_SEAS_SITES_FILE_NAME,
)
from src.utils.gcp import read_json_from_gcs, upload_gdf, write_json_to_gcs
from src.utils.logger import Logger

logger = Logger()

BASE_URL = "https://map.navigatormap.org/api"


def force_2d(geom):
    return transform(lambda x, y, z=None: (x, y), geom)


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
    id_col: str = "ps_id",
) -> gpd.GeoDataFrame:
    if changed_gdf.empty:
        return local_gdf.copy()

    if id_col not in local_gdf.columns:
        raise ValueError(f"{id_col} not found in local_gdf")

    if id_col not in changed_gdf.columns:
        alt_id_col = "site_id" if "site_id" in changed_gdf.columns else None
        if alt_id_col:
            changed_gdf = changed_gdf.rename(columns={alt_id_col: id_col})
        else:
            raise ValueError(f"{id_col} not found in changed_gdf")

    local_without_changed = local_gdf[
        ~local_gdf[id_col].astype(str).isin(changed_gdf[id_col].astype(str))
    ].copy()

    updated = pd.concat([local_without_changed, changed_gdf], ignore_index=True)
    return gpd.GeoDataFrame(updated, geometry="geometry", crs=local_gdf.crs)


def update_protected_seas_data(
    sites_file_name: str = PROTECTED_SEAS_SITES_FILE_NAME,
    last_updated_file_name: str = PROTECTED_SEAS_LAST_UPDATED_FILE_NAME,
    bucket: str = BUCKET,
    project: str = PROJECT,
    verbose: bool = True,
):
    last_updated_meta = read_json_from_gcs(bucket, last_updated_file_name, verbose=verbose)
    last_update_date = last_updated_meta["last_updated"]

    if verbose:
        logger.info({"message": f"fetching Protected Seas sites updated since {last_update_date}"})
    current = read_json_from_gcs(bucket, sites_file_name, verbose=verbose)
    current_gdf = gpd.GeoDataFrame.from_features(current["features"], crs="EPSG:4326")

    changed, _ = fetch_updated_site_details(last_update_date)

    if verbose:
        logger.info({"message": f"{len(changed)} site(s) changed since {last_update_date}"})
        if changed.attrs.get("failures"):
            logger.warning(
                {"message": "some sites failed to fetch", "failures": changed.attrs["failures"]}
            )

    updated = upsert_protected_seas_sites(current_gdf, changed)

    upload_gdf(bucket, updated, sites_file_name, project_id=project, verbose=verbose)

    today = datetime.date.today().isoformat()
    write_json_to_gcs(bucket, last_updated_file_name, {"last_updated": today}, verbose=verbose)

    if verbose:
        logger.info({"message": f"Protected Seas data updated; last_updated set to {today}"})
