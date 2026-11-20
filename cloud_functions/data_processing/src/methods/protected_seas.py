import datetime
import glob
import re
import time
from dataclasses import dataclass, field

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
    PROTECTED_SEAS_FETCH_BUDGET_SECONDS,
    PROTECTED_SEAS_MAX_REMOVED_SHARE,
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
    """Normalize site attribute types in place and return `df`."""
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
    """Create the initial Protected Seas sites dataset from local Navigator exports.

    This one-time bootstrap reads every ``*LFP[0-5]*.json`` file in ``json_dir``,
    combines the site geometries, normalizes the fields used by the incremental
    update workflow, and maps each numeric LFP value to a fishing-protection
    bucket. The export date encoded as ``MMDDYY`` in the first filename becomes
    the dataset's ``last_updated`` value.

    The resulting GeoDataFrame is uploaded to ``archive_file_name`` in Cloud
    Storage, then that object is copied to ``sites_file_name`` to establish the
    current dataset used by :func:`update_protected_seas_data`.

    Args:
        json_dir: Local directory containing the Navigator LFP GeoJSON exports.
        sites_file_name: Cloud Storage object name for the current dataset.
        archive_file_name: Cloud Storage object name for the dated seed snapshot.
        bucket: Cloud Storage bucket containing the datasets.
        project: Google Cloud project used for storage operations.
        verbose: Whether storage helpers should emit progress messages.

    Raises:
        FileNotFoundError: If ``json_dir`` contains no matching LFP export files.
        ValueError: If the date cannot be parsed from the first export filename.
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

    # Save the dated archive snapshot, then duplicate it to the current file.
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


class BoundaryWithheldError(ValueError):
    """Site Details returned no boundary.

    Navigator withholds some boundaries for redistribution reasons. Not an
    error or a deletion, the site is treated as attribute-only.
    """


def load_protected_seas_site(
    ps_id: str,
    keep_bounds: bool = True,
    max_retries: int = 5,
    base_sleep: float = 3.0,
) -> gpd.GeoDataFrame:
    url = f"{PROTECTED_SEAS_SITES_URL}/detail/"
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
            raise BoundaryWithheldError(f"No site_boundary found for ps_id={ps_id}")

        site_geom = force_2d(shape(data["site_boundary"]))
        attrs = {k: v for k, v in data.items() if k not in {"site_boundary", "bounds"}}

        if keep_bounds and data.get("bounds"):
            attrs["bounds_geometry"] = force_2d(shape(data["bounds"]))

        return gpd.GeoDataFrame([attrs], geometry=[site_geom], crs="EPSG:4326")

    raise requests.HTTPError(
        f"Exceeded retries for ps_id={ps_id}; "
        f"last status={getattr(last_response, 'status_code', None)}"
    )


def select_sites_needing_boundary(
    active_index: pd.DataFrame,
    local_gdf: gpd.GeoDataFrame,
    changed_since: str,
) -> list[str]:
    """Return the ps_ids in `active_index` whose boundary must be fetched.

    Fetch when:
    - the site isn't stored yet
    - Navigator has no `last_boundary_update` for it
    - the stored `last_boundary_update` is older than Navigator's
    - none is stored and Navigator's is on or after `changed_since`

    Comparing with the stored per-site date lets a partial run resume without
    refetching what it saved. Dates are `YYYY-MM-DD` so they compare as text.
    """
    ids = active_index["ps_id"]
    stored = local_gdf.set_index("ps_id")
    if "last_boundary_update" in stored.columns:
        local = ids.map(stored["last_boundary_update"])
    else:
        local = pd.Series(None, index=ids.index, dtype=object)
    remote = active_index["last_boundary_update"]

    # Comparisons with a missing date are False
    needed = (
        ~ids.isin(stored.index)
        | remote.isna()
        | (local.notna() & (remote > local))
        | (local.isna() & (remote >= changed_since))
    )
    return ids[needed].tolist()


@dataclass
class SiteUpdates:
    """Changes from one sync."""

    changed_gdf: gpd.GeoDataFrame
    removed_ids: list[str]
    # Failed or not reached before the time budget ran out, left untouched so
    # a later run retries them
    failures: list[dict] = field(default_factory=list)
    unfinished_ids: list[str] = field(default_factory=list)
    # New sites with a withheld boundary, nothing to store
    withheld_new_ids: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not self.failures and not self.unfinished_ids


def fetch_updated_site_details(
    changed_since: str,
    local_gdf: gpd.GeoDataFrame,
    time_budget_seconds: float | None = PROTECTED_SEAS_FETCH_BUDGET_SECONDS,
) -> SiteUpdates:
    """Collect Navigator's site changes since `changed_since`.

    Attributes come from search. Boundaries come from Site Details only for
    sites picked by `select_sites_needing_boundary`, the rest keep their stored
    boundary. Fetching stops after `time_budget_seconds`, leaving the rest in
    `unfinished_ids` for the next run.
    """
    started = time.monotonic()
    updated_index = get_updated_site_index(changed_since=changed_since)
    empty = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    if updated_index.empty:
        return SiteUpdates(empty, [])

    index = updated_index.dropna(subset=["ps_id"]).copy()
    index["ps_id"] = index["ps_id"].astype(str)
    # Paging returns each site once unless data changes mid-sweep
    index = index.drop_duplicates(subset="ps_id", keep="last")

    if "status" in index.columns:
        is_removed = index["status"].astype(str).str.lower() == "removed"
    else:
        is_removed = pd.Series(False, index=index.index)

    removed_ids = index.loc[is_removed, "ps_id"].tolist()
    active = index.loc[~is_removed]
    need_boundary = select_sites_needing_boundary(active, local_gdf, changed_since)

    logger.info(
        {
            "message": (
                f"{len(active)} changed and {len(removed_ids)} removed site(s) since "
                f"{changed_since}; fetching {len(need_boundary)} boundary(ies)"
            )
        }
    )

    fetched = {}
    failures = []
    unfinished = []

    for position, ps_id in enumerate(tqdm(need_boundary)):
        if time_budget_seconds is not None and time.monotonic() - started > time_budget_seconds:
            unfinished = need_boundary[position:]
            break
        try:
            site = load_protected_seas_site(ps_id, keep_bounds=False)
            fetched[ps_id] = site.geometry.iloc[0]
        except BoundaryWithheldError:
            # Keeps its stored geometry, or is skipped below if new
            pass
        except Exception as exc:
            failures.append({"ps_id": ps_id, "error": str(exc)})

    logger.info({"message": f"fetched {len(fetched)} boundary(ies)"})

    # Leave failed and unfinished sites out so their stored rows stay as is
    skipped = [f["ps_id"] for f in failures] + unfinished
    columns = [c for c in SITE_ATTRIBUTE_COLUMNS if c in active.columns]
    attrs = active.loc[~active["ps_id"].isin(skipped), columns].set_index("ps_id")

    # Fetched boundaries replace stored ones, other sites keep theirs
    geometry = attrs.index.to_series().map(local_gdf.set_index("ps_id").geometry)
    if fetched:
        geometry.update(pd.Series(fetched, dtype=object))

    # New sites with a withheld boundary have no geometry
    has_geometry = geometry.notna()
    withheld_new = attrs.index[~has_geometry].tolist()
    if has_geometry.any():
        changed_gdf = gpd.GeoDataFrame(
            attrs[has_geometry].reset_index(),
            geometry=geometry[has_geometry].to_numpy(),
            crs="EPSG:4326",
        )
    else:
        changed_gdf = empty

    return SiteUpdates(
        changed_gdf=changed_gdf,
        removed_ids=removed_ids,
        failures=failures,
        unfinished_ids=unfinished,
        withheld_new_ids=withheld_new,
    )


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
    time_budget_seconds: float | None = PROTECTED_SEAS_FETCH_BUDGET_SECONDS,
    max_removed_share: float = PROTECTED_SEAS_MAX_REMOVED_SHARE,
    verbose: bool = True,
) -> SiteUpdates:
    """Apply Navigator's site changes since the last sync.

    `last_updated` is the start date of the last complete sync. A partial run
    saves its progress but keeps the old date, so the next run asks for the
    same changes and only fetches the boundaries still missing.

    Returns:
        The applied `SiteUpdates`, `complete` says whether another run is needed.

    Raises:
        ValueError: If more than `max_removed_share` of stored sites are reported
            removed, likely an upstream problem. Nothing is written.
    """
    # Use the start date so changes made during the run are picked up next time
    sync_started = datetime.date.today().isoformat()

    current_gdf = read_parquet_from_gcs(bucket, sites_file_name, verbose=verbose)
    last_update_date = current_gdf["last_updated"].iloc[0]

    if verbose:
        logger.info({"message": f"fetching Protected Seas sites updated since {last_update_date}"})

    updates = fetch_updated_site_details(
        last_update_date,
        current_gdf,
        time_budget_seconds=time_budget_seconds,
    )

    local_ids = current_gdf["ps_id"]
    removed_share = local_ids.isin(updates.removed_ids).mean() if len(local_ids) else 0.0
    if removed_share > max_removed_share:
        raise ValueError(
            f"Navigator reports {removed_share:.1%} of local Protected Seas sites as removed "
            f"(limit {max_removed_share:.0%}); not applying this sync"
        )

    if updates.failures:
        logger.warning(
            {"message": "some site boundaries failed to fetch", "failures": updates.failures}
        )
    if updates.unfinished_ids:
        logger.warning(
            {
                "message": (
                    f"time budget of {time_budget_seconds}s ran out with "
                    f"{len(updates.unfinished_ids)} boundary(ies) left to fetch; "
                    "saving progress, the next run will continue"
                )
            }
        )
    if updates.withheld_new_ids and verbose:
        logger.info(
            {
                "message": "new sites skipped because Navigator withholds their boundary",
                "ps_ids": updates.withheld_new_ids,
            }
        )

    updated = upsert_protected_seas_sites(
        current_gdf, updates.changed_gdf, removed_ids=updates.removed_ids
    )

    new_sync_date = sync_started if updates.complete else last_update_date
    updated["last_updated"] = new_sync_date

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
        status = "complete" if updates.complete else "partial"
        logger.info(
            {
                "message": (
                    f"Protected Seas {status} sync applied; last_updated set to {new_sync_date}"
                )
            }
        )

    return updates
