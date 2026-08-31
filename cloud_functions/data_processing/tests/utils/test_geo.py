"""Tests for src/utils/geo.py: per-pixel raster areas (compute_pixel_area_map_km2),
robust geometry unioning (robust_unary_union), metric buffering (buffer_km), and
pairwise feature/region intersection (intersect_features_with_regions)."""

import geopandas as gpd
import numpy as np
import pyproj
import pytest
from rasterio.crs import CRS
from rasterio.transform import Affine, from_bounds
from shapely.geometry import MultiPolygon, Point, Polygon, box
from shapely.ops import transform as shp_transform

from src.utils.geo import (
    _ensure_valid,
    _shift_negative_longitudes,
    _wrap_to_180,
    buffer_km,
    compute_pixel_area_map_km2,
    get_area_km2,
    intersect_features_with_regions,
    robust_unary_union,
)

# True WGS84 ellipsoid surface area; the graticule areas should integrate to it.
WGS84_SURFACE_KM2 = 510_065_621
_TO_6933 = pyproj.Transformer.from_crs("EPSG:3857", "EPSG:6933", always_xy=True).transform
GEOD = pyproj.Geod(ellps="WGS84")


def _pixel_area_6933_km2(minx, miny, maxx, maxy):
    """Independent equal-area (EPSG:6933) area of a 3857 pixel box, in km²."""
    return shp_transform(_TO_6933, box(minx, miny, maxx, maxy)).area / 1e6


# Two side-by-side regions sharing the x=10 edge, well away from the poles so
# the equal-area projection stays well behaved.
REGION_A = box(0, 0, 10, 10)
REGION_B = box(10, 0, 20, 10)


def _max_longitude(geom):
    """Largest absolute longitude anywhere in ``geom``."""
    minx, _, maxx, _ = geom.bounds
    return max(abs(minx), abs(maxx))


def _regions(**cols):
    return gpd.GeoDataFrame(
        {"location": ["1", "2"], **cols},
        geometry=[REGION_A, REGION_B],
        crs="EPSG:4326",
    )


def _features(geometries, ids=None):
    ids = ids if ids is not None else list(range(len(geometries)))
    return gpd.GeoDataFrame({"wdpa_pid": ids}, geometry=geometries, crs="EPSG:4326")


# ---------- geographic CRS ----------


def test_geographic_full_globe_sums_to_earth_surface_area():
    transform = from_bounds(-180, -90, 180, 90, 360, 180)
    area_map = compute_pixel_area_map_km2(transform, 360, 180, crs=CRS.from_epsg(4326))
    assert area_map.sum() == pytest.approx(WGS84_SURFACE_KM2, rel=1e-3)


def test_geographic_none_crs_matches_explicit_4326():
    transform = Affine(0.1, 0, -180, 0, -0.1, 90)
    assert np.allclose(
        compute_pixel_area_map_km2(transform, 50, 50, crs=None),
        compute_pixel_area_map_km2(transform, 50, 50, crs=CRS.from_epsg(4326)),
    )


def test_geographic_area_shrinks_toward_poles():
    transform = Affine(1, 0, -180, 0, -1, 90)  # rows run from 90°N downward
    col = compute_pixel_area_map_km2(transform, 1, 180, crs=None)[:, 0]
    assert col[0] < col[90]  # near-pole pixel smaller than equatorial pixel
    assert col[-1] < col[90]


def test_output_shape_matches_width_height():
    transform = Affine(1, 0, 0, 0, -1, 10)
    assert compute_pixel_area_map_km2(transform, 7, 3, crs=None).shape == (3, 7)


# ---------- EPSG:3857 ----------


