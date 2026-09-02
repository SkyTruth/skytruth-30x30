import json
from unittest.mock import MagicMock

import pytest

import src.methods.publisher as main
from src.core.retry_params import ScheduleRetry


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
        "process_eez_land_union",
        "download_marine_habitats",
        "process_terrestrial_biome_raster",
        "process_mangroves",
        "generate_terrestrial_biome_stats_country",
        "download_mpatlas",
        "download_protected_seas",
        "download_protected_planet",
        "download_and_process_protected_planet_pas",
        "generate_protected_areas_diff_table",
        "generate_terrestrial_biome_stats_pa",
        "generate_habitat_protection_table",
        "generate_protection_coverage_stats_table",
        "generate_marine_protection_level_stats_table",
        "generate_fishing_protection_table",
        "upload_locations",
        "generate_total_area_minus_pa",
        "generate_location_minus_fhp_mpa",
    ]
    for name in simple_targets:
        return_value = {"ok": True}
        monkeypatch.setattr(
            main,
            name,
            make_recorder(call_log, name, return_value=return_value),
            raising=True,
        )

    # The downloader with positional args + kwargs
    monkeypatch.setattr(
        main,
        "download_zip_to_gcs",
        make_recorder(call_log, "download_zip_to_gcs", return_value={"ok": True}),
        raising=True,
    )

    monkeypatch.setattr(
        main,
        "create_task",
        make_recorder(call_log, "create_task", return_value=MagicMock(name="tasks/fake123")),
        raising=True,
    )
    monkeypatch.setattr(
        main,
        "long_running_tasks",
        make_recorder(call_log, "long_running_tasks", return_value=("OK", 200)),
        raising=True,
    )

    monkeypatch.setattr(main, "LONG_RUNNING_TASKS", [], raising=False)

    return call_log


# Single function call methods
@pytest.mark.parametrize(
    "method, expected_call",
    [
        ("process_gadm", "process_gadm_geoms"),
        ("process_eezs", "process_eez_geoms"),
        ("process_eez_land_union", "process_eez_land_union"),
        ("download_marine_habitats", "download_marine_habitats"),
        ("process_terrestrial_biomes", "process_terrestrial_biome_raster"),
        ("process_mangroves", "process_mangroves"),
        ("generate_terrestrial_biome_stats_country", "generate_terrestrial_biome_stats_country"),
        ("download_mpatlas", "download_mpatlas"),
        ("download_protected_seas", "download_protected_seas"),
        (
            "download_protected_planet_pas",
            "download_and_process_protected_planet_pas",
        ),
        ("generate_protected_areas_table", "generate_protected_areas_diff_table"),
        ("generate_protection_coverage_stats_table", "generate_protection_coverage_stats_table"),
        (
            "generate_marine_protection_level_stats_table",
            "generate_marine_protection_level_stats_table",
        ),
        ("generate_fishing_protection_table", "generate_fishing_protection_table"),
        ("update_locations", "upload_locations"),
    ],
)
def test_single_call_methods_route_and_pass_verbose(patched_all, method, expected_call):
    """Each simple METHOD should call exactly one target with only verbose kwarg."""
    resp = main.run_from_payload({"METHOD": method})

    if method == "update_locations":
        # Split this out because update_locations passes on its return value
        assert resp == ('{"ok": true}', 200)
    else:
        assert resp == ("OK", 200)

    # Exactly one call recorded
    assert len(patched_all) == 1
    name, args, kwargs = patched_all[0]

    assert name == expected_call
    assert args == ()
    assert "verbose" in kwargs
    if method == "update_locations":
        assert kwargs["request"] == {"METHOD": "update_locations"}


def test_protected_planet_pas_receives_every_tolerance(patched_all):
    """The PA job simplifies at every tolerance in one invocation.

    It used to be dispatched once per tolerance, which meant two full WDPA
    downloads and two downstream chains that could interleave.
    """
    resp = main.run_from_payload({"METHOD": "download_protected_planet_pas"})

    assert resp == ("OK", 200)
    _, _, kwargs = patched_all[0]
    assert tuple(kwargs["tolerances"]) == tuple(main.TOLERANCES)
    assert "tolerance" not in kwargs


@pytest.mark.parametrize(
    "method, expected_tolerance",
    [
        ("generate_gadm_minus_pa", "TERRESTRIAL_TOLERANCE"),
        ("generate_eez_minus_mpa", "MARINE_TOLERANCE"),
        ("generate_location_minus_fhp_mpa", "MARINE_TOLERANCE"),
    ],
)
def test_conservation_builder_methods_use_their_domain_tolerance(
    patched_all, method, expected_tolerance
):
    """Each subtraction job builds at the tolerance for its own environment.

    All three used to read it from the payload, which meant the value was
    whatever TOLERANCES[0] happened to be - so both marine layers silently ran
    at the terrestrial tolerance.
    """
    resp = main.run_from_payload({"METHOD": method})

    assert resp == ("OK", 200)
    _, _, kwargs = patched_all[0]
    assert kwargs["tolerance"] == getattr(main, expected_tolerance)


