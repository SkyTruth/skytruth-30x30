import ast

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import MultiPoint, Point, box
from shapely.ops import unary_union

import src.methods.iho_pa_intersections as iho_pa_intersections
import src.methods.protection_coverage as protection_coverage
from src.core.processors import filter_protected_planet


def _iho_gdf(rows):
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:6933")


def _wdpa_pairs_gdf(rows, location="sea"):
    """Build (PA, sea) pairs, defaulting rows to values the coverage filter keeps.

    Each row is one PA already clipped to ``location``, so a row's geometry is
    its contribution to that sea. Points arrive with a null geometry.
    """
    return gpd.GeoDataFrame(
        [
            {
                "WDPA_PID": str(i),
                "WDPAID": str(i),
                "PA_DEF": 1,
                "STATUS": "Designated",
                "DESIG_ENG": "Marine Protected Area",
                "environment": "marine",
                "location": location,
                **row,
            }
            for i, row in enumerate(rows)
        ],
        geometry="geometry",
        crs="EPSG:6933",
    )


def _run_coverage(monkeypatch, iho, pairs, wdpa_global):
    monkeypatch.setattr(
        protection_coverage,
        "load_iho_regions",
        lambda: iho.copy(),
    )
    monkeypatch.setattr(
        protection_coverage,
        "read_parquet_from_gcs",
        lambda *_, **__: pairs.copy(),
    )
    monkeypatch.setattr(
        protection_coverage, "load_wdpa_global", lambda *_, **__: wdpa_global.copy()
    )
    return protection_coverage.compute_iho_protection_coverage(
        bucket="bucket", tolerance=0.1, verbose=False
    )


@pytest.fixture
def wdpa_country():
    """Minimal country-level marine and terrestrial WDPA statistics."""
    return pd.DataFrame(
        {
            "id": ["BRA"],
            "pas_count": [10],
            "statistics": [
                str(
                    {
                        "marine_area": 1000.0,
                        "oecms_pa_marine_area": 100.0,
                        "percentage_oecms_pa_marine_cover": 10.0,
                        "pa_marine_area": 80.0,
                        "percentage_pa_marine_cover": 8.0,
                        "protected_area_polygon_count": 5,
                        "protected_area_point_count": 2,
                        "oecm_polygon_count": 1,
                        "oecm_point_count": 0,
                        "land_area": 2000.0,
                        "oecms_pa_land_area": 200.0,
                        "percentage_oecms_pa_land_cover": 10.0,
                        "pa_land_area": 160.0,
                        "percentage_pa_land_cover": 8.0,
                    }
                )
            ],
        }
    )


@pytest.fixture
def wdpa_global():
    """Minimal global WDPA values used for GLOB and ABNJ calculations."""
    return pd.DataFrame(
        {
            "type": [
                "total_ocean_area_oecms_pas",
                "total_ocean_area_oecms",
                "total_ocean_oecms_pas_coverage_percentage",
                "total_marine_oecms_pas",
                "total_land_area_oecms_pas",
                "total_land_area_oecms",
                "total_land_oecms_pas_coverage_percentage",
                "total_terrestrial_oecms_pas",
                "high_seas_pa_coverage_area",
                "high_seas_pa_coverage_percentage",
                "national_waters_oecms_coverage_area",
                "national_waters_oecms_pas_coverage_area",
                "global_ocean_percentage",
            ],
            "value": [
                36_319_197.0,
                5_000_000.0,
                10.0,
                500,
                15_000_000.0,
                3_000_000.0,
                10.0,
                300,
                1_000_000.0,
                1.75,
                20_000_000.0,
                25_000_000.0,
                64.0,
            ],
        }
    )


@pytest.fixture
def combined_regions():
    """Country and global groupings needed by the coverage calculation."""
    return {"BRA": ["BRA"], "GLOB": []}


