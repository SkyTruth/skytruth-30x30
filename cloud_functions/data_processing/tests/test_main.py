import pytest


import main
from tests.fixtures.utils.util_mocks import MockRequest

@pytest.fixture
def call_log():
    """Shared accumulator of (name, args, kwargs) across patched functions."""
    return []

def make_recorder(call_log, name, return_value=None, side_effect=None):
    """
    Create a stub that records all calls.
    - If side_effect is provided, it will be raised when called.
    - Otherwise returns return_value.
    """
    def _recorder(*args, **kwargs):
        call_log.append((name, args, kwargs))
        if side_effect:
            raise side_effect
        return return_value
    return _recorder


@pytest.fixture
def patched_all(monkeypatch, call_log):
    """
    Patch all functions that might get called from main
    """
    simple_targets = [
        "process_gadm_geoms",
        "process_eez_geoms",
        "process_eez_gadm_unions",
        "download_marine_habitats",
        "process_terrestrial_biome_raster",
        "process_mangroves",
        "generate_terrestrial_biome_stats_country",
        "download_mpatlas",
        "download_protected_seas",
        "download_protected_planet",
        "process_protected_area_geoms",
        "generate_protected_areas_table",
        "generate_terrestrial_biome_stats_pa",
        "generate_habitat_protection_table",
        "generate_protection_coverage_stats_table",
        "generate_marine_protection_level_stats_table",
        "generate_fishing_protection_table",
    ]
    for name in simple_targets:
        monkeypatch.setattr(
            main,
            name,
            make_recorder(call_log, name, return_value={"ok": True}),
            raising=True,
        )

    # The downloader with positional args + kwargs
    monkeypatch.setattr(
        main,
        "download_zip_to_gcs",
        make_recorder(call_log, "download_zip_to_gcs", return_value={"ok": True}),
        raising=True,
    )

    return call_log


# Single function call methods
@pytest.mark.parametrize(
    "method, expected_call",
    [
        ("process_gadm", "process_gadm_geoms"),
        ("process_eezs", "process_eez_geoms"),
        ("process_eez_gadm_unions", "process_eez_gadm_unions"),
        ("download_marine_habitats", "download_marine_habitats"),
        ("process_terrestrial_biomes", "process_terrestrial_biome_raster"),
        ("process_mangroves", "process_mangroves"),
        ("generate_terrestrial_biome_stats_country", "generate_terrestrial_biome_stats_country"),
        ("download_mpatlas", "download_mpatlas"),
        ("download_protected_seas", "download_protected_seas"),
        ("generate_protected_areas_table", "generate_protected_areas_table"),
        ("generate_protection_coverage_stats_table", "generate_protection_coverage_stats_table"),
        ("generate_marine_protection_level_stats_table", "generate_marine_protection_level_stats_table"),
        ("generate_fishing_protection_table", "generate_fishing_protection_table"),
    ],
)
def test_single_call_methods_route_and_pass_verbose(patched_all, method, expected_call):
    """Each simple METHOD should call exactly one target with only verbose kwarg."""
    resp = main.main(MockRequest({"METHOD": method}))
    assert resp == ("OK", 200)

    # Exactly one call recorded
    assert len(patched_all) == 1
    name, args, kwargs = patched_all[0]
    assert name == expected_call
    assert args == ()
    assert "verbose" in kwargs 


# Multi-function call methods
def test_download_protected_planet_wdpa_calls_two(patched_all):
    """download_protected_planet_wdpa should call download_protected_planet then process_protected_area_geoms."""
    resp = main.main(MockRequest({"METHOD": "download_protected_planet_wdpa"}))
    assert resp == ("OK", 200)

    # Two calls in order
    assert [c[0] for c in patched_all] == [
        "download_protected_planet",
        "process_protected_area_geoms",
    ]
    # Both called with verbose kwarg
    for _, args, kwargs in patched_all:
        assert args == ()
        assert "verbose" in kwargs


def test_generate_habitat_protection_table_calls_both(patched_all):
    """generate_habitat_protection_table should call stats_pa then the final table generator."""
    resp = main.main(MockRequest({"METHOD": "generate_habitat_protection_table"}))
    assert resp == ("OK", 200)

    assert [c[0] for c in patched_all] == [
        "generate_terrestrial_biome_stats_pa",
        "generate_habitat_protection_table",
    ]
    for _, args, kwargs in patched_all:
        assert args == ()
        assert "verbose" in kwargs