@pytest.mark.parametrize("origin_y", [0.0, 5_000_000.0, -8_000_000.0])
def test_3857_pixel_area_matches_equal_area_reprojection(origin_y):
    """3857 is conformal, so per-pixel area must come from the latitude-varying
    math; cross-check against the same pixel reprojected to equal-area 6933."""
    pixel, origin_x = 10_000.0, -1_000_000.0
    transform = Affine(pixel, 0, origin_x, 0, -pixel, origin_y)
    area_map = compute_pixel_area_map_km2(transform, 1, 1, crs=CRS.from_epsg(3857))
    expected = _pixel_area_6933_km2(origin_x, origin_y - pixel, origin_x + pixel, origin_y)
    assert area_map[0, 0] == pytest.approx(expected, rel=1e-4)


def test_3857_area_varies_with_latitude():
    pixel = 100_000.0
    equator = compute_pixel_area_map_km2(
        Affine(pixel, 0, 0, 0, -pixel, pixel), 1, 1, crs=CRS.from_epsg(3857)
    )
    high_lat = compute_pixel_area_map_km2(
        Affine(pixel, 0, 0, 0, -pixel, 8_000_000 + pixel), 1, 1, crs=CRS.from_epsg(3857)
    )
    assert equator[0, 0] > high_lat[0, 0]


# ---------- unsupported CRS (non-happy path) ----------


def test_unsupported_projected_crs_raises():
    transform = Affine(30, 0, 500_000, 0, -30, 4_000_000)
    with pytest.raises(NotImplementedError, match="EPSG:3857"):
        compute_pixel_area_map_km2(transform, 10, 10, crs=CRS.from_epsg(32633))  # UTM 33N


def test_projected_crs_without_epsg_code_raises():
    # A projected CRS that doesn't resolve to an EPSG code must still refuse
    # rather than silently mis-measuring (epsg falls back to None).
    crs = CRS.from_proj4("+proj=laea +lat_0=0 +lon_0=0 +datum=WGS84 +units=m")
    transform = Affine(1000, 0, 0, 0, -1000, 0)
    with pytest.raises(NotImplementedError):
        compute_pixel_area_map_km2(transform, 5, 5, crs=crs)


# ---------- anchored to the real EPSG:3857 coral raster ----------


