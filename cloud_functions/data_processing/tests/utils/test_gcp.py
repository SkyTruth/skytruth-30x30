import json

import pytest
import requests
import responses

import src.utils.gcp as gcp
from src.utils.gcp import TqdmBytesIO, download_zip_to_gcs
from tests.fixtures.utils.util_mocks import (
    IterableMockBar,
    MockBar,
    MockBlob,
    MockBucket,
    MockClient,
)


@pytest.fixture(autouse=True)
def patch_tqdm(monkeypatch):
    """
    Monkey‐patch gcp.tqdm (which was imported from `from tqdm import tqdm`)
    so it returns our MockBar and records the init args.
    """

    def mock_tqdm(
        iterable=None, total=None, unit=None, unit_scale=None, desc=None, leave=None, **kwargs
    ):
        mock_tqdm.last_call = (total, unit, unit_scale, desc, leave)
        if iterable is not None:
            return IterableMockBar(iterable, **kwargs)
        else:
            return MockBar()

    monkeypatch.setattr(gcp, "tqdm", mock_tqdm)
    return mock_tqdm


@pytest.fixture
def mock_logger(monkeypatch):
    """
    Mock the logger to avoid actual logging during tests.
    """
    mock_logger = type(
        "MockLogger",
        (),
        {
            "info": lambda self, msg: None,
            "warning": lambda self, msg: None,
            "error": lambda self, msg: None,
        },
    )
    monkeypatch.setattr(gcp, "logger", mock_logger)
    return mock_logger


def test_TqdmBytesIO_init_creates_bar_with_correct_args(patch_tqdm):
    """
    Test that TqdmBytesIO initializes the tqdm bar with the correct parameters.
    """
    data = b"hello"
    total_size = 5
    chunk_size = 2

    buffer = TqdmBytesIO(data, total_size=total_size, chunk_size=chunk_size)

    assert patch_tqdm.last_call == (total_size, "B", True, "Uploading", True)
    assert isinstance(buffer.tqdm_bar, MockBar)
    assert buffer.chunk_size == chunk_size


def test_TqdmBytesIO_read_updates_bar_and_returns_bytes():
    """
    Test that reading from TqdmBytesIO updates the bar and returns the correct bytes.
    """
    data = b"abcdef"
    buffer = TqdmBytesIO(data, total_size=len(data), chunk_size=3)
    bar = buffer.tqdm_bar

    chunk1 = buffer.read(3)
    assert chunk1 == b"abc"
    assert bar.updates == [3]

    chunk2 = buffer.read()
    assert chunk2 == b"def"
    assert bar.updates == [3, 3]

    # 3) reading past EOF yields empty and still updates by 0
    chunk3 = buffer.read(1)
    assert chunk3 == b""
    assert bar.updates == [3, 3, 0]


def test_TqdmBytesIO_close_closes_both_bar_and_bytesio():
    """
    Test that closing TqdmBytesIO also closes the tqdm bar.
    """
    data = b"test"
    buffer = TqdmBytesIO(data, total_size=len(data), chunk_size=2)
    bar = buffer.tqdm_bar

    assert not buffer.closed

    buffer.close()
    assert bar.closed, "tqdm_bar.close() should have been called"
    assert buffer.closed

    # Once closed, any further read() should raise ValueError
    with pytest.raises(ValueError):
        buffer.read(1)


