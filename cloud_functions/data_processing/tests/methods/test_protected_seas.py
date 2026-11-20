import datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
import requests
from shapely.geometry import Point, Polygon, mapping

import src.methods.download_and_process.protected_seas as download_ps
import src.methods.protected_seas as protected_seas
from src.core.retry_params import METHOD_RETRY_CONFIGS, ScheduleRetry


class FakeResponse:
    def __init__(self, *, status_code=200, data=None, headers=None):
        self.status_code = status_code
        self._data = data or {}
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")

    def json(self):
        return self._data


def _site_gdf(ps_id, lfp, x=0):
    return gpd.GeoDataFrame(
        {
            "SITE_ID": [ps_id],
            "site_name": [f"Site {ps_id}"],
            "country": ["Testland"],
            "lfp": [lfp],
        },
        geometry=[Point(x, 0)],
        crs="EPSG:4326",
    )


def test_seed_protected_seas_sites_normalizes_and_uploads_exports(tmp_path, monkeypatch):
    """Seed local exports into normalized archive and current datasets."""
    paths = [
        tmp_path / "Navigator_LFP0_sites_010226.json",
        tmp_path / "Navigator_LFP3_sites_010226.json",
        tmp_path / "Navigator_LFP5_sites_010226.json",
    ]
    for path in paths:
        path.touch()

    source_by_name = {
        paths[0].name: _site_gdf("zero", 0, 0),
        paths[1].name: _site_gdf("moderate", 3, 1),
        paths[2].name: _site_gdf("high", 5, 2),
    }
    monkeypatch.setattr(
        protected_seas.gpd,
        "read_file",
        lambda path, **_: source_by_name[Path(path).name].copy(),
    )

    calls = []
    monkeypatch.setattr(
        protected_seas,
        "upload_gdf",
        lambda bucket, gdf, filename, **kwargs: calls.append(
            ("upload", bucket, filename, gdf.copy(), kwargs)
        ),
    )
    monkeypatch.setattr(
        protected_seas,
        "duplicate_blob",
        lambda bucket, source, destination, **kwargs: calls.append(
            ("duplicate", bucket, source, destination, kwargs)
        ),
    )

    protected_seas.seed_protected_seas_sites(
        str(tmp_path),
        sites_file_name="current.parquet",
        archive_file_name="archive.parquet",
        bucket="bucket",
        project="project",
        verbose=False,
    )

    assert [call[0] for call in calls] == ["upload", "duplicate"]
    uploaded = calls[0][3].set_index("ps_id")
    assert list(uploaded.columns) == [
        "site_name",
        "country",
        "lfp",
        "geometry",
        "fishing_protection_level",
        "last_updated",
    ]
    assert uploaded.loc["moderate", "fishing_protection_level"] == "moderately"
    assert uploaded.loc["high", "fishing_protection_level"] == "highly"
    assert pd.isna(uploaded.loc["zero", "fishing_protection_level"])
    assert set(uploaded["last_updated"]) == {"2026-01-02"}
    assert calls[0][1:3] == ("bucket", "archive.parquet")
    assert calls[0][4]["project_id"] == "project"
    assert calls[1][1:4] == ("bucket", "archive.parquet", "current.parquet")


def test_seed_protected_seas_sites_requires_matching_files(tmp_path):
    """Reject a seed directory that contains no matching Navigator exports."""
    with pytest.raises(FileNotFoundError, match="No Navigator LFP site files"):
        protected_seas.seed_protected_seas_sites(str(tmp_path), verbose=False)


def test_seed_protected_seas_sites_requires_date_suffix(tmp_path):
    """Reject an export filename without the required MMDDYY suffix."""
    (tmp_path / "Navigator_LFP5_sites.json").touch()

    with pytest.raises(ValueError, match="Could not parse a MMDDYY date"):
        protected_seas.seed_protected_seas_sites(str(tmp_path), verbose=False)