def _run_country_global_coverage(monkeypatch, wdpa_country, wdpa_global, combined_regions):
    monkeypatch.setattr(protection_coverage, "load_regions", lambda **_: (combined_regions, {}))
    monkeypatch.setattr(protection_coverage, "read_dataframe", lambda *_, **__: wdpa_country.copy())
    monkeypatch.setattr(
        protection_coverage, "load_wdpa_global", lambda *_, **__: wdpa_global.copy()
    )
    table, country_areas = protection_coverage.compute_country_global_coverage(verbose=False)
    return table, country_areas


def _get_country_global_row(df, location, environment="marine"):
    rows = df[(df["location"] == location) & (df["environment"] == environment)]
    assert len(rows) == 1, f"Expected 1 row for {location}/{environment}, got {len(rows)}"
    return rows.iloc[0]


def _global_value(wdpa_global, stat_type):
    return float(wdpa_global.loc[wdpa_global["type"] == stat_type, "value"].iloc[0])


def _global_area(wdpa_global, environment2):
    """Global area the fixture implies: its protected area over the share of the globe it covers."""
    protected_area = _global_value(wdpa_global, f"total_{environment2}_area_oecms_pas")
    coverage = _global_value(wdpa_global, f"total_{environment2}_oecms_pas_coverage_percentage")
    return protected_area * 100 / coverage


def _country_stat(wdpa_country, key):
    return ast.literal_eval(wdpa_country["statistics"].iloc[0])[key]


def test_country_global_coverage_calculates_global_marine_area(
    monkeypatch, wdpa_country, wdpa_global, combined_regions
):
    """Back-calculate global marine area from protected area and coverage."""
    table, _ = _run_country_global_coverage(
        monkeypatch, wdpa_country, wdpa_global, combined_regions
    )

    row = _get_country_global_row(table, "GLOB")
    assert row["total_area"] == pytest.approx(_global_area(wdpa_global, "ocean"))


def test_country_global_coverage_calculates_global_terrestrial_area(
    monkeypatch, wdpa_country, wdpa_global, combined_regions
):
    """Back-calculate global terrestrial area from protected area and coverage."""
    table, _ = _run_country_global_coverage(
        monkeypatch, wdpa_country, wdpa_global, combined_regions
    )

    row = _get_country_global_row(table, "GLOB", environment="terrestrial")
    assert row["total_area"] == pytest.approx(_global_area(wdpa_global, "land"))


def test_country_global_coverage_sets_global_contribution(
    monkeypatch, wdpa_country, wdpa_global, combined_regions
):
    """Use global coverage as the global row's contribution percentage."""
    table, _ = _run_country_global_coverage(
        monkeypatch, wdpa_country, wdpa_global, combined_regions
    )

    row = _get_country_global_row(table, "GLOB")
    assert row["global_contribution"] == _global_value(
        wdpa_global, "total_ocean_oecms_pas_coverage_percentage"
    )


def test_country_global_coverage_measures_group_contribution_against_global_area(
    monkeypatch, wdpa_country, wdpa_global, combined_regions
):
    """Compare a group's protected area to the global area, not to its own coverage."""
    table, _ = _run_country_global_coverage(
        monkeypatch, wdpa_country, wdpa_global, combined_regions
    )

    marine = _get_country_global_row(table, "BRA")
    terrestrial = _get_country_global_row(table, "BRA", environment="terrestrial")

    assert marine["global_contribution"] == pytest.approx(
        100
        * _country_stat(wdpa_country, "oecms_pa_marine_area")
        / _global_area(wdpa_global, "ocean")
    )
    assert terrestrial["global_contribution"] == pytest.approx(
        100 * _country_stat(wdpa_country, "oecms_pa_land_area") / _global_area(wdpa_global, "land")
    )


