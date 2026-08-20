import copy

from src.methods.download_and_process import normalize_mpatlas_geojson


def properties_by_zone(data):
    return {feat["id"]: feat["properties"] for feat in data["features"]}


def test_normalize_renames_v4_fields(mock_mpatlas_v4_geojson):
    result = normalize_mpatlas_geojson(mock_mpatlas_v4_geojson)

    props = properties_by_zone(result)[4821]
    assert props["name"] == "Cairns Section"
    assert props["designation"] == "Marine Park"
    assert props["protection_mpaguide_level"] == "high"
    for v4_name in [
        "zone_name",
        "site_designation",
        "mpaguide_protection_level",
        "assessment_establishment_stage",
    ]:
        assert v4_name not in props


def test_normalize_uses_zone_effective_establishment_stage(mock_mpatlas_v4_geojson):
    """The site-level establishment_stage must be replaced by the assessment value."""
    result = normalize_mpatlas_geojson(mock_mpatlas_v4_geojson)

    props = properties_by_zone(result)
    assert props[4821]["establishment_stage"] == "implemented"
    assert props[4822]["establishment_stage"] == "actively managed"
    assert props[4823]["establishment_stage"] == "designated"


def test_normalize_leaves_unmapped_fields_untouched(mock_mpatlas_v4_geojson):
    original = copy.deepcopy(mock_mpatlas_v4_geojson)
    result = normalize_mpatlas_geojson(mock_mpatlas_v4_geojson)

    original_props = properties_by_zone(original)
    for feature in result["features"]:
        props = feature["properties"]
        expected = original_props[feature["id"]]
        for field in ["zone_id", "site_id", "country", "sovereign", "wdpa_id", "wdpa_pid"]:
            assert props[field] == expected[field]

    # geometry and top-level id pass through as-is, nulls included
    assert [f["id"] for f in result["features"]] == [f["id"] for f in original["features"]]
    assert [f["geometry"] for f in result["features"]] == [
        f["geometry"] for f in original["features"]
    ]


def test_normalize_is_idempotent(mock_mpatlas_v4_geojson):
    once = normalize_mpatlas_geojson(copy.deepcopy(mock_mpatlas_v4_geojson))
    twice = normalize_mpatlas_geojson(copy.deepcopy(once))
    assert twice == once