def test_get_updated_site_index_retries_429_and_paginates(monkeypatch):
    """Retry rate limits on the same page and collect every result page."""
    responses = iter(
        [
            FakeResponse(status_code=429),
            FakeResponse(data={"sites": [{"ps_id": "1"}, {"ps_id": "2"}]}),
            FakeResponse(data={"sites": [{"ps_id": "3"}]}),
        ]
    )
    requested_pages = []

    def fake_get(_url, *, params, timeout):
        assert timeout == 60
        requested_pages.append(params["page"])
        assert params["include_inactive"] == "true"
        return next(responses)

    sleeps = []
    monkeypatch.setattr(protected_seas.requests, "get", fake_get)
    monkeypatch.setattr(protected_seas.time, "sleep", sleeps.append)

    result = protected_seas.get_updated_site_index("2026-01-01", limit=2, sleep_seconds=0.25)

    assert result["ps_id"].tolist() == ["1", "2", "3"]
    assert requested_pages == [1, 1, 2]
    assert sleeps == [10, 0.25]


def test_load_protected_seas_site_retries_and_forces_2d(monkeypatch):
    """Retry a site request and remove Z coordinates from returned geometries."""
    boundary = Polygon([(0, 0, 5), (1, 0, 5), (1, 1, 5), (0, 1, 5)])
    bounds = Polygon([(-1, -1, 2), (2, -1, 2), (2, 2, 2), (-1, 2, 2)])
    responses = iter(
        [
            FakeResponse(status_code=429, headers={"Retry-After": "2"}),
            FakeResponse(
                data={
                    "ps_id": "123",
                    "site_name": "Test site",
                    "site_boundary": mapping(boundary),
                    "bounds": mapping(bounds),
                }
            ),
        ]
    )
    monkeypatch.setattr(protected_seas.requests, "get", lambda *_, **__: next(responses))
    sleeps = []
    monkeypatch.setattr(protected_seas.time, "sleep", sleeps.append)

    result = protected_seas.load_protected_seas_site("123")

    assert sleeps == [2.0]
    assert result.crs.to_epsg() == 4326
    assert result.geometry.iloc[0].has_z is False
    assert result.loc[0, "bounds_geometry"].has_z is False
    assert "site_boundary" not in result.columns
    assert "bounds" not in result.columns


def test_load_protected_seas_site_rejects_missing_boundary(monkeypatch):
    """Reject site details that do not include a boundary geometry."""
    monkeypatch.setattr(
        protected_seas.requests,
        "get",
        lambda *_, **__: FakeResponse(data={"ps_id": "123", "site_boundary": None}),
    )

    with pytest.raises(ValueError, match="No site_boundary found for ps_id=123"):
        protected_seas.load_protected_seas_site("123")


def test_load_protected_seas_site_raises_after_retry_exhaustion(monkeypatch):
    """Raise an HTTP error after exhausting rate-limit retries."""
    monkeypatch.setattr(
        protected_seas.requests,
        "get",
        lambda *_, **__: FakeResponse(status_code=429),
    )
    monkeypatch.setattr(protected_seas.time, "sleep", lambda _: None)

    with pytest.raises(requests.HTTPError, match="Exceeded retries for ps_id=123"):
        protected_seas.load_protected_seas_site("123", max_retries=2, base_sleep=0)


def _local_sites(**columns):
    """Local sites dataset with one row per ps_id in `columns["ps_id"]`."""
    n = len(columns["ps_id"])
    data = {
        "site_name": [f"Site {i}" for i in columns["ps_id"]],
        "country": ["A"] * n,
        "lfp": [5] * n,
        "fishing_protection_level": ["highly"] * n,
        "last_updated": ["2026-01-01"] * n,
        **columns,
    }
    return gpd.GeoDataFrame(data, geometry=[Point(i, 0) for i in range(n)], crs="EPSG:4326")


def _index(**columns):
    """Search results for `sites_updated` with the attribute columns filled in."""
    n = len(columns["ps_id"])
    data = {
        "site_name": [f"New {i}" for i in columns["ps_id"]],
        "country": ["B"] * n,
        "lfp": [2] * n,
        "wdpa_id": [None] * n,
        "type": ["MPA"] * n,
        "status": ["active"] * n,
        "last_update": ["2026-02-01"] * n,
        "last_boundary_update": ["2026-02-01"] * n,
        **columns,
    }
    return pd.DataFrame(data)


def _detail(ps_id, x=100, **attrs):
    return gpd.GeoDataFrame(
        {"ps_id": [ps_id], "site_name": [f"Detail {ps_id}"], **{k: [v] for k, v in attrs.items()}},
        geometry=[Point(x, 0)],
        crs="EPSG:4326",
    )