def test_country_global_coverage_calculates_unrounded_abnj_area(
    monkeypatch, wdpa_country, wdpa_global, combined_regions
):
    """Calculate ABNJ area without the table wrapper's output rounding."""
    table, _ = _run_country_global_coverage(
        monkeypatch, wdpa_country, wdpa_global, combined_regions
    )

    row = _get_country_global_row(table, "ABNJ")
    assert row["total_area"] == pytest.approx(
        _global_area(wdpa_global, "ocean")
        * _global_value(wdpa_global, "global_ocean_percentage")
        / 100
    )


def test_iho_coverage_reports_a_sea_with_no_pairs_as_uncovered(monkeypatch, wdpa_global):
    """Every sea gets a row, so a sea no PA reaches reports zeros rather than vanishing.

    A PA that does not overlap a sea simply has no pair for it.
    """
    iho = _iho_gdf([{"MRGID": 10, "geometry": box(0, 0, 1000, 1000)}])
    elsewhere = _wdpa_pairs_gdf(
        [{"PA_DEF": 1, "geometry": box(5000, 5000, 6000, 6000)}], location="999"
    )

    result = _run_coverage(monkeypatch, iho, elsewhere, wdpa_global).iloc[0]

    assert result["location"] == "10"
    assert result["environment"] == "marine"
    assert result["total_area"] == 1.0
    assert result["protected_area"] == 0.0
    assert result["coverage"] == 0.0
    assert result["pas"] == 0.0
    assert result["oecms"] == 0.0
    assert result["protected_areas_count"] == 0
    assert result["global_contribution"] == 0.0


def test_iho_coverage_ignores_pairs_belonging_to_other_environments(monkeypatch, wdpa_global):
    """Marine coverage must skip any pair that is not marine.

    The writer emits marine pairs only, so nothing exercises this today. It is
    the filter that keeps adding the terrestrial estate back to the pairs file a
    safe change, which is why the guard stays.
    """
    iho = _iho_gdf([{"MRGID": "sea", "geometry": box(0, 0, 2000, 1000)}])
    pairs = _wdpa_pairs_gdf(
        [
            {"PA_DEF": 1, "geometry": box(0, 0, 500, 1000)},
            {"PA_DEF": 1, "environment": "terrestrial", "geometry": box(1000, 0, 1500, 1000)},
        ]
    )

    result = _run_coverage(monkeypatch, iho, pairs, wdpa_global).iloc[0]

    assert result["protected_area"] == 0.5
    assert result["coverage"] == 25.0
    assert result["protected_areas_count"] == 1


def test_iho_coverage_dissolves_overlapping_protected_areas(monkeypatch, wdpa_global):
    """Dissolve overlapping protected areas to prevent double-counting."""
    iho = _iho_gdf([{"MRGID": "sea", "geometry": box(0, 0, 2000, 1000)}])
    pairs = _wdpa_pairs_gdf(
        [
            {"PA_DEF": 1, "geometry": box(0, 0, 1200, 1000)},
            {"PA_DEF": 1, "geometry": box(800, 0, 2000, 1000)},
        ]
    )

    result = _run_coverage(monkeypatch, iho, pairs, wdpa_global).iloc[0]

    # The polygons overlap by 0.4 km², so their dissolved union is the 2 km² sea,
    # not the naive 2.4 km² sum.
    assert result["total_area"] == 2.0
    assert result["protected_area"] == 2.0
    assert result["coverage"] == 100.0
    assert result["pas"] == 100.0
    assert result["oecms"] == 0.0
    assert result["protected_areas_count"] == 2


def test_iho_coverage_calculates_pa_and_oecm_shares(monkeypatch, wdpa_global):
    """Calculate overall coverage and the PA/OECM shares of protected area."""
    iho = _iho_gdf([{"MRGID": "sea", "geometry": box(0, 0, 2000, 1000)}])
    pairs = _wdpa_pairs_gdf(
        [
            {"PA_DEF": 1, "geometry": box(0, 0, 500, 1000)},
            {"PA_DEF": 0, "geometry": box(1000, 0, 1500, 1000)},
        ]
    )

    result = _run_coverage(monkeypatch, iho, pairs, wdpa_global).iloc[0]

    assert result["protected_area"] == 1.0
    assert result["coverage"] == 50.0
    assert result["pas"] == 50.0
    assert result["oecms"] == 50.0
    assert result["protected_areas_count"] == 2


