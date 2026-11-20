import datetime
import glob
import re
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
    PROTECTED_SEAS_BOUNDARY_MIN_INTERVAL_SECONDS,
    PROTECTED_SEAS_SITES_FILE_NAME,
    PROTECTED_SEAS_SITES_URL,
)
from src.utils.gcp import duplicate_blob, read_parquet_from_gcs, upload_gdf
from src.utils.logger import Logger

logger = Logger()

# Map Level of Fishing Protection (lfp) to our fishing_protection_level buckets.
# lfp=0 (unprotected) has no bucket and maps to NaN.
FISHING_PROTECTION_MAPPING = {1: "less", 2: "less", 3: "moderately", 4: "highly", 5: "highly"}

# Site attributes kept alongside geometry, fishing_protection_level, and last_updated
# Only ps_id and lfp are required, the others are kept when the source has them
SITE_ATTRIBUTE_COLUMNS = [
    "ps_id",
    "site_name",
    "country",
    "lfp",
    "wdpa_id",
    "type",
    "last_boundary_update",
]


def force_2d(geom):
    return transform(lambda x, y, z=None: (x, y), geom)


def _normalize_site_attributes(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize site attribute types in place and return `df`"""
    df["ps_id"] = df["ps_id"].astype(str)
    df["lfp"] = df["lfp"].astype(int)
    return df


def seed_protected_seas_sites(
    json_dir: str,  # local path for the one-time run
    sites_file_name: str = PROTECTED_SEAS_SITES_FILE_NAME,
    archive_file_name: str = ARCHIVE_PROTECTED_SEAS_SITES_FILE_NAME,
    bucket: str = BUCKET,
    project: str = PROJECT,
    verbose: bool = True,
):
    """Create the Protected Seas sites dataset from local Navigator exports.

    Combines every `*LFP[0-5]*.json` file in `json_dir`, keeps the
    `SITE_ATTRIBUTE_COLUMNS` the export has and maps LFP to a fishing protection
    level. The `MMDDYY` date in the first filename becomes `last_updated`, so the
    next update fetches changes since the export.

    Uploads a dated archive, then copies it to `sites_file_name`

    Args:
        json_dir: Local directory with the Navigator LFP GeoJSON exports
        sites_file_name: Cloud Storage object for the current dataset
        archive_file_name: Cloud Storage object for the dated snapshot
        bucket: Cloud Storage bucket for the datasets
        project: Google Cloud project for storage operations
        verbose: Whether storage helpers log progress

    Raises:
        FileNotFoundError: If `json_dir` has no LFP export files
        ValueError: If the first filename has no `MMDDYY` date
    """
    site_files = sorted(glob.glob(f"{json_dir}/*LFP[0-5]*.json"))
    if not site_files:
        raise FileNotFoundError(f"No Navigator LFP site files found in {json_dir}")

    date_match = re.search(r"_(\d{6})\.json$", site_files[0])
    if not date_match:
        raise ValueError(f"Could not parse a MMDDYY date from filename: {site_files[0]}")
    last_updated = datetime.datetime.strptime(date_match.group(1), "%m%d%y").date().isoformat()

    parts = [gpd.read_file(path, engine="pyogrio") for path in tqdm(site_files)]
    gdf = gpd.GeoDataFrame(
        pd.concat(parts, ignore_index=True), geometry="geometry", crs=parts[0].crs
    )
    gdf = gdf.rename(columns={"SITE_ID": "ps_id"})
    columns = [c for c in SITE_ATTRIBUTE_COLUMNS if c in gdf.columns]
    gdf = _normalize_site_attributes(gdf[[*columns, "geometry"]].copy())
    gdf["fishing_protection_level"] = gdf["lfp"].map(FISHING_PROTECTION_MAPPING)

    gdf["last_updated"] = last_updated

    # Save the dated archive, then copy it to the current file
    upload_gdf(bucket, gdf, archive_file_name, project_id=project, verbose=verbose)
    duplicate_blob(bucket, archive_file_name, sites_file_name, project_id=project, verbose=verbose)


def get_updated_site_index(
    changed_since: str,
    limit: int = 1000,
    sleep_seconds: float = 0.1,
) -> pd.DataFrame:
    rows = []
    page = 1

    while True:
        url = f"{PROTECTED_SEAS_SITES_URL}/search/"
        params = {
            "type": "sites_updated",
            "changed_since": changed_since,
            "limit": limit,
            "page": page,
            "export_bounds": "false",
            "include_inactive": "true",
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


class RateLimiter:
    """Space calls at least `min_interval` seconds apart.

    Navigator allows 5 Site Details calls per 10 seconds, so 2 seconds stays
    under the limit.
    """

    def __init__(self, min_interval: float):
        self.min_interval = min_interval
        self._next_allowed = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        if now < self._next_allowed:
            time.sleep(self._next_allowed - now)
            now = time.monotonic()
        self._next_allowed = now + self.min_interval


def load_protected_seas_site(
    ps_id: str,
    keep_bounds: bool = True,
    max_retries: int = 5,
    base_sleep: float = 3.0,
    rate_limiter: RateLimiter | None = None,
) -> gpd.GeoDataFrame:
    url = f"{PROTECTED_SEAS_SITES_URL}/detail/"
    params = {
        "ps_id": ps_id,
        "export_boundaries": "true",
    }

    last_response = None

    for attempt in range(max_retries):
        if rate_limiter is not None:
            rate_limiter.wait()
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
    min_interval: float = PROTECTED_SEAS_BOUNDARY_MIN_INTERVAL_SECONDS,
) -> tuple[gpd.GeoDataFrame, list[str], pd.DataFrame]:
    updated_index = get_updated_site_index(changed_since=changed_since)

    if updated_index.empty:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326"), [], updated_index

    if "status" in updated_index.columns:
        is_removed = updated_index["status"].astype(str).str.lower() == "removed"
    else:
        is_removed = pd.Series(False, index=updated_index.index)

    removed_ids = (
        updated_index.loc[is_removed, "ps_id"].dropna().astype(str).drop_duplicates().tolist()
    )
    changed_ids = (
        updated_index.loc[~is_removed, "ps_id"].dropna().astype(str).drop_duplicates().tolist()
    )

    logger.info(
        {
            "message": (
                f"{len(changed_ids)} changed and {len(removed_ids)} removed site(s) "
                f"since {changed_since}; fetching details for changed sites"
            )
        }
    )

    rate_limiter = RateLimiter(min_interval)
    gdfs = []
    failures = []

    for ps_id in tqdm(changed_ids):
        try:
            gdfs.append(load_protected_seas_site(ps_id, rate_limiter=rate_limiter))
        except Exception as exc:
            failures.append({"ps_id": ps_id, "error": str(exc)})

    if gdfs:
        changed_gdf = pd.concat(gdfs, ignore_index=True)
        changed_gdf = gpd.GeoDataFrame(changed_gdf, geometry="geometry", crs="EPSG:4326")
    else:
        changed_gdf = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    changed_gdf.attrs["failures"] = failures
    return changed_gdf, removed_ids, updated_index


def upsert_protected_seas_sites(
    local_gdf: gpd.GeoDataFrame,
    changed_gdf: gpd.GeoDataFrame,
    removed_ids: list[str] | None = None,
    id_col: str = "ps_id",
) -> gpd.GeoDataFrame:
    removed_ids = set(map(str, removed_ids or []))

    if changed_gdf.empty and not removed_ids:
        return local_gdf

    if not changed_gdf.empty:
        columns = [c for c in SITE_ATTRIBUTE_COLUMNS if c in changed_gdf.columns]
        changed = _normalize_site_attributes(changed_gdf[[*columns, "geometry"]].copy())
        changed_ids = set(changed[id_col])
    else:
        changed = None
        changed_ids = set()

    # Upsert on record identity, not version numbers: an attribute-only change
    # (e.g. lfp 5 -> 2 from a re-coding correction) may not advance any version
    # field, so we key off changed_since and always replace the local row.
    # Retired sites (removed_ids) are dropped and not re-appended.
    drop_ids = removed_ids | changed_ids
    updated = local_gdf[~local_gdf[id_col].astype(str).isin(drop_ids)]

    if changed is not None:
        updated = pd.concat([updated, changed], ignore_index=True)

    updated["fishing_protection_level"] = updated["lfp"].map(FISHING_PROTECTION_MAPPING)
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

    changed, removed_ids, _ = fetch_updated_site_details(last_update_date)

    if verbose and changed.attrs.get("failures"):
        logger.warning(
            {"message": "some sites failed to fetch", "failures": changed.attrs["failures"]}
        )

    updated = upsert_protected_seas_sites(current_gdf, changed, removed_ids=removed_ids)

    # Advance the baseline so the next run fetches changes since this run.
    today = datetime.date.today().isoformat()
    updated["last_updated"] = today

    # Write only the known columns
    updated = updated.reindex(
        columns=[*SITE_ATTRIBUTE_COLUMNS, "geometry", "fishing_protection_level", "last_updated"]
    )

    # Save the dated archive snapshot, then duplicate it to the current file.
    if verbose:
        logger.info({"message": f"uploading protected seas to {archive_file_name}"})
    upload_gdf(bucket, updated, archive_file_name, project_id=project, verbose=verbose)

    if verbose:
        logger.info({"message": f"duplicating blob to {sites_file_name}"})
    duplicate_blob(bucket, archive_file_name, sites_file_name, project_id=project, verbose=verbose)

    if verbose:
        logger.info({"message": f"Protected Seas data updated; last_updated set to {today}"})
