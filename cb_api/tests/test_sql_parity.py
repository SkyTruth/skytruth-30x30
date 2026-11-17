"""Guards that the ported analysis still sends the cloud function's SQL, apart from
one intended change to the stats query's join.

Compares the strings input to sqlalchemy.text() at runtime,
so src/analysis.py can be reformatted as long as the statements the database
receives are unchanged. Delete once the cloud function is removed.
"""

import importlib.util
import pathlib
from collections.abc import Callable
from types import ModuleType

import pytest
import sqlalchemy

from src.analysis import get_locations_stats

ORIGINAL = (
    pathlib.Path(__file__).resolve().parents[2]
    / "cloud_functions"
    / "analysis"
    / "src"
    / "analysis.py"
)

GEOMETRY = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}
TABLE = "eez_minus_mpa_v2"

CLOUD_FUNCTION_JOIN = f"""                        FROM
                            data.{TABLE},
                            user_data_stats
                        WHERE
                            ST_Intersects(the_geom, user_data_stats.geom)
"""
CB_API_JOIN = f"""                        FROM
                            user_data_stats
                            LEFT JOIN data.{TABLE}
                                ON ST_Intersects(the_geom, user_data_stats.geom)
"""

pytestmark = pytest.mark.skipif(
    not ORIGINAL.exists(), reason="the analysis cloud function has been removed"
)


class FakeRow(dict):
    """A result row readable by name, as cb_api reads it, and by position, as the cloud
    function reads it."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class FakeResult:
    def mappings(self):
        return self

    def one(self):
        return {"geom_type": "ST_Polygon", "is_empty": False}

    def all(self):
        # What the stats query returns when nothing intersects
        return [FakeRow(location=None, portion_area_km2=None, user_area_km2=0.0)]


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, statement, parameters=None):
        return FakeResult()


class FakeEngine:
    def connect(self):
        return FakeConnection()


def load_original() -> ModuleType:
    spec = importlib.util.spec_from_file_location("legacy_analysis", ORIGINAL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def capture_sql(run: Callable[[], object]) -> list[str]:
    """Record every string passed to sqlalchemy.text() while `run` executes."""
    statements: list[str] = []
    original_text = sqlalchemy.text

    def spy(statement: str):
        statements.append(statement)
        return original_text(statement)

    sqlalchemy.text = spy
    try:
        run()
    finally:
        sqlalchemy.text = original_text
    return statements


def test_runtime_sql_is_identical_to_the_cloud_function():
    ported = capture_sql(lambda: get_locations_stats(FakeEngine(), GEOMETRY, TABLE))
    legacy = load_original()
    original = capture_sql(
        lambda: legacy.get_locations_stats("marine", FakeEngine(), GEOMETRY, TABLE)
    )

    assert len(ported) == len(original) == 2, "expected a topology check and a stats query"
    assert ported[0] == original[0]
    # The one intended difference: a LEFT JOIN instead of a comma join and WHERE, so a
    # shape that intersects nothing still returns a row carrying its drawn area
    assert ported[1] == original[1].replace(CLOUD_FUNCTION_JOIN, CB_API_JOIN)
    assert CLOUD_FUNCTION_JOIN in original[1], "the cloud function's join has changed"


def test_the_table_name_reaches_the_statement():
    statements = capture_sql(lambda: get_locations_stats(FakeEngine(), GEOMETRY, TABLE))

    assert f"data.{TABLE}" in statements[1]