def test_iho_coverage_keeps_results_independent_for_each_sea(monkeypatch, wdpa_global):
    """Calculate each IHO sea independently and retain zero-coverage seas."""
    iho = _iho_gdf(
        [
            {"MRGID": 1, "geometry": box(0, 0, 1000, 1000)},
            {"MRGID": 2, "geometry": box(2000, 0, 3000, 1000)},
        ]
    )
    pairs = _wdpa_pairs_gdf([{"PA_DEF": 1, "geometry": box(0, 0, 500, 1000)}], location="1")

    result = _run_coverage(monkeypatch, iho, pairs, wdpa_global).set_index("location")

    assert set(result.index) == {"1", "2"}
    assert result.loc["1", "coverage"] == pytest.approx(50.0)
    assert result.loc["2", "coverage"] == 0.0


def test_iho_coverage_measures_global_contribution_against_global_ocean_area(
    monkeypatch, wdpa_global
):
    """Express a sea's protected area as a share of the whole ocean, not of the sea."""
    # 2 million km² sea, half of it protected.
    iho = _iho_gdf([{"MRGID": "sea", "geometry": box(0, 0, 2_000_000, 1_000_000)}])
    pairs = _wdpa_pairs_gdf([{"PA_DEF": 1, "geometry": box(0, 0, 1_000_000, 1_000_000)}])
    protected_km2 = 1_000_000

    result = _run_coverage(monkeypatch, iho, pairs, wdpa_global).iloc[0]

    assert result["coverage"] == 50.0
    assert result["global_contribution"] == pytest.approx(
        round(100 * protected_km2 / _global_area(wdpa_global, "ocean"), 2)
    )


@pytest.mark.parametrize("excluded_status", ["Proposed", "Not Reported"])
def test_iho_coverage_excludes_sites_protected_planet_leaves_out(
    monkeypatch, wdpa_global, excluded_status
):
    """Exclude proposed and unreported sites, as the country-level statistics already do."""
    iho = _iho_gdf([{"MRGID": "sea", "geometry": box(0, 0, 2000, 1000)}])
    pairs = _wdpa_pairs_gdf(
        [
            {"PA_DEF": 1, "geometry": box(0, 0, 500, 1000)},
            {"PA_DEF": 1, "STATUS": excluded_status, "geometry": box(1000, 0, 1500, 1000)},
        ]
    )

    result = _run_coverage(monkeypatch, iho, pairs, wdpa_global).iloc[0]

    # Only the designated 0.5 km² site may reach the area, coverage and count.
    assert result["protected_area"] == 0.5
    assert result["coverage"] == 25.0
    assert result["protected_areas_count"] == 1


@pytest.mark.parametrize("kept_status", ["Designated", "Established", "Inscribed", "Adopted"])
def test_iho_coverage_keeps_every_status_protected_planet_counts(
    monkeypatch, wdpa_global, kept_status
):
    """Keep the non-designated statuses that Protected Planet still counts as coverage."""
    iho = _iho_gdf([{"MRGID": "sea", "geometry": box(0, 0, 2000, 1000)}])
    pairs = _wdpa_pairs_gdf(
        [{"PA_DEF": 1, "STATUS": kept_status, "geometry": box(0, 0, 1000, 1000)}]
    )

    result = _run_coverage(monkeypatch, iho, pairs, wdpa_global).iloc[0]

    assert result["protected_area"] == 1.0
    assert result["coverage"] == 50.0
    assert result["protected_areas_count"] == 1


