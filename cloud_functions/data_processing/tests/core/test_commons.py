"""Tests for get_cover_areas, process_buffered_iho and the IHO spatial joins
(intersect_with_iho and the intersect_wdpa_with_iho / intersect_mpatlas_with_iho
wrappers) in src/core/commons.py."""

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.transform import Affine
from shapely.geometry import MultiPolygon, Point, Polygon, box, mapping

from src.core import commons
from src.core.commons import (
    get_cover_areas,
    intersect_mpatlas_with_iho,
    intersect_wdpa_with_iho,
    intersect_with_iho,
    process_buffered_iho,
)
from src.utils.geo import compute_pixel_area_map_km2

CLASS_MAP = {0: "class-a", 1: "class-b"}


def _write_raster(path, arr, crs, transform, nodata):
    h, w = arr.shape
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=1,
        dtype=arr.dtype,
        crs=crs,
        transform=transform,
        nodata=nodata,
    ) as dst:
        dst.write(arr, 1)


def test_excludes_nan_nodata_and_areas_match_pixel_counts(tmp_path):
    """float32 + nan nodata on a projected (EPSG:3857) raster: nan must not leak
    in as a class, and per-class km² must equal pixel count × per-pixel area."""
    pixel = 250.0
    transform = Affine(pixel, 0, 0.0, 0, -pixel, pixel * 5)
    arr = np.full((6, 6), np.nan, dtype="float32")
    arr[1:4, 1:3] = 1.0  # 6 class-b pixels
    arr[1:4, 3:5] = 0.0  # 6 class-a pixels (same rows → equal area to class-b)

    path = str(tmp_path / "r.tif")
    _write_raster(path, arr, "EPSG:3857", transform, float("nan"))

    poly = box(0.0, pixel * 5 - pixel * 6, pixel * 6, pixel * 5)
    with rasterio.open(path) as src:
        res = get_cover_areas(src, [mapping(poly)], "X", "country", CLASS_MAP, include_zero=True)
        per_class = compute_pixel_area_map_km2(src.transform, 6, 6, crs=src.crs)[1:4, 0].sum() * 2

    assert set(res) == {"country", "total", "class-a", "class-b"}  # no nan-derived key
    assert res["class-a"] == pytest.approx(per_class)
    assert res["class-b"] == pytest.approx(per_class)
    assert res["total"] == pytest.approx(2 * per_class)


def test_all_zero_region_returns_none_without_include_zero(tmp_path):
    """With include_zero=False an all-zero window is treated as 'no class' → None."""
    transform = Affine(1, 0, -10, 0, -1, 10)
    arr = np.zeros((10, 10), dtype="uint8")
    path = str(tmp_path / "zeros.tif")
    _write_raster(path, arr, "EPSG:4326", transform, 255)

    poly = box(-10, -10, 10, 10)
    with rasterio.open(path) as src:
        assert get_cover_areas(src, [mapping(poly)], "X", "country", CLASS_MAP) is None


def test_unmapped_pixel_value_falls_back_to_generic_class_name(tmp_path):
    """A pixel value missing from class_map is reported under a class_<value> key
    rather than dropped."""
    transform = Affine(1, 0, -10, 0, -1, 10)
    arr = np.full((10, 10), 7, dtype="uint8")  # 7 is not in CLASS_MAP
    path = str(tmp_path / "seven.tif")
    _write_raster(path, arr, "EPSG:4326", transform, 255)

    poly = box(-10, -10, 10, 10)
    with rasterio.open(path) as src:
        res = get_cover_areas(src, [mapping(poly)], "X", "country", CLASS_MAP)
    assert "class_7" in res
    assert res["class_7"] == pytest.approx(res["total"])


def _bowtie(x, y):
    """A self-intersecting — and therefore invalid — polygon."""
    return Polygon([(x, y), (x + 2, y + 2), (x + 2, y), (x, y + 2), (x, y)])