@pytest.mark.parametrize(
    "method",
    [
        "download_protected_planet_pas",
        "generate_gadm_minus_pa",
        "generate_eez_minus_mpa",
        "generate_location_minus_fhp_mpa",
    ],
)
def test_payload_tolerance_is_never_honoured(patched_all, method):
    """Tolerance is resolved from constants at the read site, never from a task.

    A queued task must not be able to vary it: a partial or wrongly-simplified
    dataset would still let the shared step_list fire on it.
    """
    resp = main.run_from_payload({"METHOD": method, "TOLERANCE": 0.5})

    assert resp == ("OK", 200)
    _, _, kwargs = patched_all[0]
    assert 0.5 not in tuple(kwargs.get("tolerances", ())) and kwargs.get("tolerance") != 0.5


@pytest.mark.parametrize(
    "habitat",
    ["coldwatercorals", ["coldwatercorals", "saltmarshes", "seagrasses"]],
    ids=["single", "list"],
)
def test_download_marine_habitats_forwards_habitat_selection(patched_all, habitat):
    """HABITAT selects which source zips to fetch, one name or a list of them."""
    resp = main.run_from_payload({"METHOD": "download_marine_habitats", "HABITAT": habitat})

    assert resp == ("OK", 200)
    _, _, kwargs = patched_all[0]
    assert kwargs["habitats"] == habitat


def test_download_marine_habitats_without_habitat_downloads_everything(patched_all):
    """Omitting HABITAT means all of them, so the monthly job needs no extra config."""
    resp = main.run_from_payload({"METHOD": "download_marine_habitats"})

    assert resp == ("OK", 200)
    _, _, kwargs = patched_all[0]
    assert kwargs["habitats"] is None


# Tests for functions that directly call download_zip_to_gcs
def _assert_download_zip_call_kwargs(
    call, *, url, bucket_name, blob_name, chunk_size, extra_kwargs=None
):
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
                "data": lambda m: m.MARINE_REGIONS_BODY,
                "params": lambda m: m.EEZ_PARAMS,
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
                "data": lambda m: m.MARINE_REGIONS_BODY,
                "params": lambda m: m.HIGH_SEAS_PARAMS,
                "headers": lambda m: m.MARINE_REGIONS_HEADERS,
            },
            id="high_seas",
        ),
        pytest.param(
            "download_eez_land_union",
            dict(
                url=lambda m: m.MARINE_REGIONS_URL,
                bucket_name=lambda m: m.BUCKET,
                blob_name=lambda m: m.EEZ_LAND_UNION_PARAMS["zipfile_name"],
                chunk_size=lambda m: m.CHUNK_SIZE,
            ),
            {
                "data": lambda m: m.MARINE_REGIONS_BODY,
                "params": lambda m: m.EEZ_LAND_UNION_PARAMS,
                "headers": lambda m: m.MARINE_REGIONS_HEADERS,
            },
            id="eez_land_union",
        ),
    ],
)
def test_downloader_zip_routes(patched_all, method, expected, extra):
    """
    Each downloader METHOD must call download_zip_to_gcs keyword-only with the right values.
    Using lambdas defers constant lookup to runtime so imports/fixtures don't break collection.
    """
    resp = main.run_from_payload({"METHOD": method})
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


def _make_mock_strapi(recorder):
    """
    Build a fake Strapi class that records instantiation and exposes the upsert methods.
    """

    class MockClient:
        def __init__(self):
            recorder["instantiated"] = recorder.get("instantiated", 0) + 1

        # These methods won't be invoked by main; only passed as upload_function.
        # We still provide them to allow isinstance/identity checks.
        def upsert_protection_coverage_stats(self, *a, **k):
            pass

        def upsert_mpaa_protection_level_stats(self, *a, **k):
            pass

        def upsert_fishing_protection_level_stats(self, *a, **k):
            pass

        def upsert_habitat_stats(self, *a, **k):
            pass

    return MockClient


def _patch_upload_stats_to_recorder(monkeypatch, recorder):
    def mock_upload_stats(*, filename, upload_function, verbose=True, **_):
        recorder["filename"] = filename
        recorder["upload_function"] = upload_function
        recorder["verbose"] = verbose
        return ("STATS_OK", 201)

    monkeypatch.setattr(main, "upload_stats", mock_upload_stats, raising=True)


