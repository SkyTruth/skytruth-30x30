import pytest

import src.methods.static_processes.marine_habitat_sources as marine_habitat_sources

FAKE_HABITAT_PARAMS = {
    "coldwatercorals": {
        "url": "https://example.test/corals.zip",
        "file_name": "habitats/corals.zip",
        "archive_file_name": "archive/habitats/corals_v1.zip",
    },
    "saltmarshes": {
        "url": "https://example.test/saltmarshes.zip",
        "file_name": "habitats/saltmarshes.zip",
        "archive_file_name": "archive/habitats/saltmarshes_v1.zip",
    },
    "seagrasses": {
        "url": "https://example.test/seagrasses.zip",
        "file_name": "habitats/seagrasses.zip",
        "archive_file_name": "archive/habitats/seagrasses_v1.zip",
    },
}


@pytest.fixture
def download_recorder(monkeypatch):
    """Record download_and_duplicate_zipfile calls instead of downloading files."""
    calls = []

    def _record(url, bucket, blob_name, archive_blob_name, chunk_size=None, verbose=True):
        calls.append(
            {
                "url": url,
                "bucket": bucket,
                "blob_name": blob_name,
                "archive_blob_name": archive_blob_name,
                "chunk_size": chunk_size,
            }
        )

    monkeypatch.setattr(
        marine_habitat_sources, "download_and_duplicate_zipfile", _record, raising=True
    )
    return calls


def download(habitats, recorder_bucket="test-bucket"):
    marine_habitat_sources.download_marine_habitats(
        habitats=habitats,
        marine_habitat_params=FAKE_HABITAT_PARAMS,
        bucket=recorder_bucket,
        verbose=False,
    )


def test_none_downloads_every_habitat(download_recorder):
    """Passing no habitat downloads all of them."""
    download(None)

    assert [call["blob_name"] for call in download_recorder] == [
        "habitats/corals.zip",
        "habitats/saltmarshes.zip",
        "habitats/seagrasses.zip",
    ]


def test_a_single_name_downloads_only_that_habitat(download_recorder):
    """Passing one habitat downloads just that one."""
    download("saltmarshes")

    assert len(download_recorder) == 1
    call = download_recorder[0]
    assert call["url"] == "https://example.test/saltmarshes.zip"
    assert call["blob_name"] == "habitats/saltmarshes.zip"
    assert call["archive_blob_name"] == "archive/habitats/saltmarshes_v1.zip"
    assert call["bucket"] == "test-bucket"


def test_a_list_downloads_those_habitats_in_order(download_recorder):
    """Passing multiple habitats downloads them in order."""
    download(["seagrasses", "coldwatercorals"])

    assert [call["blob_name"] for call in download_recorder] == [
        "habitats/seagrasses.zip",
        "habitats/corals.zip",
    ]


@pytest.mark.parametrize(
    "habitats",
    [
        "nonexistent",
        ["nonexistent"],
        ["coldwatercorals", "nonexistent"],
        [None],
        [1],
        [None, "nonexistent", 1],
    ],
    ids=[
        "unknown_str",
        "unknown_in_list",
        "mixed_with_valid",
        "none_entry",
        "int_entry",
        "mixed_types",
    ],
)
def test_unknown_habitats_raise_before_downloading_anything(download_recorder, habitats):
    """ValueError is raised if any habitat is unknown, and nothing is downloaded."""
    with pytest.raises(ValueError, match="unknown marine habitat"):
        download(habitats)

    assert download_recorder == [], "nothing should be downloaded when the request is invalid"