def test_select_sites_needing_boundary_applies_navigator_rules():
    """Fetch boundaries only for new sites or ones whose boundary changed."""
    local = _local_sites(
        ps_id=["stored-old", "stored-same", "unstored-recent", "unstored-old", "no-remote"],
        last_boundary_update=["2026-01-15", "2026-02-01", None, None, "2026-01-01"],
    )
    index = _index(
        ps_id=["stored-old", "stored-same", "unstored-recent", "unstored-old", "no-remote", "new"],
        last_boundary_update=[
            "2026-02-01",
            "2026-02-01",
            "2026-01-01",
            "2025-12-31",
            None,
            "2025-06-01",
        ],
    )

    result = protected_seas.select_sites_needing_boundary(index, local, "2026-01-01")

    assert result == ["stored-old", "unstored-recent", "no-remote", "new"]


def test_select_sites_needing_boundary_uses_changed_since_for_seeded_data():
    """Fall back to changed_since when the local dataset has no per-site dates."""
    local = _local_sites(ps_id=["1", "2"])
    index = _index(ps_id=["1", "2"], last_boundary_update=["2026-01-01", "2025-12-01"])

    assert protected_seas.select_sites_needing_boundary(index, local, "2026-01-01") == ["1"]


def test_fetch_updated_site_details_updates_attributes_and_fetches_changed_boundaries(
    monkeypatch,
):
    """Take attributes from search, and boundaries only where they changed."""
    local = _local_sites(
        ps_id=["attr-only", "boundary", "withheld", "failed", "removed"],
        last_boundary_update=["2026-01-01"] * 5,
    )
    index = _index(
        ps_id=["attr-only", "boundary", "withheld", "failed", "removed", "new", "new-withheld"],
        last_boundary_update=["2026-01-01"] + ["2026-02-01"] * 6,
        status=["active"] * 4 + ["REMOVED"] + ["active"] * 2,
        wdpa_id=[555.0, None, None, None, None, "777", None],
    )
    monkeypatch.setattr(
        protected_seas, "get_updated_site_index", lambda changed_since: index.copy()
    )

    fetched = []

    def fake_load(ps_id, **_):
        fetched.append(ps_id)
        if ps_id in {"withheld", "new-withheld"}:
            raise protected_seas.BoundaryWithheldError(ps_id)
        if ps_id == "failed":
            raise RuntimeError("detail failed")
        return _detail(ps_id, lfp=4)

    monkeypatch.setattr(protected_seas, "load_protected_seas_site", fake_load)

    updates = protected_seas.fetch_updated_site_details(
        "2026-01-01", local, time_budget_seconds=None
    )

    assert fetched == ["boundary", "withheld", "failed", "new", "new-withheld"]
    assert updates.removed_ids == ["removed"]
    assert updates.failures == [{"ps_id": "failed", "error": "detail failed"}]
    assert updates.withheld_new_ids == ["new-withheld"]
    assert not updates.complete

    changed = updates.changed_gdf.set_index("ps_id")
    assert list(changed.index) == ["attr-only", "boundary", "withheld", "new"]
    # Attribute-only: search attributes, local geometry
    assert changed.loc["attr-only", "site_name"] == "New attr-only"
    assert changed.loc["attr-only", "lfp"] == 2
    assert changed.loc["attr-only", "wdpa_id"] == 555.0
    assert changed.loc["attr-only", "geometry"].equals(Point(0, 0))
    # Fetched: search attributes, Site Details geometry
    assert changed.loc["boundary", "site_name"] == "New boundary"
    assert changed.loc["boundary", "lfp"] == 2
    assert changed.loc["boundary", "type"] == "MPA"
    assert changed.loc["boundary", "geometry"].equals(Point(100, 0))
    # Withheld but already stored: keep the local geometry
    assert changed.loc["withheld", "geometry"].equals(Point(2, 0))