@pytest.mark.parametrize(
    "method, expected_filename_attr, client_method_name",
    [
        (
            "update_protection_coverage_stats",
            "PROTECTION_COVERAGE_FILE_NAME",
            "upsert_protection_coverage_stats",
        ),
        (
            "update_mpaa_protection_level_stats",
            "PROTECTION_LEVEL_FILE_NAME",
            "upsert_mpaa_protection_level_stats",
        ),
        (
            "update_fishing_protection_stats",
            "FISHING_PROTECTION_FILE_NAME",
            "upsert_fishing_protection_level_stats",
        ),
        (
            "update_habitat_protection_stats",
            "HABITAT_PROTECTION_FILE_NAME",
            "upsert_habitat_stats",
        ),
    ],
)
def test_update_stats_routes_instantiate_strapi_and_pass_bound_method(
    monkeypatch, method, expected_filename_attr, client_method_name
):
    """
    Each update_*_stats route should:
      - instantiate Strapi()
      - call upload_stats(filename=<CONST>, upload_function=<client.bound_method>,
        verbose=module.verbose)
      - return whatever upload_stats returns
    """
    recorder = {}

    # Patch Strapi to our fake class
    MockStrapi = _make_mock_strapi(recorder)
    monkeypatch.setattr(main, "Strapi", MockStrapi, raising=True)

    # Patch upload_stats to a recorder
    _patch_upload_stats_to_recorder(monkeypatch, recorder)

    resp = main.run_from_payload({"METHOD": method})
    assert resp == ("STATS_OK", 201)

    # Strapi was instantiated exactly once
    assert recorder.get("instantiated", 0) == 1

    expected_filename = getattr(main, expected_filename_attr)
    assert recorder["filename"] == expected_filename

    upload_fn = recorder["upload_function"]
    assert callable(upload_fn)
    # Method name matches expected
    assert getattr(upload_fn, "__name__", "") == client_method_name
    # Ensure the function is bound (has __self__ set to the MockStrapi instance)
    # this makes sure the API call will be authenticated, since the auth is tied to
    # the class instance
    assert getattr(upload_fn, "__self__", None).__class__ is MockStrapi

    # Verbose propagated from module
    assert recorder["verbose"] is True


# Monthly fan-out
@pytest.fixture
def enqueued_jobs(monkeypatch, call_log):
    """Patch only the two enqueue routes, leaving LONG_RUNNING_TASKS real.

    `patched_all` blanks LONG_RUNNING_TASKS, which is exactly what these tests
    need to exercise, so they patch narrowly instead.
    """
    monkeypatch.setattr(main, "create_task", make_recorder(call_log, "create_task"), raising=True)
    monkeypatch.setattr(
        main, "long_running_tasks", make_recorder(call_log, "long_running_tasks"), raising=True
    )

    def _run():
        main.run_from_payload({"METHOD": "publisher"}, verbose=False)
        return {
            route: [args[0] for name, args, _ in call_log if name == route]
            for route in ("create_task", "long_running_tasks")
        }

    return _run


def test_monthly_publisher_enqueues_one_pa_job(enqueued_jobs):
    """The PA job is enqueued once, not once per tolerance."""
    jobs = enqueued_jobs()

    all_jobs = jobs["create_task"] + jobs["long_running_tasks"]
    pa_jobs = [job for job in all_jobs if job["METHOD"] == "download_protected_planet_pas"]

    assert len(pa_jobs) == 1
    assert len(all_jobs) == 3
    # Tolerance is resolved from constants at each read site, so no task payload
    # carries one - neither a single value nor a fan-out list.
    assert not {"TOLERANCE", "TOLERANCES"} & set(pa_jobs[0])


def test_monthly_publisher_routes_long_running_jobs_to_the_job_runner(enqueued_jobs):
    """Long-running methods must go to a Cloud Run Job, not the task queue."""
    jobs = enqueued_jobs()

    assert "download_protected_planet_pas" in {job["METHOD"] for job in jobs["long_running_tasks"]}
    assert {job["METHOD"] for job in jobs["create_task"]} == {"download_mpatlas"}


def test_monthly_publisher_payloads_survive_the_json_boundary(enqueued_jobs):
    """Payloads reach Cloud Tasks as JSON, so they must round-trip unchanged.

    A tuple in the payload (as the old TOLERANCES key was) comes back a list,
    so the task a worker receives is not the one that was enqueued.
    """
    jobs = enqueued_jobs()

    for job in jobs["create_task"] + jobs["long_running_tasks"]:
        assert json.loads(json.dumps(job)) == job


# Non-invoking / generic flows
def test_dry_run_calls_nothing_and_returns_ok(patched_all, monkeypatch):
    """dry_run should print and return OK without calling any target."""
    resp = main.run_from_payload({"METHOD": "dry_run"})
    assert resp == ("OK", 200)
    assert patched_all == []  # no calls made