# Tests for functions that directly call download_zip_to_gcs
def _assert_download_zip_call_kwargs(call, *, url, bucket_name, blob_name, chunk_size, extra_kwargs=None):
    """Validate that download_zip_to_gcs was called with ONLY kwargs and expected values."""
    name, args, kwargs = call
    assert name == "download_zip_to_gcs"
    assert args == ()
    assert kwargs.get("url") == url
    assert kwargs.get("bucket_name") == bucket_name
    assert kwargs.get("blob_name") == blob_name  # matches handler param spelling
    assert kwargs.get("chunk_size") == chunk_size
    assert "verbose" in kwargs
    if extra_kwargs:
        for k, v in extra_kwargs.items():
            assert kwargs.get(k) == v


@pytest.mark.parametrize(
    "method, expected, extra",
    [
        pytest.param(
            "download_gadm",
            dict(
                url=lambda m: m.GADM_URL,
                bucket_name=lambda m: m.BUCKET,
                blob_name=lambda m: m.GADM_ZIPFILE_NAME,
                chunk_size=lambda m: m.CHUNK_SIZE,
            ),
            {},  # no extra kwargs for this route
            id="gadm",
        ),
        pytest.param(
            "download_eezs",
            dict(
                url=lambda m: m.MARINE_REGIONS_URL,
                bucket_name=lambda m: m.BUCKET,
                blob_name=lambda m: m.EEZ_PARAMS["zipfile_name"],
                chunk_size=lambda m: m.CHUNK_SIZE,
            ),
            {
                "data":    lambda m: m.MARINE_REGIONS_BODY,
                "params":  lambda m: m.EEZ_PARAMS,
                "headers": lambda m: m.MARINE_REGIONS_HEADERS,
            },
            id="eezs",
        ),
        pytest.param(
            "download_high_seas",
            dict(
                url=lambda m: m.MARINE_REGIONS_URL,
                bucket_name=lambda m: m.BUCKET,
                blob_name=lambda m: m.HIGH_SEAS_PARAMS["zipfile_name"],
                chunk_size=lambda m: m.CHUNK_SIZE,
            ),
            {
                "data":    lambda m: m.MARINE_REGIONS_BODY,
                "params":  lambda m: m.HIGH_SEAS_PARAMS,
                "headers": lambda m: m.MARINE_REGIONS_HEADERS,
            },
            id="high_seas",
        ),
    ],
)
def test_downloader_zip_routes(patched_all, method, expected, extra):
    """
    Each downloader METHOD must call download_zip_to_gcs keyword-only with the right values.
    Using lambdas defers constant lookup to runtime so imports/fixtures don't break collection.
    """
    resp = main.main(MockRequest({"METHOD": method}))
    assert resp == ("OK", 200)
    assert len(patched_all) == 1

    call = patched_all[0]
    _assert_download_zip_call_kwargs(
        call,
        url=expected["url"](main),
        bucket_name=expected["bucket_name"](main),
        blob_name=expected["blob_name"](main),
        chunk_size=expected["chunk_size"](main),
        extra_kwargs={k: v(main) for k, v in extra.items()} if extra else None,
    )


# Non-invoking / generic flows
def test_dry_run_calls_nothing_and_returns_ok(patched_all, monkeypatch):
    """dry_run should print and return OK without calling any target."""
    resp = main.main(MockRequest({"METHOD": "dry_run"}))
    assert resp == ("OK", 200)
    assert patched_all == []  # no calls made


def test_unknown_method_returns_ok_and_calls_nothing(patched_all):
    """Unknown methods should not call anything; handler still returns OK, 200."""
    resp = main.main(MockRequest({"METHOD": "totally_unknown"}))
    assert resp == ("OK", 200)
    assert patched_all == []


# Error path
def test_error_bubbles_to_500(monkeypatch, call_log):
    """If any called function raises, handler should catch and return 500."""
    monkeypatch.setattr(
        main, "process_gadm_geoms",
        make_recorder(call_log, "process_gadm_geoms", side_effect=RuntimeError("boom")),
        raising=True,
    )
    resp = main.main(MockRequest({"METHOD": "process_gadm"}))
    assert isinstance(resp, tuple)
    body, status = resp
    assert status == 500
    assert "Internal Server Error" in body