def test_invalid_iho_geometries_are_repaired_not_dropped():
    """Every IHO row is a location, and a dropped sea area would also stop its
    neighbours being clipped against it, so invalid input must be repaired in
    place. 1906 is in UNBUFFERED_MRGID: it is passed through, but still repaired."""
    bowtie = _bowtie(0, 0)
    arctic = _bowtie(10, 10)
    assert not bowtie.is_valid and not arctic.is_valid

    iho = gpd.GeoDataFrame(
        {
            "NAME": ["Bowtie Sea", "Neighbour Sea", "Arctic Ocean"],
            "MRGID": [111, 222, 1906],
            "geometry": [bowtie, box(2, 0, 4, 2), arctic],
        },
        crs="EPSG:4326",
    )

    result = process_buffered_iho(iho, km=1, n_jobs=1)

    assert sorted(result["MRGID"]) == [111, 222, 1906]
    assert result.geometry.is_valid.all()
    # The caller's frame is left untouched by the repair.
    assert not iho.geometry.is_valid.all()


# ---------- intersect_wdpa_with_iho / intersect_mpatlas_with_iho ----------

# Two side-by-side seas sharing the x=10 edge.
SEA_A = box(0, 0, 10, 10)
SEA_B = box(10, 0, 20, 10)


def _fake_iho():
    return gpd.GeoDataFrame(
        {"MRGID": ["1", "2"], "location": ["1", "2"], "NAME": ["Sea A", "Sea B"]},
        geometry=[SEA_A, SEA_B],
        crs="EPSG:4326",
    )


def _patch_iho(monkeypatch, calls=None):
    def fake_load_iho_regions(buffer=False):
        if calls is not None:
            calls.append(buffer)
        return _fake_iho()

    monkeypatch.setattr(commons, "load_iho_regions", fake_load_iho_regions)


def _patch_wdpa(monkeypatch, gdf, calls=None):
    def fake_read_json_df(bucket_name, filename, **kwargs):
        if calls is not None:
            calls.append(filename)
        return gdf

    monkeypatch.setattr(commons, "read_json_df", fake_read_json_df)


def _wdpa_frame(geometries, pids=None, **extra):
    n = len(geometries)
    pids = pids if pids is not None else [str(i) for i in range(n)]
    return gpd.GeoDataFrame(
        {
            "WDPA_PID": pids,
            # Carried through the join so consumers can roll parcels up to their
            # parent and split PAs from OECMs without re-reading the PA file.
            "WDPAID": [pid.split("_")[0] for pid in pids],
            "PA_DEF": [1] * n,
            **extra,
        },
        geometry=geometries,
        crs="EPSG:4326",
    )


def test_wdpa_iho_join_pairs_each_pa_with_every_sea_it_overlaps(monkeypatch):
    _patch_iho(monkeypatch)
    _patch_wdpa(
        monkeypatch,
        _wdpa_frame(
            [box(1, 1, 2, 2), box(5, 1, 15, 2), box(100, 50, 101, 51)],
            pids=["inside", "straddler", "elsewhere"],
        ),
    )

    result = intersect_wdpa_with_iho(bucket="b", tolerance=0.0001)

    pairs = sorted(zip(result["WDPA_PID"], result["location"], strict=True))
    assert pairs == [("inside", "1"), ("straddler", "1"), ("straddler", "2")]


def test_wdpa_iho_join_uses_the_marine_file_for_the_given_tolerance(monkeypatch):
    _patch_iho(monkeypatch)
    requested = []
    _patch_wdpa(monkeypatch, _wdpa_frame([box(1, 1, 2, 2)]), calls=requested)

    intersect_wdpa_with_iho(bucket="b", tolerance=0.0001)

    assert requested == ["intermediates/protected_area_geoms/marine_wdpa_0.0001.geojson"]


def test_wdpa_iho_join_uses_unbuffered_iho(monkeypatch):
    """The near-shore buffered layer is for habitats; sea assignment must use
    the true IHO boundaries."""
    buffers = []
    _patch_iho(monkeypatch, calls=buffers)
    _patch_wdpa(monkeypatch, _wdpa_frame([box(1, 1, 2, 2)]))

    intersect_wdpa_with_iho(bucket="b", tolerance=0.0001)

    assert buffers == [False]


