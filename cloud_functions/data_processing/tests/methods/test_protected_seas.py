import datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
import requests
from shapely.geometry import Point, Polygon, mapping

import src.methods.protected_seas as protected_seas


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


def test_fetch_updated_site_details_separates_removed_changed_and_failures(monkeypatch):
    """Separate removed sites while retaining changed-site fetch failures."""
    index = pd.DataFrame(
        {
            "ps_id": ["1", "1", "2", "3", None],
            "status": ["active", "active", "REMOVED", "active", "active"],
        }
    )
    monkeypatch.setattr(
        protected_seas, "get_updated_site_index", lambda changed_since: index.copy()
    )

    fetched = []

    def fake_load(ps_id):
        fetched.append(ps_id)
        if ps_id == "3":
            raise RuntimeError("detail failed")
        return gpd.GeoDataFrame(
            {"ps_id": [ps_id], "site_name": [f"Site {ps_id}"]},
            geometry=[Point(0, 0)],
            crs="EPSG:4326",
        )

    monkeypatch.setattr(protected_seas, "load_protected_seas_site", fake_load)
    monkeypatch.setattr(protected_seas.time, "sleep", lambda _: None)

    changed, removed_ids, returned_index = protected_seas.fetch_updated_site_details(
        "2026-01-01", sleep_seconds=0
    )

    assert fetched == ["1", "3"]
    assert changed["ps_id"].tolist() == ["1"]
    assert removed_ids == ["2"]
    assert returned_index.equals(index)
    assert changed.attrs["failures"] == [{"ps_id": "3", "error": "detail failed"}]


def test_fetch_updated_site_details_handles_empty_index(monkeypatch):
    """Return empty, correctly typed results when no sites have changed."""
    monkeypatch.setattr(
        protected_seas, "get_updated_site_index", lambda changed_since: pd.DataFrame()
    )

    changed, removed_ids, index = protected_seas.fetch_updated_site_details("2026-01-01")

    assert changed.empty
    assert changed.crs.to_epsg() == 4326
    assert removed_ids == []
    assert index.empty


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
        },
        geometry=[Point(10, 0)],
        crs="EPSG:4326",
    )

    result = protected_seas.upsert_protected_seas_sites(local, changed, removed_ids=[3])
    by_id = result.assign(_id=result["ps_id"].astype(str)).set_index("_id")

    assert set(by_id.index) == {"1", "2"}
    assert by_id.loc["1", "site_name"] == "Keep"
    assert by_id.loc["2", "site_name"] == "New name"
    assert by_id.loc["2", "fishing_protection_level"] == "less"
    assert by_id.loc["2", "geometry"].equals(Point(10, 0))
    assert result.crs == local.crs


def test_upsert_protected_seas_sites_returns_unchanged_data_for_no_updates():
    """Return the existing dataset directly when there are no updates."""
    local = gpd.GeoDataFrame({"ps_id": ["1"], "lfp": [5]}, geometry=[Point(0, 0)], crs="EPSG:4326")
    changed = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    assert protected_seas.upsert_protected_seas_sites(local, changed) is local


def test_update_protected_seas_data_archives_then_updates_current(monkeypatch):
    """Publish an updated archive before replacing the current dataset."""
    current = gpd.GeoDataFrame(
        {
            "ps_id": ["1"],
            "site_name": ["Site 1"],
            "country": ["A"],
            "lfp": [5],
            "fishing_protection_level": ["highly"],
            "last_updated": ["2026-01-01"],
        },
        geometry=[Point(0, 0)],
        crs="EPSG:4326",
    )
    changed = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    changed.attrs["failures"] = []

    monkeypatch.setattr(protected_seas, "read_parquet_from_gcs", lambda *_, **__: current.copy())
    requested_dates = []

    def fake_fetch(changed_since):
        requested_dates.append(changed_since)
        return changed, [], pd.DataFrame()

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

    protected_seas.update_protected_seas_data(
        sites_file_name="current.parquet",
        archive_file_name="archive.parquet",
        bucket="bucket",
        project="project",
        verbose=False,
    )

    assert requested_dates == ["2026-01-01"]
    assert [call[0] for call in calls] == ["upload", "duplicate"]
    assert set(calls[0][3]["last_updated"]) == {"2026-02-03"}
    assert calls[0][1:3] == ("bucket", "archive.parquet")
    assert calls[1][1:4] == ("bucket", "archive.parquet", "current.parquet")