def test_coral_raster_transform_matches_equal_area():
    """Anchor on the actual gdalinfo transform of the 250 m EPSG:3857 coral
    raster (our concrete use case for the 3857 branch)."""
    origin_x, origin_y, pixel, height = -20037508.178270, 3977092.815081, 250.0, 32192
    transform = Affine(pixel, 0, origin_x, 0, -pixel, origin_y)
    area_map = compute_pixel_area_map_km2(transform, 1, height, crs=CRS.from_epsg(3857))
    for row in (0, height // 2, height - 1):
        top = origin_y - pixel * row
        expected = _pixel_area_6933_km2(origin_x, top - pixel, origin_x + pixel, top)
        assert area_map[row, 0] == pytest.approx(expected, rel=1e-4)


# ---------- robust_unary_union ----------


def test_robust_unary_union_merges_overlapping_boxes():
    result = robust_unary_union([box(0, 0, 2, 2), box(1, 1, 3, 3)])
    assert result.is_valid
    assert result.area == pytest.approx(7)  # 4 + 4 − 1 overlap


def test_robust_unary_union_handles_invalid_self_intersecting_input():
    """A self-intersecting (invalid) polygon must not raise; it's validated
    before unioning."""
    bowtie = Polygon([(0, 0), (4, 4), (4, 0), (0, 4)])
    assert not bowtie.is_valid
    result = robust_unary_union([bowtie, box(2, 2, 6, 6)])
    assert result.is_valid
    assert result.area > 0


def test_robust_unary_union_empty_input_returns_empty():
    result = robust_unary_union([])
    assert result.is_empty


# ---------- buffer_km ----------


def test_buffer_km_radius_is_geodesically_accurate():
    """AEQD projection is centred on the geometry. Buffering a point
    must put every vertex exactly ``km`` away on the ellipsoid."""
    lon, lat, km = 12.0, -37.0, 100
    result = buffer_km(Point(lon, lat), km=km)

    xs, ys = result.exterior.coords.xy
    distances = [GEOD.inv(lon, lat, x, y)[2] for x, y in zip(xs, ys, strict=True)]
    assert min(distances) == pytest.approx(km * 1_000, rel=1e-3)
    assert max(distances) == pytest.approx(km * 1_000, rel=1e-3)


def test_buffer_km_contains_original_and_grows_with_distance():
    sea = box(-5, -5, 5, 5)
    small = buffer_km(sea, km=10)
    large = buffer_km(sea, km=200)

    assert small.contains(sea)
    assert large.contains(small)


def test_buffer_km_rejects_non_wgs84_input():
    """Reprojecting internally would cost two extra passes over every coordinate,
    so a non-4326 CRS is refused rather than silently handled."""
    with pytest.raises(ValueError, match="EPSG:4326"):
        buffer_km(box(0, 0, 1, 1), km=5, src_crs="EPSG:3857")


@pytest.mark.parametrize(
    "polar",
    [box(-10, 89.9995, 10, 90), box(-10, -90, 10, -89.9995)],
    ids=["north", "south"],
)
def test_buffer_km_rejects_pole_touching_geometry(polar):
    with pytest.raises(NotImplementedError, match="pole"):
        buffer_km(polar, km=5)


@pytest.mark.parametrize("geom", [None, Polygon()], ids=["none", "empty"])
def test_buffer_km_passes_through_none_and_empty(geom):
    assert buffer_km(geom, km=5) is geom


def test_buffer_km_repairs_invalid_input():
    """``process_buffered_iho`` relies on the result being valid, so an invalid
    input must come back repaired rather than propagating."""
    bowtie = Polygon([(0, 0), (2, 2), (2, 0), (0, 2)])
    assert not bowtie.is_valid

    result = buffer_km(bowtie, km=10)
    assert result.is_valid
    assert result.area > 0


def test_buffer_km_splits_antimeridian_crossing_geometry():
    """A span wider than 180° is read as crossing the antimeridian: it is shifted
    into 0–360 to be buffered continuously, then split back into -180–180 parts."""
    # minx/maxx of -170/170 spans 340°, so this is the 20°-wide strip through 180°.
    crossing = box(-170, -5, 170, 5)
    result = buffer_km(crossing, km=50)

    assert result.is_valid
    assert isinstance(result, MultiPolygon)
    assert len(result.geoms) == 2
    assert _max_longitude(result) <= 180

    # One part hugs each side of the antimeridian.
    assert {geom.bounds[0] < -170 for geom in result.geoms} == {True, False}


def test_buffer_km_keeps_ordinary_geometry_off_the_antimeridian():
    """The >180° span check must not fire on a normal mid-ocean polygon."""
    result = buffer_km(box(-20, -5, 20, 5), km=50)

    assert isinstance(result, Polygon)
    assert result.bounds[0] < -20 and result.bounds[2] > 20


# ---------- _wrap_to_180 ----------


def test_wrap_to_180_leaves_in_range_geometry_alone():
    assert _wrap_to_180(box(0, 0, 10, 10)).area == pytest.approx(100)


def test_wrap_to_180_splits_geometry_crossing_antimeridian():
    """An unwrapped 170–190 strip becomes two parts, with total area preserved."""
    result = _wrap_to_180(box(170, 0, 190, 10))

    assert isinstance(result, MultiPolygon)
    assert len(result.geoms) == 2
    assert result.area == pytest.approx(200)
    assert _max_longitude(result) <= 180


def test_wrap_to_180_translates_fully_shifted_geometry():
    """Wholly beyond 180 means no split, just a translation back into range."""
    result = _wrap_to_180(box(200, 0, 210, 10))

    assert result.bounds == pytest.approx((-160, 0, -150, 10))
    assert result.area == pytest.approx(100)


@pytest.mark.parametrize("geom", [None, Polygon()], ids=["none", "empty"])
def test_wrap_to_180_passes_through_none_and_empty(geom):
    assert _wrap_to_180(geom) is geom


# ---------- _ensure_valid / _shift_negative_longitudes ----------


def test_ensure_valid_returns_already_valid_geometry_untouched():
    """The whole point of the is_valid check is to skip make_valid's rebuild,
    so a valid geometry must come back as the same object."""
    valid = box(0, 0, 1, 1)
    assert _ensure_valid(valid) is valid


def test_ensure_valid_repairs_invalid_geometry():
    bowtie = Polygon([(0, 0), (2, 2), (2, 0), (0, 2)])
    assert not bowtie.is_valid
    assert _ensure_valid(bowtie).is_valid


def test_shift_negative_longitudes_handles_scalars_and_arrays():
    assert _shift_negative_longitudes(-170.0, 5.0) == (190.0, 5.0)
    assert _shift_negative_longitudes(170.0, 5.0) == (170.0, 5.0)

    shifted_x, y = _shift_negative_longitudes(np.array([-170.0, 170.0]), np.array([5.0, 5.0]))
    assert np.allclose(shifted_x, [190.0, 170.0])
    assert np.allclose(y, [5.0, 5.0])


def test_shift_negative_longitudes_preserves_z():
    assert _shift_negative_longitudes(-170.0, 5.0, 3.0) == (190.0, 5.0, 3.0)


# ---------- intersect_features_with_regions ----------


def test_intersect_feature_inside_one_region_returns_its_whole_area():
    feature = box(1, 1, 2, 2)
    result = intersect_features_with_regions(_features([feature]), _regions())

    assert len(result) == 1
    assert result.iloc[0]["location"] == "1"
    assert result.iloc[0]["intersection_area_km2"] == pytest.approx(get_area_km2(feature), rel=1e-6)


def test_intersect_straddling_feature_splits_across_regions():
    feature = box(5, 1, 15, 2)  # half in REGION_A, half in REGION_B
    result = intersect_features_with_regions(_features([feature]), _regions())

    by_region = dict(zip(result["location"], result["intersection_area_km2"], strict=True))
    assert sorted(by_region) == ["1", "2"]
    assert by_region["1"] == pytest.approx(get_area_km2(box(5, 1, 10, 2)), rel=1e-6)
    assert by_region["2"] == pytest.approx(get_area_km2(box(10, 1, 15, 2)), rel=1e-6)
    assert result["intersection_area_km2"].sum() == pytest.approx(get_area_km2(feature), rel=1e-6)


def test_intersect_excludes_feature_that_only_touches_a_region():
    """Shares the x=0 edge with REGION_A, so it intersects but has no area
    inside it. `keep_geom_type` must drop the resulting line."""
    result = intersect_features_with_regions(_features([box(-5, 0, 0, 10)]), _regions())

    assert result.empty


def test_intersect_omits_features_and_regions_with_no_overlap():
    inside_a = box(1, 1, 2, 2)
    far_away = box(100, 50, 101, 51)
    result = intersect_features_with_regions(
        _features([inside_a, far_away], ids=["in", "out"]), _regions()
    )

    # Only the one real overlap: no row for the distant feature, none for REGION_B.
    assert result["wdpa_pid"].tolist() == ["in"]


def test_intersect_carries_through_columns_from_both_frames():
    features = gpd.GeoDataFrame(
        {"wdpaid": [555], "wdpa_pid": ["555A"], "data_source": ["protected-planet"]},
        geometry=[box(1, 1, 2, 2)],
        crs="EPSG:4326",
    )
    result = intersect_features_with_regions(features, _regions(NAME=["Sea A", "Sea B"]))

    assert result.iloc[0][["wdpaid", "wdpa_pid", "data_source", "location", "NAME"]].tolist() == [
        555,
        "555A",
        "protected-planet",
        "1",
        "Sea A",
    ]


def test_intersect_suffixes_columns_present_in_both_frames():
    """`location` on both sides is a real possibility — PA rows carry an ISO3
    `location` and IHO regions carry an MRGID one — so the collision must be
    visible rather than silently resolved."""
    features = gpd.GeoDataFrame({"location": ["FRA"]}, geometry=[box(1, 1, 2, 2)], crs="EPSG:4326")
    result = intersect_features_with_regions(features, _regions())

    assert result.iloc[0]["location_1"] == "FRA"
    assert result.iloc[0]["location_2"] == "1"


def test_intersect_repairs_invalid_feature_geometry():
    bowtie = Polygon([(1, 1), (3, 3), (3, 1), (1, 3), (1, 1)])
    assert not bowtie.is_valid

    result = intersect_features_with_regions(_features([bowtie]), _regions())

    assert len(result) == 1
    assert result.iloc[0]["intersection_area_km2"] > 0


def test_intersect_ignores_rows_with_missing_or_empty_geometry():
    features = _features([box(1, 1, 2, 2), None, Polygon()], ids=["real", "null", "empty"])
    result = intersect_features_with_regions(features, _regions())

    assert result["wdpa_pid"].tolist() == ["real"]


def test_intersect_locates_arealess_features_with_zero_area():
    """A point inside a region is in that region, so it is paired by containment
    rather than dropped — unlike a polygon that merely touches a boundary. Its area
    is 0, which `keep_geom_type` makes unambiguous: no polygon pair can reach 0."""
    features = _features(
        [box(1, 1, 2, 2), Point(3, 3), Point(15, 5), Point(50, 50)],
        ids=["polygon", "point_a", "point_b", "point_outside"],
    )
    result = intersect_features_with_regions(features, _regions())

    areas = dict(zip(result["wdpa_pid"], result["intersection_area_km2"], strict=True))
    regions = dict(zip(result["wdpa_pid"], result["location"], strict=True))

    assert areas["polygon"] > 0
    assert areas["point_a"] == 0.0 and regions["point_a"] == "1"
    assert areas["point_b"] == 0.0 and regions["point_b"] == "2"
    assert "point_outside" not in areas


def test_intersect_returns_a_geodataframe_when_mixing_geometry_types():
    """`gpd.overlay` rejects a mixed frame outright, so the two paths are run
    separately and stitched — the result must still be a projected GeoDataFrame."""
    features = _features([box(1, 1, 2, 2), Point(3, 3)], ids=["polygon", "point"])
    result = intersect_features_with_regions(features, _regions())

    assert isinstance(result, gpd.GeoDataFrame)
    assert result.crs == "EPSG:6933"
    assert result["intersection_area_km2"].dtype == "float64"


@pytest.mark.parametrize("empty_side", ["features", "regions"])
def test_intersect_empty_input_returns_empty_frame(empty_side):
    features = _features([box(1, 1, 2, 2)])
    regions = _regions()
    if empty_side == "features":
        features = features.iloc[:0]
    else:
        regions = regions.iloc[:0]

    result = intersect_features_with_regions(features, regions)

    assert result.empty
    assert "intersection_area_km2" in result.columns


def test_intersect_rejects_frames_without_a_crs():
    """Areas are only meaningful once reprojected, so naive geometry must not
    silently produce square-degree numbers."""
    features = _features([box(1, 1, 2, 2)]).set_crs(None, allow_override=True)

    with pytest.raises(ValueError, match="naive geometries"):
        intersect_features_with_regions(features, _regions())


def test_intersect_honours_a_renamed_geometry_column():
    features = _features([box(1, 1, 2, 2)]).rename_geometry("footprint")
    regions = _regions().rename_geometry("shape")

    result = intersect_features_with_regions(features, regions)

    assert len(result) == 1
    assert result.iloc[0]["intersection_area_km2"] > 0