def test_unknown_method_returns_ok_and_calls_nothing(patched_all):
    """Unknown methods should not call anything; handler still returns OK, 200."""
    resp = main.run_from_payload({"METHOD": "totally_unknown"})
    assert resp == ("OK", 200)
    assert patched_all == []


# Error path
def test_error_bubbles_to_500(monkeypatch, call_log):
    """If any called function raises, handler should catch and return 500."""

    monkeypatch.setattr(
        main,
        "send_slack_alert",
        make_recorder(call_log, "send_slack_alert", return_value={"ok": True}),
        raising=True,
    )

    monkeypatch.setattr(
        main,
        "process_gadm_geoms",
        make_recorder(call_log, "process_gadm_geoms", side_effect=RuntimeError("boom")),
        raising=True,
    )

    resp = main.run_from_payload({"METHOD": "process_gadm", "MAX_RETRIES": 0})
    assert isinstance(resp, tuple)
    body, status = resp
    assert status == 500
    assert "failed after 1 attempts" in body


# ScheduleRetry path
def test_schedule_retry_schedules_task_on_first_attempt(monkeypatch, call_log):
    """ScheduleRetry on attempt 1 should create a delayed Cloud Task."""
    delay_seconds = 86400
    monkeypatch.setattr(
        main,
        "download_mpatlas",
        make_recorder(
            call_log,
            "download_mpatlas",
            side_effect=ScheduleRetry(
                delay_seconds=delay_seconds, max_retries=3, message="not found"
            ),
        ),
        raising=True,
    )
    monkeypatch.setattr(
        main,
        "create_task",
        make_recorder(
            call_log,
            "create_task",
            return_value=MagicMock(name="tasks/retry1"),
        ),
        raising=True,
    )

    resp = main.run_from_payload({"METHOD": "download_mpatlas"})
    assert resp == (f"Retrying in {delay_seconds} seconds", 202)

    # create_task was called with the right delay and incremented attempt
    task_calls = [call for call in call_log if call[0] == "create_task"]
    assert len(task_calls) == 1
    _name, _args, task_kwargs = task_calls[0]
    assert task_kwargs["delay_seconds"] == 86400
    payload = task_kwargs["payload"]
    assert payload["attempt"] == 2
    assert payload["MAX_RETRIES"] == 3


def test_schedule_retry_exhausted_returns_500_and_alerts(monkeypatch, call_log):
    """ScheduleRetry on final attempt should return 500 and send Slack alert."""
    monkeypatch.setattr(
        main,
        "download_mpatlas",
        make_recorder(
            call_log,
            "download_mpatlas",
            side_effect=ScheduleRetry(delay_seconds=86400, max_retries=3, message="not found"),
        ),
        raising=True,
    )
    monkeypatch.setattr(
        main,
        "send_slack_alert",
        make_recorder(call_log, "send_slack_alert", return_value={"ok": True}),
        raising=True,
    )

    # attempt=4 with max_retries=3 means all retries are exhausted
    resp = main.run_from_payload({"METHOD": "download_mpatlas", "attempt": 4})
    body, status = resp
    assert status == 500
    assert "failed after 4 attempts" in body

    # Slack alert was sent
    alert_calls = [call for call in call_log if call[0] == "send_slack_alert"]
    assert len(alert_calls) == 1

    # No retry task was created
    task_calls = [call for call in call_log if call[0] == "create_task"]
    assert len(task_calls) == 0


def test_schedule_retry_does_not_fire_on_success(patched_all):
    """Successful download_mpatlas should return OK, not retry."""
    resp = main.run_from_payload({"METHOD": "download_mpatlas"})
    assert resp == ("OK", 200)

    # No create_task calls (only the download_mpatlas recorder)
    task_calls = [call for call in patched_all if call[0] == "create_task"]
    assert len(task_calls) == 0


def test_schedule_retry_prevents_next_steps(monkeypatch, call_log):
    """When a download raises ScheduleRetry, downstream steps should not run."""
    monkeypatch.setattr(
        main,
        "download_mpatlas",
        make_recorder(
            call_log,
            "download_mpatlas",
            side_effect=ScheduleRetry(delay_seconds=86400, max_retries=3, message="not found"),
        ),
        raising=True,
    )
    monkeypatch.setattr(
        main,
        "create_task",
        make_recorder(
            call_log,
            "create_task",
            return_value=MagicMock(name="tasks/retry1"),
        ),
        raising=True,
    )
    monkeypatch.setattr(
        main,
        "pipe_next_steps",
        make_recorder(call_log, "pipe_next_steps", return_value=None),
        raising=True,
    )

    resp = main.run_from_payload({"METHOD": "download_mpatlas", "TRIGGER_NEXT": True})
    assert resp == (f"Retrying in {86400} seconds", 202)

    # pipe_next_steps was never called
    next_step_calls = [call for call in call_log if call[0] == "pipe_next_steps"]
    assert len(next_step_calls) == 0