def test_wdpa_iho_join_carries_only_the_columns_consumers_need(monkeypatch):
    """PA_DEF and WDPAID travel with the pair so the coverage stats and habitat
    rollups need not re-read the PA file. Everything else is left behind for
    callers to merge back on themselves."""
    _patch_iho(monkeypatch)
    _patch_wdpa(
        monkeypatch,
        _wdpa_frame([box(1, 1, 2, 2)], DESIG_ENG=["Marine Park"], ISO3=["FRA"]),
    )

    result = intersect_wdpa_with_iho(bucket="b", tolerance=0.0001)

    assert list(result.columns) == ["WDPA_PID", "WDPAID", "PA_DEF", "location"]


def test_wdpa_iho_join_keeps_point_pas(monkeypatch):
    """A point falls inside a sea just as a polygon does, so it is a member like
    any other PA and carries its own area from the metadata."""
    _patch_iho(monkeypatch)
    _patch_wdpa(
        monkeypatch,
        _wdpa_frame(
            [box(1, 1, 2, 2), Point(3, 3), Point(50, 50), None],
            pids=["polygon", "point_in_sea", "point_at_sea", "missing"],
        ),
    )

    result = intersect_wdpa_with_iho(bucket="b", tolerance=0.0001)

    assert sorted(result["WDPA_PID"]) == ["point_in_sea", "polygon"]


def test_wdpa_iho_join_counts_a_pa_that_only_touches_a_sea(monkeypatch):
    """`intersects` is true of a shared boundary, so a PA abutting a sea counts
    as a member. On real data that is 2 pairs out of 19,175, and filtering it
    would mean computing the overlap we no longer need."""
    _patch_iho(monkeypatch)
    _patch_wdpa(monkeypatch, _wdpa_frame([box(-5, 0, 0, 10)], pids=["adjacent"]))

    result = intersect_wdpa_with_iho(bucket="b", tolerance=0.0001)

    assert result["WDPA_PID"].tolist() == ["adjacent"]


def test_mpatlas_iho_join_pairs_zones_with_the_seas_they_overlap(monkeypatch):
    _patch_iho(monkeypatch)
    mpa = gpd.GeoDataFrame(
        {"zone_id": [10, 20, 30], "protection_mpaguide_level": ["full", "less", "unknown"]},
        geometry=[box(1, 1, 2, 2), box(11, 1, 12, 2), Point(3, 3)],
        crs="EPSG:4326",
    )
    monkeypatch.setattr(commons, "read_mpatlas_from_gcs", lambda bucket, filename: mpa)

    result = intersect_mpatlas_with_iho(bucket="b", mpa_file_name="raw/mpatlas.geojson")

    assert list(result.columns) == ["zone_id", "protection_mpaguide_level", "location"]
    # every zone regardless of protection level, and the point zone too
    assert sorted(zip(result["zone_id"], result["location"], strict=True)) == [
        (10, "1"),
        (20, "2"),
        (30, "1"),
    ]


# ---------- intersect_with_iho(with_geometry=True) ----------


def test_geometry_join_cuts_a_straddling_feature_into_one_piece_per_sea(monkeypatch):
    """The point of keeping geometry: each pair carries the feature clipped to
    its own sea, so the pieces can be unioned or differenced per sea without
    reaching back for the sea boundaries."""
    _patch_iho(monkeypatch)

    result = intersect_with_iho(
        _wdpa_frame([box(5, 1, 15, 2)], pids=["straddler"]), ["WDPA_PID"], with_geometry=True
    )

    pieces = dict(zip(result["location"], result.geometry, strict=True))
    assert pieces["1"].equals(box(5, 1, 10, 2))
    assert pieces["2"].equals(box(10, 1, 15, 2))


def test_geometry_join_leaves_a_contained_feature_whole(monkeypatch):
    _patch_iho(monkeypatch)

    result = intersect_with_iho(
        _wdpa_frame([box(1, 1, 2, 2)], pids=["inside"]), ["WDPA_PID"], with_geometry=True
    )

    assert result.geometry.iloc[0].equals(box(1, 1, 2, 2))


def test_geometry_join_drops_an_areal_feature_that_only_touches_a_sea(monkeypatch):
    """A shared boundary satisfies `intersects`, but a PA abutting a sea does not
    lie in it — the line intersection is an artifact of clipping, not a member."""
    _patch_iho(monkeypatch)
    features = _wdpa_frame([box(-5, 0, 0, 10)], pids=["adjacent"])

    assert intersect_with_iho(features, ["WDPA_PID"], with_geometry=True).empty


