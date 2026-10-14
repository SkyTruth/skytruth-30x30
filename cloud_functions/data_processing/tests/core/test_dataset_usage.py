from unittest.mock import Mock

import pytest

from src.core import commons, dataset_usage


def test_cached_dataset_use_reports_after_each_successful_return(monkeypatch):
    frame = Mock()
    frame.copy.return_value = frame
    monkeypatch.setattr(commons, "_load_iho_regions_cached", Mock(return_value=frame))
    recorder = Mock()
    monkeypatch.setattr(commons, "record_dataset_use", recorder)
    assert commons.load_iho_regions() is frame
    assert commons.load_iho_regions() is frame
    assert recorder.call_args_list == [(("iho-world-seas",),)] * 2


def test_failed_or_derived_dataset_access_does_not_report_shared_use(monkeypatch):
    loader = Mock(side_effect=RuntimeError("unavailable"))
    recorder = Mock()
    monkeypatch.setattr(commons, "_load_iho_regions_cached", loader)
    monkeypatch.setattr(commons, "record_dataset_use", recorder)
    with pytest.raises(RuntimeError):
        commons.load_iho_regions()
    loader.side_effect = None
    loader.return_value = Mock()
    commons.load_iho_regions(buffer=True)
    recorder.assert_not_called()


def test_unconfigured_local_work_and_reporting_failure_leave_operations_functional(monkeypatch):
    monkeypatch.delenv("K_SERVICE", raising=False)
    monkeypatch.setattr(dataset_usage, "_reporter", None)
    dataset_usage.record_dataset_use("iho-world-seas")
    assert dataset_usage._reporter is None
    reporter = Mock()
    reporter.flush.return_value = False
    monkeypatch.setattr(dataset_usage, "_reporter", reporter)
    monkeypatch.setenv("K_SERVICE", "x30-prod-data")
    dataset_usage.record_dataset_use("iho-world-seas")
    reporter.recordUsage.assert_called_once_with("iho-world-seas", "use")
    reporter.flush.assert_called_once()