@responses.activate
def test_download_zip_to_gcs_happy_path_GET(monkeypatch, capsys):
    """
    Test the happy path of downloading a zip file from a URL with a GET endpoint
    and uploading it to GCS.
    """
    url = "https://example.com/archive.zip"
    bucket_name = "my-bucket"
    blob_name = "dest/archive.zip"
    body = b"foobarbaz"

    responses.add(
        responses.GET,
        url,
        body=body,
        headers={"content-length": str(len(body))},
        status=200,
    )

    mock_blob = MockBlob()
    mock_bucket = MockBucket(bucket_name, mock_blob)
    monkeypatch.setattr(
        gcp.storage,
        "Client",
        lambda: MockClient(mock_bucket),
    )

    download_zip_to_gcs(url, bucket_name, blob_name, verbose=True)

    # 1) Ensure the GET was made exactly once
    assert len(responses.calls) == 1
    assert responses.calls[0].request.method == "GET"
    assert responses.calls[0].request.url == url

    # 2) Check printed output
    out = capsys.readouterr().out
    assert f"getting data from {url}" in out
    assert "streaming data into buffer" in out
    assert f"Uploading to gs://{bucket_name}/{blob_name}" in out

    # 3) Verify that GCS upload got the full concatenated body
    assert mock_blob.uploaded_data == body
    assert mock_blob.kwargs["content_type"] == "application/zip"
    assert mock_blob.kwargs["rewind"] is True
    assert mock_blob.kwargs["timeout"] == 600


@responses.activate
def test_download_zip_to_gcs_happy_path_POST(monkeypatch):
    url = "https://api.example.com/zip"
    bucket_name = "bucket"
    blob_name = "file.zip"
    data = {"foo": "bar"}
    params = {"p": "v"}
    headers = {"H": "h"}
    body = b"x"

    responses.add(
        responses.POST,
        url,
        body=body,
        headers={"content-length": "1"},
        status=200,
        match=[
            responses.matchers.query_param_matcher(params),
            responses.matchers.urlencoded_params_matcher(data),
        ],
    )

    mock_blob = MockBlob()
    mock_bucket = MockBucket(bucket_name, mock_blob)
    monkeypatch.setattr(
        gcp.storage,
        "Client",
        lambda: MockClient(mock_bucket),
    )

    download_zip_to_gcs(
        url,
        bucket_name,
        blob_name,
        data=data,
        params=params,
        headers=headers,
        verbose=False,
    )

    assert len(responses.calls) == 1

    req = responses.calls[0].request
    assert req.method == "POST"
    assert req.url.endswith("?p=v")
    assert req.body == "foo=bar"
    assert req.headers["H"] == "h"

    assert mock_blob.uploaded_data == b"x"


@responses.activate
def test_download_zip_to_gcs_http_error_raised(capsys):
    url = "https://example.com/missing.zip"
    responses.add(responses.GET, url, status=404)

    with pytest.raises(requests.HTTPError):
        download_zip_to_gcs(url, "b", "f", verbose=False)

    log = json.loads(capsys.readouterr().out)

    assert "HTTP error during download" in log["message"]
    assert log["severity"] == "ERROR"


@responses.activate
def test_download_zip_to_gcsconnection_error_raised(capsys):
    url = "https://example.com/unreachable.zip"

    responses.add(
        responses.GET,
        url,
        body=requests.ConnectionError("no network"),
    )

    with pytest.raises(requests.ConnectionError):
        download_zip_to_gcs(url, "b", "f", verbose=False)

    log = json.loads(capsys.readouterr().out)

    assert "Error during download" in log["message"]
    assert log["severity"] == "ERROR"


@responses.activate
def test_upload_exception_is_logged_and_raised(monkeypatch, capsys):
    url = "https://example.com/archive.zip"
    body = b"a"
    responses.add(
        responses.GET,
        url,
        body=body,
        headers={"content-length": "1"},
        status=200,
    )

    # Patch storage so upload_from_file raises
    class BadBlob(MockBlob):
        def upload_from_file(self, file_obj, **kwargs):
            raise RuntimeError("Upload Failed")

    bad_blob = BadBlob()
    mock_bucket = MockBucket("b", bad_blob)
    monkeypatch.setattr(
        gcp.storage,
        "Client",
        lambda: MockClient(mock_bucket),
    )

    with pytest.raises(RuntimeError):
        download_zip_to_gcs(url, "b", "f", verbose=False)

    log = json.loads(capsys.readouterr().out)

    assert "Error during upload to GCS" in log["message"]
    assert log["severity"] == "ERROR"