def test_geometry_join_drops_an_areal_feature_touching_a_sea_at_a_corner(monkeypatch):
    """Cornering a sea intersects to a Point rather than a line, and is the same
    kind of artifact: what makes a pair real is the feature having area here,
    not the shape the intersection happens to take."""
    _patch_iho(monkeypatch)
    features = _wdpa_frame([box(-5, -5, 0, 0)], pids=["corner"])

    assert intersect_with_iho(features, ["WDPA_PID"], with_geometry=True).empty


def test_geometry_join_keeps_point_features_with_no_geometry(monkeypatch):
    """A point PA has no area to clip, so a null result is expected rather than
    an artifact: it sits in the sea and the protected areas table attributes it
    there like any other member."""
    _patch_iho(monkeypatch)
    features = _wdpa_frame([box(1, 1, 2, 2), Point(3, 3)], pids=["polygon", "point"])

    result = intersect_with_iho(features, ["WDPA_PID"], with_geometry=True)

    assert result["WDPA_PID"].tolist() == ["polygon", "point"]
    assert result.geometry.notna().tolist() == [True, False]


def test_geometry_join_keeps_every_membership_pair_except_boundary_touches(monkeypatch):
    """Asking for geometry may only shed the touch artifacts. Anything with area,
    and every point member, has to survive or the pairs would understate which
    seas a PA belongs to."""
    _patch_iho(monkeypatch)
    features = _wdpa_frame(
        [box(1, 1, 2, 2), box(5, 1, 15, 2), box(-5, 0, 0, 10), Point(3, 3)],
        pids=["inside", "straddler", "adjacent", "point"],
    )

    members = intersect_with_iho(features, ["WDPA_PID"], with_geometry=False)
    geoms = intersect_with_iho(features, ["WDPA_PID"], with_geometry=True)

    dropped = sorted(
        set(zip(members["WDPA_PID"], members["location"], strict=True))
        - set(zip(geoms["WDPA_PID"], geoms["location"], strict=True))
    )
    assert dropped == [("adjacent", "1")]


def test_geometry_join_keeps_the_polygonal_part_of_a_mixed_intersection(monkeypatch):
    """A feature that both overlaps a sea and touches its boundary intersects to
    a GeometryCollection of polygon + line. Dropping the whole row would lose a
    real overlap, so only the dangling line is discarded."""
    _patch_iho(monkeypatch)
    # box(5, 5, 15, 15) overlaps Sea A in area; box(10, 0, 12, 2) meets it only
    # along the x=10 edge the two seas share.
    straddler = MultiPolygon([box(5, 5, 15, 15), box(10, 0, 12, 2)])

    result = intersect_with_iho(
        _wdpa_frame([straddler], pids=["mixed"]), ["WDPA_PID"], with_geometry=True
    )

    sea_a = result[result["location"] == "1"]
    assert sea_a.geometry.iloc[0].equals(box(5, 5, 10, 10))


def test_geometry_join_carries_the_requested_columns_through(monkeypatch):
    """The artifact has to be self-contained — consumers split by PA_DEF and roll
    up to WDPAID without re-reading the PA file."""
    _patch_iho(monkeypatch)

    result = intersect_with_iho(
        _wdpa_frame([box(1, 1, 2, 2)], WDPAID=["555"], PA_DEF=[1], DESIG_ENG=["Marine Park"]),
        ["WDPA_PID", "WDPAID", "PA_DEF"],
        with_geometry=True,
    )

    assert list(result.columns) == ["WDPA_PID", "WDPAID", "PA_DEF", "location", "geometry"]


def test_geometry_join_can_use_the_buffered_seas(monkeypatch):
    """Habitat callers join against the near-shore layer; everything else uses
    the true boundaries."""
    buffers = []
    _patch_iho(monkeypatch, calls=buffers)

    intersect_with_iho(_wdpa_frame([box(1, 1, 2, 2)]), ["WDPA_PID"], buffer=True)

    assert buffers == [True]
