import pickle

import pandas as pd
import pytest

import src.methods.generate_tables as gen_tables
from tests.fixtures.utils.util_mocks import MockBlob, MockBucket, MockClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def updated_pas_df():
    """Minimal 'updated' PA dataframe returned by generate_protected_areas_table."""
    return pd.DataFrame(
        [
            {
                "wdpaid": "1",
                "wdpa_p_id": "1",
                "zone_id": None,
                "name": "Alpha",
                "area": 100.0,
                "coverage": 50.0,
                "location": "USA",
                "environment": "marine",
            },
            {
                "wdpaid": "2",
                "wdpa_p_id": "2",
                "zone_id": None,
                "name": "Beta",
                "area": 200.0,
                "coverage": 75.0,
                "location": "USA",
                "environment": "marine",
            },
        ]
    )


@pytest.fixture
def current_db_rows():
    """Minimal 'current DB' rows as returned by get_pas()."""
    return [
        {
            "documentId": "doc-10",
            "wdpaid": "1",
            "wdpa_p_id": "1",
            "zone_id": None,
            "name": "Alpha",
            "area": "100.0",  # strings on purpose — the function coerces to float
            "coverage": "50.0",
            "location": "USA",
            "environment": "marine",
        },
    ]


@pytest.fixture
def gcs_mock(monkeypatch):
    """
    Patch gen_tables.storage.Client so no real GCS call is ever made.
    Returns the MockBlob / MockBucket / MockClient instances for assertions.
    """
    mock_blob = MockBlob()
    mock_bucket = MockBucket(name=None, blob=mock_blob)
    mock_client_holder = {}

    def _client_factory(project=None):
        client = MockClient(mock_bucket, project)
        mock_client_holder["client"] = client
        return client

    # storage is `from google.cloud import storage` inside gen_tables; patch the
    # attribute rather than the name so `storage.Client(project=...)` resolves here.
    class _MockStorage:
        Client = staticmethod(_client_factory)

    monkeypatch.setattr(gen_tables, "storage", _MockStorage)

    return {
        "blob": mock_blob,
        "bucket": mock_bucket,
        "client_holder": mock_client_holder,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_deps(
    monkeypatch,
    tmp_path,
    *,
    updated_pas,
    current_db,
    db_changes,
    change_cols=None,
    generate_recorder=None,
):
    """Patch every external dependency so the function runs offline."""
    if change_cols is None:
        change_cols = pd.DataFrame({"name": [False], "area": [False]})

    def _mock_generate_protected_areas_table(**kwargs):
        if generate_recorder is not None:
            generate_recorder.update(kwargs)
        return updated_pas

    def _mock_get_pas():
        return current_db

    def _mock_make_pa_updates(current_db_df, updated, verbose=True):
        return db_changes, change_cols

    monkeypatch.setattr(
        gen_tables, "generate_protected_areas_table", _mock_generate_protected_areas_table
    )
    monkeypatch.setattr(gen_tables, "get_pas", _mock_get_pas)
    monkeypatch.setattr(gen_tables, "make_pa_updates", _mock_make_pa_updates)

    # db_changes.pkl gets written to CWD — keep it out of the repo
    monkeypatch.chdir(tmp_path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_returns_true_when_new_or_changed_present(
    monkeypatch, tmp_path, updated_pas_df, current_db_rows, gcs_mock
):
    _patch_deps(
        monkeypatch,
        tmp_path,
        updated_pas=updated_pas_df,
        current_db=current_db_rows,
        db_changes={
            "new": [{"wdpaid": "2", "name": "Beta"}],
            "changed": [],
            "deleted": [],
        },
    )

    result = gen_tables.generate_protected_areas_diff_table(verbose=False)

    assert result is True


def test_returns_false_when_no_new_or_changed(
    monkeypatch, tmp_path, updated_pas_df, current_db_rows, gcs_mock
):
    _patch_deps(
        monkeypatch,
        tmp_path,
        updated_pas=updated_pas_df,
        current_db=current_db_rows,
        db_changes={"new": [], "changed": [], "deleted": ["doc-1", "doc-2"]},
    )

    result = gen_tables.generate_protected_areas_diff_table(verbose=False)

    assert result is False


def test_uploads_pickle_to_correct_bucket_and_blob(
    monkeypatch, tmp_path, updated_pas_df, current_db_rows, gcs_mock
):
    _patch_deps(
        monkeypatch,
        tmp_path,
        updated_pas=updated_pas_df,
        current_db=current_db_rows,
        db_changes={"new": [], "changed": [], "deleted": []},
    )

    gen_tables.generate_protected_areas_diff_table(
        pa_file_name="path/to/pa_changes.pkl",
        bucket="my-bucket",
        project="my-project",
        verbose=False,
    )

    client = gcs_mock["client_holder"]["client"]
    assert client.project == "my-project"
    assert client.bucket_name == "my-bucket"
    assert gcs_mock["bucket"].blob_name == "path/to/pa_changes.pkl"
    assert gcs_mock["blob"].uploaded_filename == "db_changes.pkl"


def test_uploaded_pickle_bytes_match_db_changes(
    monkeypatch, tmp_path, updated_pas_df, current_db_rows, gcs_mock
):
    """The bytes handed to GCS round-trip back to the cleaned db_changes dict."""
    db_changes = {
        "new": [{"name": "Alpha", "area": 1.0}],
        "changed": [{"name": "Beta", "area": 2.0}],
        "deleted": ["doc-7"],
    }
    _patch_deps(
        monkeypatch,
        tmp_path,
        updated_pas=updated_pas_df,
        current_db=current_db_rows,
        db_changes=db_changes,
    )

    gen_tables.generate_protected_areas_diff_table(verbose=False)

    saved = pickle.loads(gcs_mock["blob"].uploaded_data)
    assert saved["new"] == [{"name": "Alpha", "area": 1.0}]
    assert saved["changed"] == [{"name": "Beta", "area": 2.0}]
    assert saved["deleted"] == ["doc-7"]


def test_nan_and_inf_floats_are_replaced_with_none(
    monkeypatch, tmp_path, updated_pas_df, current_db_rows, gcs_mock
):
    """clean_for_json replaces NaN/Inf floats with None before the pickle is saved."""
    db_changes = {
        "new": [
            {
                "name": "Alpha",
                "area": float("nan"),
                "coverage": float("inf"),
                "year": 2024,
            }
        ],
        "changed": [{"name": "Beta", "area": float("-inf")}],
        "deleted": [],
    }
    _patch_deps(
        monkeypatch,
        tmp_path,
        updated_pas=updated_pas_df,
        current_db=current_db_rows,
        db_changes=db_changes,
    )

    gen_tables.generate_protected_areas_diff_table(verbose=False)

    saved = pickle.loads(gcs_mock["blob"].uploaded_data)
    assert saved["new"][0]["area"] is None
    assert saved["new"][0]["coverage"] is None
    assert saved["new"][0]["year"] == 2024
    assert saved["changed"][0]["area"] is None


def test_empty_strings_are_replaced_with_none(
    monkeypatch, tmp_path, updated_pas_df, current_db_rows, gcs_mock
):
    """Empty-string values are converted to None so they round-trip as JSON null."""
    db_changes = {
        "new": [{"name": "Alpha", "designation": "", "iucn_category": "Ia"}],
        "changed": [],
        "deleted": [],
    }
    _patch_deps(
        monkeypatch,
        tmp_path,
        updated_pas=updated_pas_df,
        current_db=current_db_rows,
        db_changes=db_changes,
    )

    gen_tables.generate_protected_areas_diff_table(verbose=False)

    saved = pickle.loads(gcs_mock["blob"].uploaded_data)
    assert saved["new"][0]["designation"] is None
    assert saved["new"][0]["iucn_category"] == "Ia"


def test_clean_for_json_recurses_into_nested_lists_and_dicts(
    monkeypatch, tmp_path, updated_pas_df, current_db_rows, gcs_mock
):
    """Nested lists/dicts should be cleaned recursively."""
    db_changes = {
        "new": [
            {
                "bbox": [1.0, float("nan"), 3.0, float("inf")],
                "children": [{"name": ""}, {"name": "child2"}],
                "parent": {"wdpaid": "", "zone_id": None},
            }
        ],
        "changed": [],
        "deleted": [],
    }
    _patch_deps(
        monkeypatch,
        tmp_path,
        updated_pas=updated_pas_df,
        current_db=current_db_rows,
        db_changes=db_changes,
    )

    gen_tables.generate_protected_areas_diff_table(verbose=False)

    saved = pickle.loads(gcs_mock["blob"].uploaded_data)
    row = saved["new"][0]
    assert row["bbox"] == [1.0, None, 3.0, None]
    assert row["children"][0]["name"] is None
    assert row["children"][1]["name"] == "child2"
    assert row["parent"] == {"wdpaid": None, "zone_id": None}


def test_current_db_area_and_coverage_converted_to_float(
    monkeypatch, tmp_path, updated_pas_df, gcs_mock
):
    """area/coverage strings from the DB should be coerced to floats before comparison."""
    captured = {}

    def _mock_spy_make_pa_updates(current_db_df, updated_pas, verbose=True):
        captured["current_db_df"] = current_db_df.copy()
        return {"new": [], "changed": [], "deleted": []}, pd.DataFrame()

    monkeypatch.setattr(gen_tables, "generate_protected_areas_table", lambda **_: updated_pas_df)
    monkeypatch.setattr(
        gen_tables,
        "get_pas",
        lambda: [
            {"documentId": "doc-1", "area": "123.5", "coverage": "45.6", "name": "A"},
            {"documentId": "doc-2", "area": "7.25", "coverage": None, "name": "B"},
        ],
    )
    monkeypatch.setattr(gen_tables, "make_pa_updates", _mock_spy_make_pa_updates)
    monkeypatch.chdir(tmp_path)

    gen_tables.generate_protected_areas_diff_table(verbose=False)

    df = captured["current_db_df"]
    assert df["area"].tolist() == [123.5, 7.25]
    assert df["area"].dtype == float
    assert df["coverage"].iloc[0] == 45.6
    # None passes through the lambda but pandas stores it as NaN in a float column
    assert pd.isna(df["coverage"].iloc[1])
    # documentId should be preserved as a string and `id` must not be injected
    assert "id" not in df.columns
    assert df["documentId"].tolist() == ["doc-1", "doc-2"]
    assert all(isinstance(v, str) for v in df["documentId"])


def test_empty_current_db_does_not_raise(monkeypatch, tmp_path, updated_pas_df, gcs_mock):
    """When get_pas() returns an empty list, the area/coverage cast is skipped."""
    _patch_deps(
        monkeypatch,
        tmp_path,
        updated_pas=updated_pas_df,
        current_db=[],
        db_changes={
            "new": updated_pas_df.to_dict(orient="records"),
            "changed": [],
            "deleted": [],
        },
    )

    result = gen_tables.generate_protected_areas_diff_table(verbose=False)

    assert result is True  # 2 new rows, 0 changed


def test_parameters_are_forwarded_to_generate_protected_areas_table(
    monkeypatch, tmp_path, updated_pas_df, current_db_rows, gcs_mock
):
    """wdpa_file_name, mpatlas_file_name, bucket, tolerance are forwarded verbatim."""
    recorder = {}
    _patch_deps(
        monkeypatch,
        tmp_path,
        updated_pas=updated_pas_df,
        current_db=current_db_rows,
        db_changes={"new": [], "changed": [], "deleted": []},
        generate_recorder=recorder,
    )

    gen_tables.generate_protected_areas_diff_table(
        wdpa_file_name="wdpa.csv",
        mpatlas_file_name="mpa.csv",
        bucket="custom-bucket",
        tolerance=0.5,
        verbose=False,
    )

    assert recorder["wdpa_file_name"] == "wdpa.csv"
    assert recorder["mpatlas_file_name"] == "mpa.csv"
    assert recorder["bucket"] == "custom-bucket"
    assert recorder["tolerance"] == 0.5
    assert recorder["verbose"] is False


def test_verbose_logs_per_changed_column(
    monkeypatch, tmp_path, updated_pas_df, current_db_rows, gcs_mock
):
    """When verbose=True, the function iterates change_cols.columns without raising."""
    change_cols = pd.DataFrame(
        {
            "name": [True, False],
            "area": [False, False],
            "coverage": [True, True],
        }
    )
    _patch_deps(
        monkeypatch,
        tmp_path,
        updated_pas=updated_pas_df,
        current_db=current_db_rows,
        db_changes={"new": [], "changed": [{"documentId": "doc-1"}], "deleted": []},
        change_cols=change_cols,
    )

    result = gen_tables.generate_protected_areas_diff_table(verbose=True)

    assert result is True