def test_iho_coverage_returns_zero_when_every_site_is_filtered_out(monkeypatch, wdpa_global):
    """Report a sea as uncovered when the filter removes all of its sites."""
    iho = _iho_gdf([{"MRGID": "sea", "geometry": box(0, 0, 2000, 1000)}])
    pairs = _wdpa_pairs_gdf(
        [{"PA_DEF": 1, "STATUS": "Proposed", "geometry": box(0, 0, 1000, 1000)}]
    )

    result = _run_coverage(monkeypatch, iho, pairs, wdpa_global).iloc[0]

    assert result["protected_area"] == 0.0
    assert result["coverage"] == 0.0
    assert result["protected_areas_count"] == 0


@pytest.mark.parametrize(
    "point",
    [None, Point(250, 500), MultiPoint([(250, 500), (300, 500)])],
    ids=["null", "point", "multipoint"],
)
def test_iho_coverage_excludes_points_with_no_reported_area(monkeypatch, wdpa_global, point):
    """Exclude sites left as points, which reported no area to buffer into a polygon.

    They contribute no area either way, but counting them would inflate the site
    count. A point has nothing to clip to a sea, so its pair carries a null
    geometry; the point geometries cover the case of one reaching the pairs intact.
    """
    iho = _iho_gdf([{"MRGID": "sea", "geometry": box(0, 0, 2000, 1000)}])
    pairs = _wdpa_pairs_gdf(
        [
            {"PA_DEF": 1, "geometry": box(0, 0, 500, 1000)},
            {"PA_DEF": 1, "geometry": point},
        ]
    )

    result = _run_coverage(monkeypatch, iho, pairs, wdpa_global).iloc[0]

    assert result["protected_area"] == 0.5
    assert result["coverage"] == 25.0
    assert result["protected_areas_count"] == 1


def test_iho_coverage_keeps_polygons_however_small(monkeypatch, wdpa_global):
    """Only points are dropped for want of an area.

    A polygon carries its own geometry, so it is measured whatever its provider
    reported.
    """
    iho = _iho_gdf([{"MRGID": "sea", "geometry": box(0, 0, 2000, 1000)}])
    pairs = _wdpa_pairs_gdf([{"PA_DEF": 1, "geometry": box(0, 0, 1000, 1000)}])

    result = _run_coverage(monkeypatch, iho, pairs, wdpa_global).iloc[0]

    assert result["protected_area"] == 1.0
    assert result["coverage"] == 50.0
    assert result["protected_areas_count"] == 1


def test_iho_coverage_keeps_points_already_buffered_into_polygons(monkeypatch, wdpa_global):
    """Keep sites submitted as points that reported an area.

    The download step buffers those into circular polygons, so they reach the filter as
    polygons and must survive it.
    """
    iho = _iho_gdf([{"MRGID": "sea", "geometry": box(0, 0, 2000, 1000)}])
    buffered_point = Point(500, 500).buffer(200)
    pairs = _wdpa_pairs_gdf([{"PA_DEF": 1, "geometry": buffered_point}])

    result = _run_coverage(monkeypatch, iho, pairs, wdpa_global).iloc[0]

    assert result["protected_areas_count"] == 1
    # The function rounds to two decimals, and buffer() approximates the circle.
    assert result["protected_area"] == round(buffered_point.area / 1e6, 2)
    assert result["protected_area"] > 0


def test_iho_coverage_excludes_biosphere_reserves_that_are_not_oecms(monkeypatch, wdpa_global):
    """Exclude MAB reserves recorded as protected areas, as Protected Planet does.

    Their buffer and transition zones are not themselves protected, so counting the
    whole reserve would overstate coverage. They stay in the PA table and tilesets.
    """
    iho = _iho_gdf([{"MRGID": "sea", "geometry": box(0, 0, 2000, 1000)}])
    pairs = _wdpa_pairs_gdf(
        [
            {"PA_DEF": 1, "geometry": box(0, 0, 500, 1000)},
            {
                "PA_DEF": 1,
                "DESIG_ENG": "UNESCO-MAB Biosphere Reserve",
                "geometry": box(1000, 0, 1500, 1000),
            },
        ]
    )

    result = _run_coverage(monkeypatch, iho, pairs, wdpa_global).iloc[0]

    # Only the 0.5 km² non-MAB site may reach the area, coverage and count.
    assert result["protected_area"] == 0.5
    assert result["coverage"] == 25.0
    assert result["protected_areas_count"] == 1