def test_fetch_updated_site_details_stops_at_time_budget(monkeypatch):
    """Leave the remaining boundaries for the next run once the budget is spent."""
    local = _local_sites(ps_id=["0"], last_boundary_update=["2026-01-01"])
    index = _index(ps_id=["1", "2", "3"])
    monkeypatch.setattr(
        protected_seas, "get_updated_site_index", lambda changed_since: index.copy()
    )
    monkeypatch.setattr(
        protected_seas,
        "load_protected_seas_site",
        lambda ps_id, **_: _detail(ps_id),
    )
    clock = iter([0.0, 1.0, 5.0, 11.0])
    monkeypatch.setattr(protected_seas.time, "monotonic", lambda: next(clock))

    updates = protected_seas.fetch_updated_site_details("2026-01-01", local, time_budget_seconds=10)

    assert updates.changed_gdf["ps_id"].tolist() == ["1", "2"]
    assert updates.unfinished_ids == ["3"]
    assert not updates.complete


def test_fetch_updated_site_details_handles_empty_index(monkeypatch):
    """Return empty, correctly typed results when no sites have changed."""
    monkeypatch.setattr(
        protected_seas, "get_updated_site_index", lambda changed_since: pd.DataFrame()
    )

    updates = protected_seas.fetch_updated_site_details("2026-01-01", _local_sites(ps_id=["1"]))

    assert updates.changed_gdf.empty
    assert updates.changed_gdf.crs.to_epsg() == 4326
    assert updates.removed_ids == []
    assert updates.complete


def test_upsert_protected_seas_sites_replaces_changes_and_removes_retired_sites():
    """Replace changed records, remove retired ones, and preserve unchanged ones."""
    local = gpd.GeoDataFrame(
        {
            "ps_id": ["1", "2", "3"],
            "site_name": ["Keep", "Old name", "Retire"],
            "country": ["A", "A", "A"],
            "lfp": [5, 5, 3],
            "fishing_protection_level": ["highly", "highly", "moderately"],
            "last_updated": ["2026-01-01"] * 3,
        },
        geometry=[Point(0, 0), Point(1, 0), Point(2, 0)],
        crs="EPSG:4326",
    )
    changed = gpd.GeoDataFrame(
        {
            "ps_id": [2],
            "site_name": ["New name"],
            "country": ["B"],
            "lfp": [2],
            "wdpa_id": ["12345"],
            "type": ["MPA"],
            "category_id": [9],
        },
        geometry=[Point(10, 0)],
        crs="EPSG:4326",
    )

    result = protected_seas.upsert_protected_seas_sites(local, changed, removed_ids=[3])
    by_id = result.set_index("ps_id")

    assert set(by_id.index) == {"1", "2"}
    assert by_id.loc["1", "site_name"] == "Keep"
    assert pd.isna(by_id.loc["1", "wdpa_id"])
    assert by_id.loc["2", "site_name"] == "New name"
    assert by_id.loc["2", "fishing_protection_level"] == "less"
    assert by_id.loc["2", "wdpa_id"] == "12345"
    assert by_id.loc["2", "type"] == "MPA"
    assert by_id.loc["2", "geometry"].equals(Point(10, 0))
    assert "category_id" not in result.columns
    assert result.crs == local.crs


def test_upsert_protected_seas_sites_returns_unchanged_data_for_no_updates():
    """Return the existing dataset directly when there are no updates."""
    local = gpd.GeoDataFrame({"ps_id": ["1"], "lfp": [5]}, geometry=[Point(0, 0)], crs="EPSG:4326")
    changed = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    assert protected_seas.upsert_protected_seas_sites(local, changed) is local


def _run_update(monkeypatch, current, updates, **kwargs):
    """Run update_protected_seas_data with storage and fetching stubbed out."""
    monkeypatch.setattr(protected_seas, "read_parquet_from_gcs", lambda *_, **__: current.copy())
    requested = []

    def fake_fetch(changed_since, local_gdf, **_):
        requested.append(changed_since)
        return updates

    monkeypatch.setattr(protected_seas, "fetch_updated_site_details", fake_fetch)

    class FixedDate(datetime.date):
        @classmethod
        def today(cls):
            return cls(2026, 2, 3)

    monkeypatch.setattr(protected_seas.datetime, "date", FixedDate)

    calls = []
    monkeypatch.setattr(
        protected_seas,
        "upload_gdf",
        lambda bucket, gdf, filename, **kw: calls.append(("upload", bucket, filename, gdf.copy())),
    )
    monkeypatch.setattr(
        protected_seas,
        "duplicate_blob",
        lambda bucket, source, destination, **kw: calls.append(
            ("duplicate", bucket, source, destination)
        ),
    )

    result = protected_seas.update_protected_seas_data(
        sites_file_name="current.parquet",
        archive_file_name="archive.parquet",
        bucket="bucket",
        project="project",
        verbose=False,
        **kwargs,
    )
    assert result is updates
    return requested, calls


