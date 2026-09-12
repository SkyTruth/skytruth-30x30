"""Tests for the IHO spatial joins in src/methods/iho_pa_intersections.py:
intersect_with_iho and its intersect_wdpa_with_iho / intersect_mpatlas_with_iho
wrappers."""

import geopandas as gpd
from shapely.geometry import MultiPolygon, Point, box

from src.core.commons import add_tolerance_suffix
from src.core.params import WDPA_MARINE_WITH_SEAS_FILE_NAME
from src.methods import iho_pa_intersections
from src.methods.iho_pa_intersections import (
    generate_iho_pa_intersections,
    intersect_mpatlas_with_iho,
    intersect_wdpa_with_iho,
    intersect_with_iho,
)

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

    monkeypatch.setattr(iho_pa_intersections, "load_iho_regions", fake_load_iho_regions)


def _patch_wdpa(monkeypatch, gdf, calls=None):
    def fake_read_json_df(bucket_name, filename, **kwargs):
        if calls is not None:
            calls.append(filename)
        return gdf

    monkeypatch.setattr(iho_pa_intersections, "read_json_df", fake_read_json_df)


def _wdpa_frame(geometries, pids=None, **extra):
    n = len(geometries)
    pids = pids if pids is not None else [str(i) for i in range(n)]
    return gpd.GeoDataFrame(
        {
            "WDPA_PID": pids,
            # Carried through the join so consumers can roll parcels up to their
            # parent, split PAs from OECMs and apply the statistics filter
            # without re-reading the PA file.
            "WDPAID": [pid.split("_")[0] for pid in pids],
            "PA_DEF": [1] * n,
            "STATUS": ["Designated"] * n,
            "DESIG_ENG": ["Marine Protected Area"] * n,
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
    """Sea assignment must use the true IHO boundaries.

    The saved pairs are measured against the published seas, so a buffered join
    would credit a sea with protected area lying outside it."""
    buffers = []
    _patch_iho(monkeypatch, calls=buffers)
    _patch_wdpa(monkeypatch, _wdpa_frame([box(1, 1, 2, 2)]))

    intersect_wdpa_with_iho(bucket="b", tolerance=0.0001)

    assert buffers == [False]


def test_wdpa_iho_join_carries_only_the_columns_consumers_need(monkeypatch):
    """WDPAID travels with the pair so the habitat rollups can reach a parent, and
    PA_DEF, STATUS and DESIG_ENG so the coverage stats can split PAs from OECMs
    and apply the statistics filter. Everything else is left behind for callers
    to merge back on themselves."""
    _patch_iho(monkeypatch)
    _patch_wdpa(monkeypatch, _wdpa_frame([box(1, 1, 2, 2)], ISO3=["FRA"]))

    result = intersect_wdpa_with_iho(bucket="b", tolerance=0.0001)

    assert list(result.columns) == [
        "WDPA_PID",
        "WDPAID",
        "PA_DEF",
        "STATUS",
        "DESIG_ENG",
        "location",
        "geometry",
    ]


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


def test_mpatlas_iho_join_pairs_zones_with_the_seas_they_overlap(monkeypatch):
    _patch_iho(monkeypatch)
    mpa = gpd.GeoDataFrame(
        {"zone_id": [10, 20, 30], "protection_mpaguide_level": ["full", "less", "unknown"]},
        geometry=[box(1, 1, 2, 2), box(11, 1, 12, 2), Point(3, 3)],
        crs="EPSG:4326",
    )
    monkeypatch.setattr(iho_pa_intersections, "read_mpatlas_from_gcs", lambda bucket, filename: mpa)

    result = intersect_mpatlas_with_iho(bucket="b", mpa_file_name="raw/mpatlas.geojson")

    assert list(result.columns) == [
        "zone_id",
        "protection_mpaguide_level",
        "location",
        "geometry",
    ]
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


# ---------- generate_iho_pa_intersections ----------


def _patch_mpatlas(monkeypatch):
    mpa = gpd.GeoDataFrame(
        {"zone_id": [10], "protection_mpaguide_level": ["full"]},
        geometry=[box(1, 1, 2, 2)],
        crs="EPSG:4326",
    )
    monkeypatch.setattr(iho_pa_intersections, "read_mpatlas_from_gcs", lambda bucket, filename: mpa)


def _patch_upload(monkeypatch):
    saved = {}

    def fake_upload_gdf(bucket_name, gdf, destination_blob_name, **kwargs):
        saved[destination_blob_name] = gdf

    monkeypatch.setattr(iho_pa_intersections, "upload_gdf", fake_upload_gdf)

    return saved


def test_generate_reads_the_pa_file_once(monkeypatch):
    """The marine PAs are both joined to the seas and saved with their pairs
    appended, so they are read once and handed to the join."""
    _patch_iho(monkeypatch)
    _patch_mpatlas(monkeypatch)
    _patch_upload(monkeypatch)
    reads = []
    _patch_wdpa(monkeypatch, _wdpa_frame([box(1, 1, 2, 2)], ISO3=["FRA"]), calls=reads)

    generate_iho_pa_intersections(tolerance=0.0001, bucket="b", verbose=False)

    assert reads == ["intermediates/protected_area_geoms/marine_wdpa_0.0001.geojson"]


def test_generate_appends_each_sea_pair_to_the_marine_pas(monkeypatch):
    """A pair's sea rides in ISO3, where the jobs that subtract protected areas
    from a location look for one, so a sea is just another location to them. The
    point PA keeps its own row but has no pair to append: nothing to subtract."""
    _patch_iho(monkeypatch)
    _patch_mpatlas(monkeypatch)
    saved = _patch_upload(monkeypatch)
    _patch_wdpa(
        monkeypatch,
        _wdpa_frame(
            [box(5, 1, 15, 2), Point(3, 3)], pids=["straddler", "point"], ISO3=["FRA", "FRA"]
        ),
    )

    generate_iho_pa_intersections(tolerance=0.0001, bucket="b", verbose=False)

    combined = saved[add_tolerance_suffix(WDPA_MARINE_WITH_SEAS_FILE_NAME, 0.0001)]

    assert sorted(zip(combined["WDPA_PID"], combined["ISO3"], strict=True)) == [
        ("point", "FRA"),
        ("straddler", "1"),
        ("straddler", "2"),
        ("straddler", "FRA"),
    ]
    # the appended rows carry the PA clipped to their own sea
    sea_a = combined[(combined["WDPA_PID"] == "straddler") & (combined["ISO3"] == "1")]
    assert sea_a.geometry.iloc[0].equals(box(5, 1, 10, 2))


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