def test_iho_coverage_keeps_biosphere_reserves_recorded_as_oecms(monkeypatch, wdpa_global):
    """Keep MAB reserves that are also OECMs, which Protected Planet does count."""
    iho = _iho_gdf([{"MRGID": "sea", "geometry": box(0, 0, 2000, 1000)}])
    pairs = _wdpa_pairs_gdf(
        [
            {
                "PA_DEF": 0,
                "DESIG_ENG": "UNESCO-MAB Biosphere Reserve",
                "geometry": box(0, 0, 1000, 1000),
            }
        ]
    )

    result = _run_coverage(monkeypatch, iho, pairs, wdpa_global).iloc[0]

    assert result["protected_area"] == 1.0
    assert result["coverage"] == 50.0
    assert result["protected_areas_count"] == 1


def test_iho_coverage_matches_a_direct_join_of_pas_against_seas(monkeypatch, wdpa_global):
    """Reading saved pairs gives the areas a direct PA/sea join gives.

    The pairs are built by the real ``intersect_with_iho`` and then measured,
    while the reference filters the same PAs, joins them to the same seas and
    unions per sea in the equal-area projection. Every PA here sits strictly
    inside a sea, since a PA merely touching one is a pair the join drops but a
    plain ``intersects`` would keep.
    """
    seas = gpd.GeoDataFrame(
        {
            "MRGID": [1, 2],
            "location": ["1", "2"],
            "geometry": [box(0, 0, 10, 10), box(10, 0, 20, 10)],
        },
        geometry="geometry",
        crs="EPSG:4326",
    )
    pas = gpd.GeoDataFrame(
        {
            "WDPA_PID": ["a", "b", "c", "d", "e"],
            "WDPAID": ["a", "b", "c", "d", "e"],
            "PA_DEF": [1, 0, 1, 1, 1],
            "STATUS": ["Designated", "Designated", "Proposed", "Designated", "Designated"],
            "DESIG_ENG": [
                "Marine Protected Area",
                "Marine Protected Area",
                "Marine Protected Area",
                "UNESCO-MAB Biosphere Reserve",
                "Marine Protected Area",
            ],
            # a and b overlap inside sea 1, c and d are filtered out, e sits in sea 2
            "geometry": [
                box(1, 1, 6, 6),
                box(4, 1, 8, 6),
                box(1, 7, 3, 9),
                box(5, 7, 7, 9),
                box(12, 1, 16, 6),
            ],
        },
        geometry="geometry",
        crs="EPSG:4326",
    )

    seas_proj = seas.to_crs(epsg=6933)
    kept = pas.pipe(filter_protected_planet).to_crs(epsg=6933)
    sindex = kept.sindex
    expected = {}
    for _, sea in seas_proj.iterrows():
        actual = kept.iloc[list(sindex.intersection(sea.geometry.bounds))]
        actual = actual[actual.intersects(sea.geometry)]
        total_area = round(sea.geometry.area / 1e6, 2)
        protected_area = sea.geometry.intersection(unary_union(actual.geometry)).area / 1e6
        expected[str(sea["MRGID"])] = {
            "protected_area": round(protected_area, 2),
            "coverage": round(100 * protected_area / total_area, 2),
            "protected_areas_count": len(actual),
        }

    monkeypatch.setattr(iho_pa_intersections, "load_iho_regions", lambda buffer=False: seas.copy())
    pairs = iho_pa_intersections.intersect_with_iho(
        pas,
        ["WDPA_PID", "WDPAID", "PA_DEF", "STATUS", "DESIG_ENG"],
        with_geometry=True,
    ).assign(environment="marine")

    result = _run_coverage(monkeypatch, seas, pairs, wdpa_global).set_index("location")

    for location, stats in expected.items():
        for field, value in stats.items():
            assert result.loc[location, field] == pytest.approx(value, rel=1e-9), (
                f"{location}/{field}"
            )