def _empty_updates(**kwargs):
    return protected_seas.SiteUpdates(gpd.GeoDataFrame(geometry=[], crs="EPSG:4326"), [], **kwargs)


def test_update_protected_seas_data_archives_then_updates_current(monkeypatch):
    """Publish an updated archive before replacing the current dataset."""
    requested, calls = _run_update(monkeypatch, _local_sites(ps_id=["1"]), _empty_updates())

    assert requested == ["2026-01-01"]
    assert [call[0] for call in calls] == ["upload", "duplicate"]
    assert set(calls[0][3]["last_updated"]) == {"2026-02-03"}
    assert calls[0][1:3] == ("bucket", "archive.parquet")
    assert calls[1][1:4] == ("bucket", "archive.parquet", "current.parquet")


@pytest.mark.parametrize(
    "partial",
    [
        {"failures": [{"ps_id": "1", "error": "boom"}]},
        {"unfinished_ids": ["1"]},
    ],
)
def test_update_protected_seas_data_saves_partial_sync_without_advancing_date(monkeypatch, partial):
    """Save progress from a partial sync but keep the previous sync date."""
    changed = gpd.GeoDataFrame(
        {"ps_id": ["2"], "site_name": ["Changed"], "country": ["A"], "lfp": [3]},
        geometry=[Point(5, 0)],
        crs="EPSG:4326",
    )
    updates = protected_seas.SiteUpdates(changed, [], **partial)

    _, calls = _run_update(monkeypatch, _local_sites(ps_id=["1", "2"]), updates)

    uploaded = calls[0][3].set_index("ps_id")
    assert uploaded.loc["2", "site_name"] == "Changed"
    assert set(uploaded["last_updated"]) == {"2026-01-01"}


def test_update_protected_seas_data_writes_only_known_columns(monkeypatch):
    """Drop unknown columns and write every known one, even if empty."""
    current = _local_sites(ps_id=["1"], last_update=["2026-01-01"], stray=["x"])

    _, calls = _run_update(monkeypatch, current, _empty_updates())

    assert list(calls[0][3].columns) == [
        *protected_seas.SITE_ATTRIBUTE_COLUMNS,
        "geometry",
        "fishing_protection_level",
        "last_updated",
    ]


def test_update_protected_seas_data_refuses_mass_removal(monkeypatch):
    """Write nothing when Navigator reports too many local sites as removed."""
    updates = _empty_updates()
    updates.removed_ids = ["1", "2"]

    with pytest.raises(ValueError, match="as removed"):
        _run_update(
            monkeypatch,
            _local_sites(ps_id=["1", "2", "3", "4"]),
            updates,
            max_removed_share=0.25,
        )


def _stub_download(monkeypatch, updates):
    """Stub the region stats download and the sites update in download_protected_seas."""
    monkeypatch.setattr(
        download_ps,
        "retry_and_alert",
        lambda *_, **__: pd.DataFrame({"iso_ter": ["AAA"]}),
    )
    monkeypatch.setattr(download_ps, "upload_dataframe", lambda *_, **__: None)
    monkeypatch.setattr(download_ps, "duplicate_blob", lambda *_, **__: None)
    monkeypatch.setattr(download_ps, "update_protected_seas_data", lambda **_: updates)


def test_download_protected_seas_schedules_continuation_after_partial_sync(monkeypatch):
    """Queue another run when the sites sync stopped before applying every change."""
    _stub_download(monkeypatch, _empty_updates(unfinished_ids=["1", "2"]))

    with pytest.raises(ScheduleRetry) as raised:
        download_ps.download_protected_seas(verbose=False)

    cfg = METHOD_RETRY_CONFIGS["download_protected_seas"]
    assert raised.value.delay_seconds == cfg["delay_seconds"]
    assert raised.value.max_retries == cfg["max_retries"]
    assert "2 boundary(ies) not reached" in str(raised.value)


def test_download_protected_seas_finishes_after_complete_sync(monkeypatch):
    """Return normally, letting the pipeline move on, once the sync is complete."""
    _stub_download(monkeypatch, _empty_updates())

    download_ps.download_protected_seas(verbose=False)