# ---------------------------------------------------------------------------
# compute_iho_protection_level
# ---------------------------------------------------------------------------


def _sea_gdf(rows):
    """IHO sea areas as load_iho_regions returns them, in the published CRS."""
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")


def _pairs_gdf(rows):
    """(zone, sea) pairs as generate_iho_pa_intersections saves them.

    Each row is one zone clipped to one sea, defaulting to a protection level
    the filter keeps.
    """
    return gpd.GeoDataFrame(
        [{"zone_id": i, "protection_mpaguide_level": "full", **row} for i, row in enumerate(rows)],
        geometry="geometry",
        crs="EPSG:4326",
    )


def _run_protection_level(monkeypatch, pairs, seas):
    monkeypatch.setattr(protection_coverage, "read_parquet_from_gcs", lambda *a, **kw: pairs.copy())
    monkeypatch.setattr(protection_coverage, "load_iho_regions", lambda: seas.copy())
    return protection_coverage.compute_iho_protection_level(bucket="bucket", verbose=False)


def test_protection_level_reports_one_row_per_sea_holding_a_qualifying_zone(monkeypatch):
    """A sea with no fully or highly protected zone contributes no row at all."""
    seas = _sea_gdf(
        [
            {"location": "1", "geometry": box(0, 0, 10, 10)},
            {"location": "2", "geometry": box(10, 0, 20, 10)},
            {"location": "3", "geometry": box(20, 0, 30, 10)},
        ]
    )
    pairs = _pairs_gdf(
        [
            {"location": "1", "geometry": box(0, 0, 5, 10)},
            {"location": "2", "geometry": box(10, 0, 12, 10)},
        ]
    )

    result = _run_protection_level(monkeypatch, pairs, seas)

    assert sorted(result["location"]) == ["1", "2"]
    assert set(result["mpaa_protection_level"]) == {"fully-highly-protected"}


@pytest.mark.parametrize("level", ["full", "high"])
def test_protection_level_counts_fully_and_highly_protected_zones(monkeypatch, level):
    seas = _sea_gdf([{"location": "1", "geometry": box(0, 0, 10, 10)}])
    pairs = _pairs_gdf(
        [{"location": "1", "protection_mpaguide_level": level, "geometry": box(0, 0, 5, 10)}]
    )

    result = _run_protection_level(monkeypatch, pairs, seas)

    assert result["location"].tolist() == ["1"]


@pytest.mark.parametrize("level", ["less", "incompatible", "unknown"])
def test_protection_level_excludes_weaker_protection_levels(monkeypatch, level):
    """Only the fully and highly protected zones count toward this stat."""
    seas = _sea_gdf([{"location": "1", "geometry": box(0, 0, 10, 10)}])
    pairs = _pairs_gdf(
        [{"location": "1", "protection_mpaguide_level": level, "geometry": box(0, 0, 5, 10)}]
    )

    assert _run_protection_level(monkeypatch, pairs, seas).empty


def test_protection_level_ignores_point_zones_carrying_no_geometry(monkeypatch):
    """Point zones ride along on the pairs with a null geometry and no area.

    They must neither contribute area nor break the dissolve.
    """
    seas = _sea_gdf([{"location": "1", "geometry": box(0, 0, 10, 10)}])
    pairs = _pairs_gdf(
        [
            {"location": "1", "geometry": box(0, 0, 5, 10)},
            {"location": "1", "geometry": None},
        ]
    )

    result = _run_protection_level(monkeypatch, pairs, seas)
    only_polygon = _run_protection_level(
        monkeypatch, _pairs_gdf([{"location": "1", "geometry": box(0, 0, 5, 10)}]), seas
    )

    assert result["area"].iloc[0] == pytest.approx(only_polygon["area"].iloc[0])


def test_protection_level_counts_overlapping_zones_in_a_sea_once(monkeypatch):
    """Zones in the same sea are unioned, so overlap is not double counted."""
    seas = _sea_gdf([{"location": "1", "geometry": box(0, 0, 10, 10)}])
    overlapping = _pairs_gdf(
        [
            {"location": "1", "geometry": box(0, 0, 6, 10)},
            {"location": "1", "geometry": box(4, 0, 10, 10)},
        ]
    )
    whole = _pairs_gdf([{"location": "1", "geometry": box(0, 0, 10, 10)}])

    overlapped = _run_protection_level(monkeypatch, overlapping, seas)["area"].iloc[0]
    unioned = _run_protection_level(monkeypatch, whole, seas)["area"].iloc[0]

    assert overlapped == pytest.approx(unioned)


def test_protection_level_percentage_is_the_protected_share_of_the_sea(monkeypatch):
    seas = _sea_gdf([{"location": "1", "geometry": box(0, 0, 10, 10)}])
    pairs = _pairs_gdf([{"location": "1", "geometry": box(0, 0, 5, 10)}])

    result = _run_protection_level(monkeypatch, pairs, seas).iloc[0]

    assert result["percentage"] == pytest.approx(50.0)
    assert result["percentage"] == pytest.approx(100 * result["area"] / result["total_area"])


def test_protection_level_total_area_is_the_whole_sea_not_the_protected_part(monkeypatch):
    """total_area measures the sea itself, so coverage has a stable denominator."""
    seas = _sea_gdf([{"location": "1", "geometry": box(0, 0, 10, 10)}])
    sliver = _pairs_gdf([{"location": "1", "geometry": box(0, 0, 1, 10)}])
    most = _pairs_gdf([{"location": "1", "geometry": box(0, 0, 9, 10)}])

    assert _run_protection_level(monkeypatch, sliver, seas)["total_area"].iloc[0] == pytest.approx(
        _run_protection_level(monkeypatch, most, seas)["total_area"].iloc[0]
    )


def test_protection_level_matches_the_overlay_of_zones_against_seas(monkeypatch):
    """Reading saved pairs gives the areas a direct MPAtlas/IHO overlay gives.

    The pairs are built by the real ``intersect_with_iho`` and then measured,
    while the reference overlays the same zones against the same seas in the
    equal-area projection and unions per sea. Both must agree, including for a
    zone straddling two seas and for one excluded by protection level.
    """
    seas = _sea_gdf(
        [
            {"location": "1", "geometry": box(0, 0, 10, 10)},
            {"location": "2", "geometry": box(10, 0, 20, 10)},
        ]
    )
    zones = gpd.GeoDataFrame(
        {
            "zone_id": [10, 20, 30],
            "protection_mpaguide_level": ["full", "high", "less"],
            "geometry": [box(5, 1, 15, 3), box(1, 5, 3, 7), box(6, 6, 8, 8)],
        },
        geometry="geometry",
        crs="EPSG:4326",
    )

    qualifying = zones[zones["protection_mpaguide_level"].isin(("full", "high"))]
    seas_proj = seas.to_crs(epsg=6933)
    joined = gpd.overlay(qualifying.to_crs(epsg=6933), seas_proj, how="intersection")
    expected = {
        location: group.geometry.union_all().area / 1e6
        for location, group in joined.groupby("location")
    }

    monkeypatch.setattr(iho_pa_intersections, "load_iho_regions", lambda buffer=False: seas.copy())
    pairs = iho_pa_intersections.intersect_with_iho(
        zones, ["zone_id", "protection_mpaguide_level"], with_geometry=True
    )

    result = _run_protection_level(monkeypatch, pairs, seas)
    actual = dict(zip(result["location"], result["area"], strict=True))

    assert actual.keys() == expected.keys()
    for location, area in expected.items():
        assert actual[location] == pytest.approx(area, rel=1e-9)
